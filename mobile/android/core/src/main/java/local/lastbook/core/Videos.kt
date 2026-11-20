package local.lastbook.core

import android.content.Context
import org.json.JSONObject
import java.io.File

/** Port of the iPad's videos section: home rows, category pages, search, related videos, docs and transcripts. */
class Videos(private val library: Library, private val context: Context) {
    companion object {
        val VROWS: List<Triple<String, String, String>> = listOf(
            Triple("health", "First aid & health", "first-aid medical care-continuity"),
            Triple("water", "Water & sanitation", "water-safety-planning water-treatment rainwater water-sanitation water-sampling sanitary-inspection pumps"),
            Triple("food", "Growing & preserving food", "food-preservation agriculture food-growing seed-saving grain-mill-assembly grain-mill-maintenance grain-mill-operation"),
            Triple("power", "Power, generators & solar", "generator generators offgrid-power"),
            Triple("outdoors", "Shelter, fire & outdoor skills", "field-survival fire-and-shelter knots weather communications-navigation"),
            Triple("repair", "Tools, engines & repair", "small-engine-repair lawn-mower garden-power-equipment snow-blower woodworking welding welding-equipment sharpening workshop milling-layout-and-fit bearing-maintenance seals-installation road-vehicles marine heavy-ag-machinery machining-tool-geometry measurement"),
            Triple("making", "Making things by hand", "craft-manufacturing-including-ceramics-and-textiles glass-manufacturing-processes refractory-installation refractory-process-control typesetting-printing-binding bark-to-amate-paper"),
            Triple("coalcracker", "Coalcracker Bushcraft", "creator-coalcracker-bushcraft"),
            Triple("corporals", "Corporals Corner", "creator-corporals-corner"),
            Triple("canterbury", "Dave Canterbury", "creator-david-canterbury"),
            Triple("primitive", "Primitive Technology", "creator-primitive-technology"),
            Triple("courses", "Courses, lectures & more", ""),
        )
        val VROW_NOTE = mapOf(
            "coalcracker" to "Hobbyist channel", "corporals" to "Hobbyist channel",
            "canterbury" to "Hobbyist channel", "primitive" to "Hobbyist channel — no narration",
            "courses" to "University lectures (MIT and others)",
        )

        fun vrowOf(r: Rec): String {
            val c = r.s("category")
            for ((vid, _, cats) in VROWS) if (cats.split(' ').contains(c)) return vid
            return "courses"
        }
    }

    private fun cat(): Catalog = Catalog.shared.also { it.ensure(library) }

    fun vcard(r: Rec): Rec {
        val p = Catalog.publicRec(r) ?: emptyMap()
        val o = LinkedHashMap<String, Any?>()
        for (k in listOf("id", "title", "publisher", "duration", "thumb", "transcript", "trust", "year")) o[k] = p[k] ?: JSONObject.NULL
        return o
    }

    fun vless(a: Rec, b: Rec): Boolean {
        val c = cat()
        fun key(r: Rec): Key {
            val tx = c.transcriptFor(r.s("path"))
            val th = c.thumbFor(r.s("path"))
            return Key(-Catalog.trust(r).second, if (tx == null && !r.truthy("captions")) 1 else 0, if (th == null) 1 else 0, r.s("title"))
        }
        return key(a) < key(b)
    }
    private data class Key(val trust: Double, val noTx: Int, val noThumb: Int, val title: String) : Comparable<Key> {
        override fun compareTo(other: Key): Int {
            trust.compareTo(other.trust).let { if (it != 0) return it }
            noTx.compareTo(other.noTx).let { if (it != 0) return it }
            noThumb.compareTo(other.noThumb).let { if (it != 0) return it }
            return title.compareTo(other.title)
        }
    }

