package local.lastbook.core

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.URLDecoder
import java.net.URLEncoder

class WebResponse(val status: Int = 200, val mime: String = "application/json", val bytes: ByteArray = ByteArray(0), val headers: Map<String, String> = emptyMap())

/**
 * The in-process routes behind the WebView map and reader. No port is opened: WebViewClient intercepts every request
 * for https://lastbook.local/ and answers from these routes, exactly as the iPad's lastbook:// scheme handler does.
 */
class WebRoutes(
    private val context: Context,
    private val library: Library,
    private val videos: Videos,
    private val map: MapEngine,
    private val chat: ChatEngine,
    private val zim: ZimReader,
) {
    companion object {
        const val ORIGIN = "https://lastbook.local"
    }

    private fun asset(path: String): ByteArray? = runCatching {
        context.assets.open(path).use { it.readBytes() }
    }.getOrNull()

    fun handle(path: String, query: Map<String, String>, method: String = "GET", body: ByteArray? = null): WebResponse {
        val p = path.substringBefore('?')
        // Bundled web UI
        if (p == "/" || p == "/index.html") return web("index.html")
        if (p.startsWith("/ui/")) return web(p.removePrefix("/ui/"))
        if (p == "/api/health") return json(JSONObject().put("service", "survival-library").put("offline", true))

        // Map
        Regex("^/api/map/tile/(\\d+)/(\\d+)/(\\d+)$").find(p)?.let { m ->
            return WebResponse(200, "application/json", map.tile(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt()),
                mapOf("Cache-Control" to "max-age=86400"))
        }
        if (p == "/api/map/info") return WebResponse(200, "application/json", map.info())
        if (p == "/api/map/pins") {
            val kinds = (query["kinds"] ?: "").split(',').filter { it.isNotEmpty() }.toSet()
            return WebResponse(200, "application/json", map.pins(
                query["west"]?.toDoubleOrNull() ?: -180.0, query["south"]?.toDoubleOrNull() ?: -85.0,
                query["east"]?.toDoubleOrNull() ?: 180.0, query["north"]?.toDoubleOrNull() ?: 85.0,
                query["zoom"]?.toIntOrNull() ?: 8, kinds))
        }
        if (p == "/api/map/members") {
            val kinds = (query["kinds"] ?: "").split(',').filter { it.isNotEmpty() }.toSet()
            return WebResponse(200, "application/json", map.members(
                query["west"]?.toDoubleOrNull() ?: -180.0, query["south"]?.toDoubleOrNull() ?: -85.0,
                query["east"]?.toDoubleOrNull() ?: 180.0, query["north"]?.toDoubleOrNull() ?: 85.0,
                kinds, query["lat"]?.toDoubleOrNull() ?: 0.0, query["lon"]?.toDoubleOrNull() ?: 0.0))
        }
        if (p == "/api/map/near") {
            val classes = (query["cls"] ?: "").split(',').filter { it.isNotEmpty() }
            return WebResponse(200, "application/json", map.near(
                query["lat"]?.toDoubleOrNull() ?: 0.0, query["lon"]?.toDoubleOrNull() ?: 0.0, classes,
                query["limit"]?.toIntOrNull() ?: 8))
        }
        if (p == "/api/map/resources") {
            return WebResponse(200, "application/json", map.resources(
                query["west"]?.toDoubleOrNull() ?: -180.0, query["south"]?.toDoubleOrNull() ?: -85.0,
                query["east"]?.toDoubleOrNull() ?: 180.0, query["north"]?.toDoubleOrNull() ?: 85.0,
                query["zoom"]?.toIntOrNull() ?: 8, (query["kinds"] ?: "").split(',')))
        }
        Regex("^/api/map/terrain/(\\d+)/(\\d+)/(\\d+)\\.png$").find(p)?.let { m ->
            val b = map.terrainTile(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
            return if (b == null) WebResponse(204, "image/png") else WebResponse(200, "image/png", b)
        }
        Regex("^/api/map/crops/(\\d+)/(\\d+)/(\\d+)\\.png$").find(p)?.let { m ->
            val b = map.cropTile(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
            return if (b == null) WebResponse(204, "image/png") else WebResponse(200, "image/png", b)
        }
        Regex("^/api/map/aerial/(\\d+)/(\\d+)/(\\d+)$").find(p)?.let { m ->
            val b = map.aerialTile(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
            return if (b == null) WebResponse(204, "image/jpeg") else WebResponse(200, "image/jpeg", b)
        }
        if (p.startsWith("/api/map/bldg3d/")) return WebResponse(200, "application/octet-stream", ByteArray(4))
        if (p == "/api/places") {
            val near = query["near"]?.split(',')?.mapNotNull { it.toDoubleOrNull() }?.takeIf { it.size == 2 }?.let { it[0] to it[1] }
            return WebResponse(200, "application/json", map.places(query["q"] ?: "", near, query["limit"]?.toIntOrNull() ?: 20))
        }

        // Videos / documents / transcripts
        if (p == "/api/videos") return json(JSONArray(videos.home()))
        if (p == "/api/videos/all") {
            return json(JSONArray(videos.list("all", query["q"] ?: "", query["len"] ?: "", query["sort"] ?: "", query["offset"]?.toIntOrNull() ?: 0)["items"] as List<*>))
        }
        if (p.startsWith("/api/videos/related/")) return json(JSONArray(videos.related(p.removePrefix("/api/videos/related/"))))
        if (p.startsWith("/api/videos/")) {
            val row = p.removePrefix("/api/videos/")
            return json(JSONObject(videos.list(row, query["q"] ?: "", query["len"] ?: "", query["sort"] ?: "", query["offset"]?.toIntOrNull() ?: 0)))
        }
        if (p.startsWith("/api/doc/")) {
            val id = decode(p.removePrefix("/api/doc/"))
            return videos.doc(id)?.let { json(JSONObject(it)) } ?: WebResponse(404, "application/json", JSONObject().put("error", "Not found.").toString().toByteArray())
        }
        if (p.startsWith("/api/transcript/")) {
            val id = decode(p.removePrefix("/api/transcript/"))
            return videos.transcript(id)?.let { json(JSONObject(it as Map<*, *>)) } ?: WebResponse(404, "application/json", JSONObject().put("error", "unknown video").toString().toByteArray())
        }

        // Library/search
        if (p == "/api/library") return json(JSONObject(librarySummary()))
        if (p == "/api/find") return json(JSONArray(chat.find(query["q"] ?: "", query["kind"] ?: "all", 200)))
        if (p == "/api/search") return json(JSONArray(chat.search(query["q"] ?: "", 40)))
        if (p == "/api/retrieve") {
            val q = query["q"] ?: ""
            return json(JSONObject().put("q", q).put("results", JSONArray(chat.sources(q, query["k"]?.toIntOrNull() ?: 8)))
                .put("semantic", JSONObject().put("available", false)))
        }
        if (p == "/api/topics") return json(JSONArray(Catalog.topics(context)))
        if (p == "/api/assistant/status") return json(JSONObject(chat.status()))
        if (p == "/api/assistant/local" && method == "POST") return json(JSONObject(chat.setLocal(method, body)))
        if (p == "/api/chat" && method == "POST") return json(JSONObject(chat.answerFromBody(body)))

        // Reading pages and PDFs
        if (p == "/api/pdfpage") {
            val rel = decode(query["path"] ?: "")
            val page = (query["n"] ?: "1").toIntOrNull() ?: 1
            val file = library.lib?.resolve(rel)
            val png = file?.let { PdfPages.render(it, page - 1) }
            return if (png == null) WebResponse(404, "text/plain") else WebResponse(200, "image/png", png)
        }

        // Library files
        val rel = decode(p.removePrefix("/"))
        if (rel.isNotEmpty() && isAllowed(rel)) {
            val file = library.lib?.resolve(rel)
            if (file != null && file.isFile) {
                if (rel.lowercase().endsWith(".pdf")) return pdfViewer(rel, file)
                val bytes = runCatching { file.readBytes() }.getOrNull() ?: return WebResponse(404)
                val headers = if (rel.lowercase().endsWith(".html") || rel.lowercase().endsWith(".htm"))
                    mapOf("Content-Security-Policy" to "sandbox; default-src 'none'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; font-src 'self' data:") else emptyMap()
                return WebResponse(200, Mime.of(rel), bytes, headers)
            }
        }
        if (p.startsWith("/zim/")) {
            val rest = p.removePrefix("/zim/")
            val name = rest.substringBefore('/')
            val path = rest.substringAfter('/', "")
            if (name.isEmpty()) return WebResponse(404)
            return zim.content(name, path)
        }
        if (p == "/api/zim/search") {
            return WebResponse(200, "application/json", zim.search(query["name"] ?: "", query["q"] ?: "", query["full"] == "1"))
        }
        if (p == "/api/zim") return WebResponse(200, "application/json", JSONArray(zim.names()).toString().toByteArray())
        return WebResponse(404, "text/plain", "Not found.".toByteArray())
    }

    private fun web(rel: String): WebResponse {
        val b = asset("web/$rel") ?: return WebResponse(404)
        return WebResponse(200, Mime.of(rel), b, mapOf("Cache-Control" to "no-store"))
    }

    private fun json(o: Any): WebResponse = WebResponse(200, "application/json", o.toString().toByteArray())

    private fun decode(s: String): String = runCatching { URLDecoder.decode(s, "UTF-8") }.getOrDefault(s)

    private fun isAllowed(rel: String): Boolean {
        if (rel == "reader.css") return true
        if (rel.lowercase().endsWith(".zim")) return false
        val prefixes = listOf("documents/", "pages/", "videos/", "videos-external/", "transcripts/", "metadata/videos/", "courses/", "collections/", "assets/")
        return prefixes.any { rel.startsWith(it) } || rel.startsWith("library-data/")
    }

    private fun pdfViewer(rel: String, file: File): WebResponse {
        val pages = PdfPages.pageCount(file)
        val title = rel.substringAfterLast('/')
        val rows = (1..pages).joinToString("") { n -> "<div class=p><img loading=lazy alt='Page $n' src='/api/pdfpage?path=${enc(rel)}&n=$n'></div>" }
        val html = "<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'><title>${esc(title)}</title>" +
            "<style>html{background:#525659}body{margin:0;padding:8px}.p{max-width:1000px;margin:0 auto 8px}.p img{display:block;width:100%;height:auto;background:#fff}</style></head><body>$rows</body></html>"
        return WebResponse(200, "text/html; charset=utf-8", html.toByteArray())
    }

    private fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")
    private fun esc(s: String): String = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

    private fun librarySummary(): Rec {
        val lib = library.lib
        val summary = lib?.resolve("summary.json")?.takeIf { it.isFile }?.let { f ->
            runCatching { JSONObject(f.readText()).toStringMap() }.getOrNull()
        } ?: emptyMap()
        val out = LinkedHashMap<String, Any?>()
        for (k in listOf("resources", "pdfs", "pdf_pages", "web_pages", "videos", "collections", "document_bytes")) out[k] = summary[k] ?: JSONObject.NULL
        out["zims"] = library.zimFiles().map { it.name }
        out["pack"] = library.packInfo() != null
        out["pins"] = true
        return out
    }
}

object Mime {
    fun of(ext: String): String {
        val e = ext.substringAfterLast('.', "").lowercase()
        return when (e) {
            "html", "htm" -> "text/html; charset=utf-8"; "js", "mjs" -> "text/javascript; charset=utf-8"
            "css" -> "text/css; charset=utf-8"; "json", "webmanifest" -> "application/json"
            "svg" -> "image/svg+xml"; "png" -> "image/png"; "jpg", "jpeg" -> "image/jpeg"; "webp" -> "image/webp"
            "gif" -> "image/gif"; "mp4", "m4v" -> "video/mp4"; "webm" -> "video/webm"; "mkv" -> "video/x-matroska"
            "mp3" -> "audio/mpeg"; "m4a" -> "audio/mp4"; "vtt" -> "text/vtt; charset=utf-8"; "txt" -> "text/plain; charset=utf-8"
            "pdf" -> "application/pdf"; "woff2" -> "font/woff2"; "woff" -> "font/woff"; "ttf" -> "font/ttf"
            else -> "application/octet-stream"
        }
    }
}

object PdfPages {
    fun pageCount(file: File): Int = runCatching {
        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { fd ->
            PdfRenderer(fd).use { it.pageCount }
        }
    }.getOrDefault(0)

    fun render(file: File, index: Int): ByteArray? = runCatching {
        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { fd ->
            PdfRenderer(fd).use { r ->
                if (index !in 0 until r.pageCount) return null
                r.openPage(index).use { page ->
                    val width = 1200
                    val height = (width.toFloat() * page.height / page.width).toInt().coerceAtLeast(1)
                    val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                    bmp.eraseColor(Color.WHITE)
                    page.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    val out = ByteArrayOutputStream()
                    bmp.compress(Bitmap.CompressFormat.PNG, 90, out)
                    bmp.recycle()
                    out.toByteArray()
                }
            }
        }
    }.getOrNull()
}
