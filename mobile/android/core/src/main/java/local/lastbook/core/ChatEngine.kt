package local.lastbook.core

import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import local.lastbook.core.ai.LlamaAndroid
import java.util.concurrent.atomic.AtomicLong

/**
 * Chat's library half: keyword retrieval over the library's own FTS5 index, the catalog and video transcripts. When a
 * local GGUF is present the same sources become the system context for the on-device model; without one the answer is
 * the honest list of matching pages, exactly as desktop and iPad Chat do.
 */
class ChatEngine(
    private val context: android.content.Context,
    private val library: Library,
    private val videos: Videos,
    private val catalog: Catalog,
    private val paths: LastbookPaths,
) {
    private val llama = AtomicLong(0L)
    @Volatile private var llamaPath: String? = null

    private val stop = setOf("a", "an", "and", "are", "aren", "as", "at", "be", "been", "but", "by", "can", "do", "does", "doesn",
        "don", "during", "for", "from", "get", "got", "had", "has", "have", "help", "how", "i", "if", "in", "into", "is", "isn",
        "it", "its", "keep", "make", "me", "my", "need", "no", "not", "of", "off", "on", "or", "our", "out", "please", "should",
        "so", "some", "someone", "something", "stay", "still", "tap", "that", "the", "their", "them", "then", "there", "these",
        "they", "this", "to", "up", "us", "was", "we", "what", "when", "where", "which", "who", "why", "will", "with", "without",
        "won", "work", "you", "your")

    private val synonyms = mapOf(
        "cut" to listOf("wound", "laceration", "bleeding"), "cuts" to listOf("wound", "laceration"),
        "bleed" to listOf("bleeding", "hemorrhage"), "bleeding" to listOf("hemorrhage", "blood loss"),
        "burn" to listOf("burns", "scald"), "broken" to listOf("fracture"), "sprain" to listOf("strain"),
        "toilet" to listOf("latrine", "sanitation", "excreta"), "sewage" to listOf("sewer", "wastewater"),
        "purify" to listOf("purification", "disinfect", "treatment"), "filter" to listOf("filtration"),
        "bleach" to listOf("chlorine", "hypochlorite"), "power" to listOf("electricity", "outage"),
        "generator" to listOf("generators"), "fridge" to listOf("refrigerator", "refrigerated"),
        "food" to listOf("spoilage", "food safety"), "canning" to listOf("canned", "canner"),
        "cold" to listOf("hypothermia", "cold weather"), "heat" to listOf("heat stroke", "heat exhaustion"),
        "cpr" to listOf("resuscitation", "chest compressions"), "choking" to listOf("airway"),
        "baby" to listOf("newborn", "infant"), "pregnant" to listOf("pregnancy"), "diarrhea" to listOf("diarrhoea", "dehydration"),
        "radio" to listOf("amateur radio", "ham"), "compass" to listOf("navigation", "bearing"),
        "repair" to listOf("maintenance"), "sharpen" to listOf("sharpening"), "rope" to listOf("knots"),
        "pump" to listOf("pumps"), "well" to listOf("wells", "borehole"), "mold" to listOf("mould"),
    )

    private fun terms(q: String): List<String> {
        val words = Regex("[a-z0-9]+").findAll(q.lowercase()).map { it.value }.filter { it.length > 2 && it !in stop }.toList()
        val out = LinkedHashSet<String>()
        words.forEach { w -> out += w; synonyms[w]?.forEach { out += it } }
        return out.toList()
    }

    private fun ftsExpr(q: String): String {
        val t = terms(q)
        if (t.isEmpty()) return ""
        return t.joinToString(" OR ") { "\"${it.replace("\"", "")}\"" }
    }

    fun search(q: String, limit: Int = 40): List<Rec> {
        if (q.isBlank()) return emptyList()
        val db = library.db("search.sqlite") ?: return emptyList()
        val expr = ftsExpr(q)
        if (expr.isEmpty()) return emptyList()
        val out = ArrayList<Rec>()
        val ftsOk = runCatching {
            db.rawQuery("SELECT doc_id,title,collection,category,path,page,body FROM pages WHERE pages MATCH ? LIMIT ?",
                arrayOf(expr, limit.toString())).use { c ->
                while (c.moveToNext()) out += mapOf(
                    "id" to c.getString(0), "title" to c.getString(1), "collection" to c.getString(2),
                    "category" to c.getString(3), "path" to c.getString(4), "page" to c.getInt(5),
                    "excerpt" to excerpt(c.getString(6) ?: "", terms(q)),
                )
            }
            true
        }.getOrDefault(false)
        if (ftsOk) return out
        // Android's system SQLite may be built without FTS5. The FTS table's content table is ordinary SQL, so search
        // it with LIKE: group each query word with its synonyms by OR, and rank title matches first.
        val baseWords = Regex("[a-z0-9]+").findAll(q.lowercase()).map { it.value }.filter { it.length > 2 && it !in stop }.distinct().toList()
        val groups = baseWords.map { w -> (listOf(w) + (synonyms[w] ?: emptyList())).distinct() }
        if (groups.isEmpty()) return emptyList()
        val ts = groups.flatten().distinct()
        val cond = groups.joinToString(" AND ") { g ->
            "(" + g.joinToString(" OR ") { "(lower(c1) LIKE ? OR lower(c6) LIKE ?)" } + ")"
        }
        val scoreExpr = baseWords.joinToString(" + ") { "(CASE WHEN lower(c1) LIKE ? THEN 3 ELSE 0 END)" }
        val args = ArrayList<String>()
        for (w in baseWords) args += "%${w.replace("%", "")}%"
        for (g in groups) for (t in g) { args += "%${t.replace("%", "")}%"; args += "%${t.replace("%", "")}%" }
        args += limit.toString()
        runCatching {
            db.rawQuery("SELECT c0,c1,c2,c3,c4,c5,c6 FROM pages_content WHERE $cond ORDER BY ($scoreExpr) DESC LIMIT ?", args.toTypedArray()).use { c ->
                while (c.moveToNext()) out += mapOf(
                    "id" to c.getString(0), "title" to c.getString(1), "collection" to c.getString(2),
                    "category" to c.getString(3), "path" to c.getString(4), "page" to c.getInt(5),
                    "excerpt" to excerpt(c.getString(6) ?: "", ts),
                )
            }
        }
        return out
    }

    fun find(q: String, kind: String = "all", limit: Int = 200): List<Rec> {
        catalog.ensure(library)
        val words = q.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
        return catalog.records.asSequence()
            .filter { r ->
                (kind == "all" || r.s("kind") == kind || (kind == "read" && r.s("kind") in setOf("pdf", "html", "pptx"))) &&
                    (words.isEmpty() || words.all { w ->
                        (r.s("title") + " " + r.s("publisher") + " " + r.s("collection") + " " + r.s("category")).lowercase().contains(w)
                    })
            }
            .take(limit)
            .mapNotNull { Catalog.publicRec(it, full = true) }
            .toList()
    }

    fun sources(q: String, k: Int = 8): List<Rec> {
        val found = search(q, k * 2)
        val out = ArrayList<Rec>()
        catalog.ensure(library)
        var n = 0
        for (r in found) {
            val rec = catalog.get(r.s("id")) ?: continue
            n++
            val key = "S$n"
            val isVideo = rec.s("kind") == "video" || rec.s("kind") == "transcript"
            val videoId = if (rec.s("kind") == "transcript") catalog.byPath(rec.s("video_path"))?.s("id") ?: rec.s("video_id") else rec.s("id")
            val o = LinkedHashMap<String, Any?>()
            o["key"] = key
            o["kind"] = if (isVideo) "video" else rec.s("kind")
            o["doc_id"] = if (isVideo) videoId else rec.s("id")
            o["title"] = Catalog.cleanTitle(rec)
            o["publisher"] = rec.s("publisher")
            o["year"] = Catalog.yearOf(rec) ?: JSONObject.NULL
            o["page"] = r["page"]
            o["excerpt"] = r["excerpt"]
            if (isVideo) o["t"] = JSONObject.NULL
            out += o
            if (out.size >= k) break
        }
        return out
    }

    private fun excerpt(text: String, terms: List<String>): String {
        val lower = text.lowercase()
        val at = terms.map { lower.indexOf(it) }.filter { it >= 0 }.minOrNull() ?: 0
        val start = (at - 140).coerceAtLeast(0)
        val end = (at + 260).coerceAtMost(text.length)
        return (if (start > 0) "… " else "") + text.substring(start, end).replace(Regex("\\s+"), " ").trim() + (if (end < text.length) " …" else "")
    }

    fun status(): Rec {
        val model = localModelFile()
        val state = if (model == null) "absent" else "stopped"
        return mapOf(
            "online" to (model != null),
            "local" to mapOf(
                "state" to state,
                "phase" to if (model == null) "unavailable" else "ready",
                "message" to if (model == null) "No local AI file on this phone. Chat shows the library pages that match."
                    else "Local AI ready. It starts when you ask a question.",
                "file" to (model?.name ?: ""),
            ),
        )
    }

    fun canGenerate(): Boolean = localModelFile() != null

    /** One answer written on this phone from the retrieved sources. Returns null when the runtime or model cannot start. */
    fun generate(question: String, sources: List<Rec>): String? {
        val model = localModelFile() ?: return null
        var h = llama.get()
        if (h == 0L || llamaPath != model.path) {
            if (h != 0L) { runCatching { LlamaAndroid.nativeFree(h) }; llama.set(0L) }
            val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 6)
            h = runCatching { LlamaAndroid.nativeLoad(model.path, 2048, threads) }.getOrDefault(0L)
            if (h == 0L) return null
            llama.set(h); llamaPath = model.path
        }
        val src = StringBuilder()
        for ((i, s) in sources.take(3).withIndex()) {
            val key = "S${i + 1}"
            src.append("[").append(key).append("] ").append(s.s("title"))
            val where = listOfNotNull(s.s("publisher").takeIf { it.isNotEmpty() },
                (s["page"] as? Number)?.let { "page $it" }).joinToString(", ")
            if (where.isNotEmpty()) src.append(" (").append(where).append(")")
            s.str("excerpt")?.let { src.append(": ").append(it.take(200)) }
            src.append("\n")
            if (src.length > 6000) break
        }
        val system = "You answer questions from the Lastbook offline library. Use only the sources below. " +
            "Start immediately with the direct answer and practical steps, citing source keys like [S1] or [S2]. " +
            "Do not repeat the question or write internal analysis/notes. If the sources do not answer it, say the library does not cover it.\n\nSources:\n" + src
        val texts = arrayListOf<String>()
        val special = arrayListOf<Boolean>()
        fun sp(t: String) { texts.add(t); special.add(true) }
        fun tx(t: String) { texts.add(t); special.add(false) }
        sp("<|turn>system\n"); tx(system); sp("<turn|>\n")
        sp("<|turn>user\n"); tx(question); sp("<turn|>\n")
        sp("<|turn>model\n<|channel>thought\n")
        tx("I have checked the sources and will now write a direct, practical answer citing [S1], [S2], [S3].\n")
        sp("<channel|>")
        return runCatching {
            LlamaAndroid.nativeGenerate(h, texts.toTypedArray(), special.toBooleanArray(), 160, 0.2f, 40, 0.95f)
                .trim().takeIf { it.isNotEmpty() }
        }.getOrNull()
    }

    fun stop() { val h = llama.get(); if (h != 0L) runCatching { LlamaAndroid.nativeCancel(h) } }

    fun release() {
        val h = llama.getAndSet(0L)
        if (h != 0L) runCatching { LlamaAndroid.nativeFree(h) }
        llamaPath = null
    }

    fun localModelFile(): File? {
        val dir = library.root?.resolve("models") ?: paths.modelsDir
        if (!dir.isDirectory) return null
        return dir.listFiles()?.filter { it.isFile && it.name.endsWith(".gguf") && isGguf(it) }?.maxByOrNull { it.length() }
    }

    private fun isGguf(f: File): Boolean = runCatching {
        val head = ByteArray(4)
        f.inputStream().use { if (it.read(head) != 4) return false }
        String(head, Charsets.US_ASCII) == "GGUF"
    }.getOrDefault(false)

    fun setLocal(method: String, body: ByteArray?): Rec = status()

    fun answerFromBody(body: ByteArray?): Rec {
        val q = runCatching { body?.let { JSONObject(String(it)).optString("q") } ?: "" }.getOrDefault("")
        return mapOf("answer" to "", "sources" to sources(q, 8), "offline" to true)
    }

    fun zimRoute(rest: String): WebResponse {
        // Filled in by the libzim bridge when the reader is available; until then this is an honest 404.
        return WebResponse(404, "text/plain", "This build has no encyclopedia reader.".toByteArray())
    }
}