    fun guideVideos(): List<Rec> {
        val out = ArrayList<Rec>(); val seen = HashSet<String>()
        val zims = library.zimFiles().map { it.name }.toSet()
        fun here(i: Rec): Boolean {
            val z = i.s("zim")
            if (z.isNotEmpty()) { val parts = z.split('/'); return parts.size > 1 && zims.contains(parts[1]) }
            return i.s("doc").isEmpty() || cat().get(i.s("doc")) != null
        }
        for (t in Catalog.topics(context)) {
            val items = ArrayList<Rec>()
            for (c in t.arr("choices")) items += c.arr("read")
            items += t.arr("learn")
            items += t.arr("prepare")
            for (st in t.arr("route")) items += st.arr("read")
            for (i in items) {
                if (!here(i)) continue
                val r = cat().get(i.s("doc")) ?: continue
                if (r.s("kind") != "video" || seen.contains(r.s("id"))) continue
                seen += r.s("id")
                val c = vcard(r).toMutableMap()
                c["guide"] = t.s("id"); c["guideTitle"] = t["title"] ?: JSONObject.NULL
                out += c
            }
        }
        return out
    }

    fun home(): List<Rec> {
        val c = cat()
        val rows = HashMap<String, MutableList<Rec>>()
        for (r in c.records) if (r.s("kind") == "video") rows.getOrPut(vrowOf(r)) { ArrayList() }.add(r)
        val g = guideVideos()
        val res = ArrayList<Rec>()
        res += mapOf(
            "id" to "guides", "title" to "Picked for the guides", "note" to "Chosen to go with the survival guides",
            "count" to g.size, "items" to g.take(10).map { vcard(c.get(it.s("id")) ?: emptyMap()) },
        )
        for ((vid, title, _) in VROWS) {
            var rs = (rows[vid] ?: ArrayList()).sortedWith(Comparator { a, b -> if (vless(a, b)) -1 else if (vless(b, a)) 1 else 0 })
            if ((VROW_NOTE[vid] ?: "").startsWith("Hobbyist")) rs = rs.sortedByDescending { it.s("upload_date") }
            if (rs.isEmpty()) continue
            res += mapOf("id" to vid, "title" to title, "note" to (VROW_NOTE[vid] ?: JSONObject.NULL),
                "count" to rs.size, "items" to rs.take(10).map { vcard(it) })
        }
        return res
    }

    fun list(row: String, q: String = "", length: String = "", sort: String = "", offset: Int = 0, limit: Int = 48): Rec {
        val c = cat()
        var rs: List<Rec> = if (row == "guides") guideVideos().mapNotNull { c.get(it.s("id")) }
        else c.records.filter { it.s("kind") == "video" && (row.isEmpty() || row == "all" || vrowOf(it) == row) }
        if (q.isNotBlank()) {
            val words = q.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
            rs = rs.filter { r -> val t = (r.s("title") + " " + r.s("publisher")).lowercase(); words.all { t.contains(it) } }
        }
        when (length) {
            "short" -> rs = rs.filter { it.d("duration") > 0 && it.d("duration") < 600 }
            "medium" -> rs = rs.filter { it.d("duration") in 600.0..<1800.0 }
            "long" -> rs = rs.filter { it.d("duration") >= 1800 }
        }
        rs = when (sort) {
            "short" -> rs.sortedBy { it.d("duration") }
            "new" -> rs.sortedByDescending { it.s("upload_date") }
            "az" -> rs.sortedBy { it.s("title").lowercase() }
            else -> if (row != "guides") rs.sortedWith(Comparator { a, b -> if (vless(a, b)) -1 else if (vless(b, a)) 1 else 0 }) else rs
        }
        val title = VROWS.firstOrNull { it.first == row }?.second ?: if (row == "guides") "Picked for the guides" else "All videos"
        val page = rs.drop(offset).take(limit)
        return mapOf(
            "title" to title, "note" to (VROW_NOTE[row] ?: JSONObject.NULL), "total" to rs.size,
            "items" to page.map { vcard(it) }, "more" to (rs.size > offset + limit),
        )
    }

