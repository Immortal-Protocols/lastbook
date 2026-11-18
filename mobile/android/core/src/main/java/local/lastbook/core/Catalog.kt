package local.lastbook.core

import android.content.Context
import org.json.JSONObject
import java.io.File

/** The library catalog (library-data/catalog.json), read once per library, plus the bundled guide topics. */
class Catalog private constructor() {
    @Volatile private var loadedFor: String? = null
    private var byId = emptyMap<String, Rec>()
    private var byPath = emptyMap<String, Rec>()
    private var videoTx = emptyMap<String, Rec>()
    private var thumbs = emptyMap<String, String>()
    private var order = emptyList<Rec>()

    val records: List<Rec> get() = order
    fun get(id: String): Rec? = byId[id]
    fun byPath(path: String): Rec? = byPath[path]
    fun transcriptFor(videoPath: String): Rec? = videoTx[videoPath]
    fun thumbFor(videoPath: String): String? = thumbs[videoPath]

    fun reset() {
        synchronized(this) {
            loadedFor = null
            byId = emptyMap(); byPath = emptyMap(); videoTx = emptyMap(); thumbs = emptyMap(); order = emptyList()
        }
    }

    fun ensure(library: Library) {
        val root = library.root ?: run { reset(); return }
        val lib = File(root, "library-data")
        val key = root.path
        synchronized(this) {
            if (loadedFor == key) return
            val all = runCatching {
                org.json.JSONArray(File(lib, "catalog.json").readText()).let { a ->
                    (0 until a.length()).mapNotNull { a.opt(it).toStringMap() }
                }
            }.getOrElse { emptyList() }

            val excluded = HashSet<String>()
            runCatching {
                val o = JSONObject(File(lib, "video-exclusions.json").readText())
                o.optJSONObject("videos")?.let { v -> for (k in v.keys()) { excluded += k; excluded += "metadata-$k" } }
            }
            val badPaths = all.filter { excluded.contains(it.s("id")) }.map { it.s("path") }.toSet()
            val kept = all.filter { r ->
                !excluded.contains(r.s("id")) && !excluded.contains(r.s("video_id")) &&
                    !(r.str("video_path")?.let { badPaths.contains(it) } ?: false)
            }
            val bi = LinkedHashMap<String, Rec>(); val bp = LinkedHashMap<String, Rec>()
            val tx = LinkedHashMap<String, Rec>(); val th = LinkedHashMap<String, String>()
            for (r in kept) {
                bi[r.s("id")] = r; bp[r.s("path")] = r
                if (r.s("kind") == "transcript") r.str("video_path")?.let { tx[it] = r }
                if (r.s("kind") == "metadata") {
                    val vp = r.str("video_path"); val t = r.str("thumbnail_path")
                    if (vp != null && t != null) th[vp] = t
                }
            }
            byId = bi; byPath = bp; videoTx = tx; thumbs = th; order = kept
            loadedFor = key
        }
    }

