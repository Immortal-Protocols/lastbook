package local.lastbook.core

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.kiwix.libkiwix.JNIKiwix
import org.kiwix.libzim.Archive
import org.kiwix.libzim.Query
import org.kiwix.libzim.Searcher
import org.kiwix.libzim.SuggestionSearcher
import java.io.File
import java.net.URLDecoder

/** ZIM encyclopedias through the pinned Kiwix/libzim Android libraries (GPL-3.0; see THIRD_PARTY_NOTICES.md). */
class ZimReader(private val context: Context, private val library: Library) {
    private val open = HashMap<String, Archive?>()
    private val lock = Any()
    @Volatile private var prepared = false

    private fun prepare() {
        if (prepared) return
        synchronized(this) {
            if (prepared) return
            val dir = File(context.filesDir, "kiwix").apply { mkdirs() }
            runCatching { JNIKiwix(context).setDataDirectory(dir.absolutePath) }
            prepared = true
        }
    }

    fun archive(name: String): Archive? {
        prepare()
        synchronized(lock) {
            if (open.containsKey(name)) return open[name]
            val f = File(library.lib, "collections/$name")
            if (!f.isFile) { open[name] = null; return null }
            val a = runCatching { Archive(f.absolutePath) }.getOrNull()
            open[name] = a
            return a
        }
    }

    fun names(): List<String> = library.zimFiles().map { it.name }

    fun mainPath(name: String): String? = runCatching {
        val a = archive(name) ?: return null
        a.getMainEntry().getItem(true).getPath()
    }.getOrNull()

    fun entry(name: String, path: String): Item? = runCatching {
        val a = archive(name) ?: return null
        val decoded = runCatching { URLDecoder.decode(path, "UTF-8") }.getOrDefault(path)
        val e = if (decoded.isEmpty() || decoded == "/") a.getMainEntry() else a.getEntryByPath(decoded.trimStart('/'))
        val item = e.getItem(true)
        Item(item.getPath(), item.getTitle(), item.getMimetype(), item.getData().getData())
    }.getOrNull()

    data class Item(val path: String, val title: String, val mime: String, val bytes: ByteArray)

    fun search(name: String, q: String, full: Boolean, limit: Int = 20): ByteArray {
        val a = archive(name) ?: return "[]".toByteArray()
        val out = JSONArray()
        runCatching {
            if (full) {
                if (a.hasFulltextIndex()) {
                    val searcher = Searcher(a)
                    val it = searcher.search(Query(q)).getResults(0, limit)
                    while (it.hasNext() && out.length() < limit) {
                        val e = it.next()
                        out.put(JSONObject().put("title", it.title).put("path", it.path).put("snippet", it.snippet))
                    }
                }
            } else {
                if (a.hasTitleIndex()) {
                    val it = SuggestionSearcher(a).suggest(q).getResults(0, limit)
                    while (it.hasNext() && out.length() < limit) {
                        val s = it.next()
                        out.put(JSONObject().put("title", s.title).put("path", s.path).put("snippet", s.snippet))
                    }
                }
            }
        }
        return out.toString().toByteArray()
    }

    fun content(name: String, path: String): WebResponse {
        val item = entry(name, path) ?: return WebResponse(404, "text/plain", "Not found.".toByteArray())
        var bytes = item.bytes
        if (item.mime.startsWith("text/html")) {
            var html = String(bytes, Charsets.UTF_8)
            val prefix = "/zim/$name/"
            // Root-relative links point at the archive root, so send them through the /zim/<name>/ route.
            html = html.replace(Regex("((?:href|src)=)([\"'])/(?!/)"), "$1$2$prefix")
            if (!Regex("(?i)<base\\s").containsMatchIn(html)) {
                // Relative links are written against the item's own folder (e.g. App/IntroPage uses ../_res_/).
                // The WebView's document URL is /zim/<name>/, so the base must restore the item's folder.
                val dir = item.path.trimStart('/').substringBeforeLast('/', "")
                val docBase = prefix + if (dir.isEmpty()) "" else "$dir/"
                html = html.replaceFirst(Regex("(?i)<head[^>]*>"), "$0<base href=\"$docBase\">")
            }
            bytes = html.toByteArray()
        }
        return WebResponse(200, item.mime, bytes, mapOf("Cache-Control" to "max-age=86400"))
    }
}