    fun related(vid: String, limit: Int = 12): List<Rec> {
        val c = cat()
        val v = c.get(vid) ?: return emptyList()
        val row = vrowOf(v)
        val vids = c.records.filter { it.s("kind") == "video" && it.s("id") != vid }
        val samePub = vids.filter { it.s("publisher") == v.s("publisher") }
        val sameRow = vids.filter { vrowOf(it) == row && it.s("publisher") != v.s("publisher") }
        val words = Regex("[a-z]{4,}").findAll(v.s("title").lowercase()).map { it.value }.toSet()
        fun score(r: Rec): Int = -words.intersect(Regex("[a-z]{4,}").findAll(r.s("title").lowercase()).map { it.value }.toSet()).size
        val a = sameRow.sortedWith { x, y -> if (score(x) != score(y)) score(x).compareTo(score(y)) else if (vless(x, y)) -1 else 1 }.take(limit / 2)
        val b = samePub.sortedWith { x, y -> if (score(x) != score(y)) score(x).compareTo(score(y)) else x.s("title").compareTo(y.s("title")) }.take(limit)
        return (a + b).distinctBy { it.s("id") }.take(limit).map { vcard(it) }
    }

    fun doc(id: String): Rec? = Catalog.publicRec(cat().get(id), full = true)

    fun file(rel: String): File? = library.lib?.resolve(rel)?.takeIf { it.isFile }

    fun thumbFile(rel: String?): File? = rel?.let { file(it) }

    fun transcript(id: String): Rec? {
        val c = cat()
        val video = c.get(id) ?: return null
        val tx = c.transcriptFor(video.s("path"))
        val vtts = ArrayList<String>()
        tx?.str("vtt_path")?.let { vtts += it }
        vtts += video.array("captions").filter { it.endsWith(".vtt") }
        for (p in vtts) {
            val f = file(p) ?: continue
            return mapOf("source" to (tx?.s("caption_type")?.takeIf { it.isNotEmpty() } ?: "captions"),
                "notes" to (tx?.str("notes") ?: JSONObject.NULL), "cues" to parseVtt(f.readText()))
        }
        if (tx != null) {
            val f = file(tx.s("path"))
            if (f != null) {
                val cues = f.readText().split(Regex("\\n\\s*\\n")).filter { it.isNotBlank() }
                    .map { mapOf("t" to JSONObject.NULL, "text" to it.trim()) }
                return mapOf("source" to (tx.s("caption_type").takeIf { it.isNotEmpty() } ?: "transcript"),
                    "notes" to (tx.str("notes") ?: JSONObject.NULL), "cues" to cues)
            }
        }
        return mapOf("source" to JSONObject.NULL, "cues" to emptyList<Any>())
    }

    private fun parseVtt(text: String): List<Rec> {
        val out = ArrayList<Rec>()
        val lines = text.replace("\r\n", "\n").split('\n')
        var i = 0
        val timeRx = Regex("^(\\d{2}):(\\d{2}):(\\d{2})[.,](\\d{3})\\s*-->")
        while (i < lines.size) {
            val m = timeRx.find(lines[i].trim())
            if (m == null) { i++; continue }
            val t = m.groupValues[1].toInt() * 3600 + m.groupValues[2].toInt() * 60 + m.groupValues[3].toInt() + m.groupValues[4].toInt() / 1000.0
            i++
            val body = StringBuilder()
            while (i < lines.size && lines[i].isNotBlank() && !timeRx.containsMatchIn(lines[i])) {
                body.append(lines[i]).append(' ')
                i++
            }
            val clean = body.toString()
                .replace(Regex("<\\d{2}:\\d{2}:\\d{2}[.,]\\d{3}>"), "")
                .replace(Regex("</?c[^>]*>"), "")
                .replace(Regex("<[^>]+>"), " ")
                .replace(Regex("\\s+"), " ").trim()
            if (clean.isNotEmpty()) out += mapOf("t" to t, "text" to clean)
        }
        return out
    }
}