    companion object {
        val shared = Catalog()

        fun reset() = shared.reset()

        private val TRUST: List<Triple<Regex, String, Double>> = listOf(
            Triple(Regex("World Health|WHO\\b|ICRC|IFRC|Red Cross|Médecins|MSF|UNICEF|Sphere|St John Ambulance|CAWST"), "International health & humanitarian guidance", 1.5),
            Triple(Regex("Hesperian|Where There Is No|Where Women|Book for Midwives|Community Guide to Environmental|Health Actions|Workers' Guide"), "Hesperian community health guide", 1.45),
            Triple(Regex("FEMA|Ready\\.gov|CDC|Centers for Disease|EPA|Environmental Protection|NOAA|National Weather|USDA|Food Safety|National Park|USGS|Department|Agency|U\\.S\\.|US Army|Army|Navy|Census|NIOSH|OSHA|NASA|FAA|Cal OES|California|County of|City of"), "Government guidance", 1.4),
            Triple(Regex("National Center for Home Food Preservation|Extension|University|UC |College|Agricultural|Food Hero|UWyo"), "University / extension service", 1.35),
            Triple(Regex("MIT|OpenStax|OpenCourseWare|NIST"), "Course or textbook", 1.1),
            Triple(Regex("Kiwix|Wikipedia|Wikibooks|Appropedia|MDWiki"), "Community-written encyclopedia", 1.0),
            Triple(Regex("Coalcracker|Corporals Corner|Canterbury|Primitive Technology|creator-"), "Hobbyist demonstration video", 0.8),
        )

        fun trust(r: Rec): Pair<String, Double> {
            val s = "${r.s("publisher")} ${r.s("collection")} ${r.s("category")}"
            for ((rx, label, w) in TRUST) if (rx.containsMatchIn(s)) return label to w
            if (r.truthy("equipment_class") || r.truthy("model")) return "Manufacturer manual (model-specific)" to 1.05
            return "Reference" to 1.0
        }

        fun kindLabel(r: Rec): String = when (r.s("kind")) {
            "pdf" -> "PDF"; "html" -> "Saved web page"; "video" -> "Video"; "transcript" -> "Transcript"
            "pptx" -> "Slides"; "zim" -> "Encyclopedia"; "metadata" -> "Video details"; else -> r.s("kind")
        }

        fun yearOf(r: Rec): String? {
            for (k in listOf("edition", "publication_date", "upload_date")) {
                Regex("(19|20)\\d\\d").find(r.s(k))?.let { return it.value }
            }
            return Regex("\\b(19[5-9]\\d|20[0-2]\\d)\\b").find(r.s("title"))?.value
        }

        fun cleanTitle(r: Rec): String {
            var t = r.s("title").replace(Regex("^(\\d{3}(\\s\\d+)?)\\s+"), "").replace(Regex("(?i)\\.pdf$"), "")
            if (Regex("[\\w\\-]+").matches(t) && t.contains("_")) t = t.replace("_", " ")
            return t
        }

        fun publicRec(r: Rec?, full: Boolean = false): Rec? {
            r ?: return null
            val trust = trust(r).first
            val out = LinkedHashMap<String, Any?>()
            out["id"] = r.s("id"); out["title"] = cleanTitle(r); out["kind"] = r.s("kind"); out["kindLabel"] = kindLabel(r)
            out["publisher"] = r["publisher"] ?: JSONObject.NULL
            out["collection"] = r["collection"] ?: JSONObject.NULL
            out["path"] = r.s("path")
            out["pages"] = if (r.truthy("pages")) r["pages"] else r["slides"]
            out["duration"] = r["duration"] ?: JSONObject.NULL
            out["year"] = yearOf(r) ?: JSONObject.NULL
            out["trust"] = trust
            out["bytes"] = r["bytes"] ?: JSONObject.NULL
            if (r.s("kind") == "video") {
                out["transcript"] = shared.videoTx[r.s("path")] != null || r.truthy("captions")
                out["thumb"] = shared.thumbs[r.s("path")] ?: JSONObject.NULL
            }
            if (r.s("searchability").startsWith("image-only")) out["imageOnly"] = true
            if (full) {
                for (k in listOf("notes", "edition", "retrieved_at", "source_url", "license", "license_url", "searchability",
                        "upload_date", "publication_date", "model", "course", "level", "caption_type")) if (r.truthy(k)) out[k] = r[k]
                if (r.s("kind") == "transcript") r.str("video_path")?.let { shared.byPath[it]?.let { v -> out["videoId"] = v.s("id") } }
                if (r.s("kind") == "video") shared.videoTx[r.s("path")]?.let { tx ->
                    out["transcriptId"] = tx.s("id"); out["caption_type"] = tx["caption_type"] ?: JSONObject.NULL
                }
            }
            return out
        }

        /** Guide topics from the bundled content/topics directory. */
        fun topics(context: Context): List<Rec> = runCatching {
            val names = context.assets.list("content/topics")?.filter { it.endsWith(".json") }?.sorted() ?: emptyList()
            names.mapNotNull { n ->
                runCatching {
                    context.assets.open("content/topics/$n").bufferedReader().use { it.readText() }
                        .let { JSONObject(it).toStringMap() }
                }.getOrNull()
            }
        }.getOrElse { emptyList() }

        fun gaps(context: Context): Rec = runCatching {
            context.assets.open("content/gaps.json").bufferedReader().use { it.readText() }
                .let { JSONObject(it).toStringMap() }
        }.getOrElse { emptyMap() }
    }
}
