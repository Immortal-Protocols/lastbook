package local.lastbook.core

import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.math.*

/** Place / address / water search, ported from server.py places() and engine/address_search.py. */
class Places(private val map: MapEngine, private val library: Library) {
    private val words = mapOf(
        "boulevard" to "blvd", "avenue" to "ave", "av" to "ave", "street" to "st", "drive" to "dr", "road" to "rd",
        "place" to "pl", "court" to "ct", "lane" to "ln", "terrace" to "ter", "circle" to "cir", "highway" to "hwy",
        "parkway" to "pkwy", "square" to "sq", "north" to "n", "south" to "s", "east" to "e", "west" to "w",
        "mount" to "mt", "saint" to "st",
    )
    private val stateNames = listOf(
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
        "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
        "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "Puerto Rico", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    )
    private val stateCodes = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY".split(" ")
    private val states = stateNames.map { it.lowercase() }.zip(stateCodes).toMap()
    private val waterWords = setOf("lake", "lakes", "reservoir", "res", "dam", "pond", "ponds")

    private fun normalize(text: String): String =
        Regex("[^a-z0-9 ]+").replace(text.lowercase(), " ").split(' ').filter { it.isNotEmpty() }
            .joinToString(" ") { words[it] ?: it }

    private fun wordSets(ws: List<String>): List<List<String>> {
        val out = ArrayList<List<String>>(); out += ws
        if (ws.size > 1) for (i in ws.indices) out += ws.filterIndexed { j, _ -> j != i }
        return out
    }

    private fun nearBonus(near: Pair<Double, Double>?, lat: Double, lon: Double): Double {
        if (near == null) return 0.0
        val km = Geo.haversine(near.first, near.second, lat, lon).first
        return 6 * exp(-km / 60) + 2 * exp(-km / 600)
    }

    fun find(q0: String, near: Pair<Double, Double>?, limit0: Int): ByteArray {
        val q = q0.trim().take(200)
        val limit = limit0.coerceIn(1, 40)
        if (isAddress(q)) return address(q, near, minOf(limit, 8))
        val db = library.db("places.sqlite", true)
        val ws = Regex("\\w+").findAll(q).map { it.value }.toList()
        if (db == null || ws.isEmpty()) return "[]".toByteArray()
        val rows = ArrayList<Array<Any?>>()
        var full = false
        for (set in wordSets(ws)) {
            if (full && set.size < ws.size) break
            if (set.isEmpty()) continue
            val match = set.joinToString(" ") { "\"${it.replace("\"", "")}\"*" }
            runCatching {
                db.rawQuery("SELECT p.name,p.kind,p.detail,p.lat,p.lon,p.rank,p.source FROM place_fts f JOIN place p ON p.id=f.rowid " +
                    "WHERE place_fts MATCH ? ORDER BY p.rank, bm25(place_fts) LIMIT 200", arrayOf(match)).use { c ->
                    while (c.moveToNext()) rows += arrayOf(c.getString(0), c.getString(1), c.getString(2), c.getDouble(3), c.getDouble(4), c.getInt(5), c.getString(6))
                }
            }
            if (set.size == ws.size) full = rows.isNotEmpty()
        }
        val dedup = rows.distinctBy { "${it[0]}|${round(it[3] as Double)}|${round(it[4] as Double)}" }
        val normQ = normalize(q)
        fun norm(s: String) = normalize(s)
        val sorted = dedup.sortedWith(compareBy(
            { norm(it[0] as String) != normQ },
            { !norm(it[0] as String).startsWith(normQ) },
            { -(nearBonus(near, it[3] as Double, it[4] as Double)) },
            { it[5] as Int },
        ))
        val out = JSONArray(); val seen = HashSet<String>()
        for (r in sorted) {
            val key = "${(r[0] as String).lowercase()}|${round((r[3] as Double) * 100)}|${round((r[4] as Double) * 100)}"
            if (!seen.add(key)) continue
            out.put(JSONObject().apply {
                put("name", r[0]); put("kind", r[1]); put("detail", r[2]); put("lat", r[3]); put("lon", r[4])
                put("source", r[6]); put("onMap", true)
            })
            if (out.length() >= limit) break
        }
        val water = waterPlaces(q, near, 10)
        if (water.isNotEmpty()) {
            val merged = JSONArray()
            val all = if (Regex("\\w+").findAll(q).any { it.value.lowercase() in waterWords })
                water + (0 until out.length()).map { out.getJSONObject(it) }
            else (0 until minOf(8, out.length())).map { out.getJSONObject(it) } + water + (8 until out.length()).map { out.getJSONObject(it) }
            for (o in all.take(limit + water.size)) merged.put(o)
            return merged.toString().toByteArray()
        }
        return out.toString().toByteArray()
    }

    private fun waterPlaces(q: String, near: Pair<Double, Double>?, limit: Int): List<JSONObject> {
        val db = map.waterDb() ?: return emptyList()
        val all = Regex("\\w+").findAll(q).map { it.value.lowercase() }.toList()
        val core = all.filter { it !in waterWords }
        if (core.isEmpty()) return emptyList()
        data class W(val score: Double, val o: JSONObject)
        val out = ArrayList<W>()
        val seen = HashSet<String>()
        for (set in wordSets(core)) {
            if (set.isEmpty()) continue
            val match = set.joinToString(" ") { "\"${it.replace("\"", "")}\"*" }
            runCatching {
                db.rawQuery("SELECT r.kind,r.name,r.lat,r.lon,r.detail FROM water_fts f JOIN resource r ON r.id=f.rowid WHERE water_fts MATCH ? LIMIT 6000", arrayOf(match)).use { c ->
                    while (c.moveToNext()) {
                        val kind = c.getString(0); val name = c.getString(1) ?: ""
                        val lat = c.getDouble(2); val lon = c.getDouble(3)
                        val detail = runCatching { JSONObject(c.getString(4) ?: "{}").toStringMap() }.getOrElse { emptyMap() }
                        if (!seen.add("$kind|$name|${round(lat * 100)}|${round(lon * 100)}")) continue
                        val text = (name + " " + detail.s("other_names")).lowercase()
                        val area = detail.d("area_acres").takeIf { it > 0 } ?: detail.d("surface_acres").takeIf { it > 0 } ?: 1.0
                        val score = all.count { text.contains(it) } * 2 + (if (text.contains(core[0])) 1 else 0) +
                            (if (kind != "dam") 1 else 0) + (if (name.equals(q.trim(), true)) 3 else 0) +
                            log10(area + 1) / 3 + nearBonus(near, lat, lon)
                        val where = listOfNotNull(detail.s("county").takeIf { it.isNotEmpty() }?.plus(" County"), detail.s("state").takeIf { it.isNotEmpty() }).joinToString(", ")
                        val extra = detail.s("other_names").takeIf { it.isNotEmpty() }?.let { " · also called $it" } ?: ""
                        val away = near?.let { val km = Geo.haversine(it.first, it.second, lat, lon).first; if (km >= 1.6) " · ${(km / 1.609).roundToInt()} mi away" else " · nearby" } ?: ""
                        val o = JSONObject().apply {
                            put("name", name); put("kind", mapOf("dam" to "Dam", "reservoir" to "Reservoir", "lake" to "Lake")[kind] ?: kind)
                            put("detail", (where.ifEmpty { "United States" }) + extra + away)
                            put("lat", lat); put("lon", lon); put("source", "water"); put("onMap", true)
                        }
                        out += W(score, o)
                    }
                }
            }
            if (out.size >= 6000) break
        }
        return out.sortedByDescending { it.score }.take(limit).map { it.o }
    }

    private fun isAddress(q: String): Boolean = Regex("^\\s*\\d[\\w-]*\\s+\\S").containsMatchIn(q)

    private fun address(q: String, near: Pair<Double, Double>?, limit: Int): ByteArray {
        val parts = q.trim().split(Regex("\\s+"), limit = 2)
        if (parts.size < 2) return "[]".toByteArray()
        val number = parts[0].uppercase()
        var rest = Regex("[^a-z0-9 ]+").replace(parts[1].lowercase(), " ").trim().split(Regex("\\s+")).toMutableList()
        var postcode = ""
        if (rest.isNotEmpty() && Regex("\\d{5}").matches(rest.last())) { postcode = rest.removeAt(rest.size - 1) }
        var state = ""
        for (count in listOf(3, 2, 1)) {
            if (rest.size <= count) continue
            val name = rest.takeLast(count).joinToString(" ")
            val code = states[name] ?: if (count == 1 && name.uppercase() in stateCodes) name.uppercase() else ""
            if (code.isNotEmpty()) { state = code; rest = rest.dropLast(count).toMutableList(); break }
        }
        val normWords = normalize(rest.joinToString(" ")).split(' ').filter { it.isNotEmpty() }
        if (normWords.isEmpty()) return "[]".toByteArray()
        val dir = library.paths.addressesDir
        var paths = dir.listFiles()?.filter { it.name.endsWith(".sqlite") }?.sortedBy { it.name } ?: emptyList()
        if (state.isNotEmpty()) paths = paths.filter { it.nameWithoutExtension.uppercase() == state }
        val dbs = paths.mapNotNull { runCatching { SQLiteDatabase.openDatabase(it.path, null, SQLiteDatabase.OPEN_READONLY) }.getOrNull() }
        if (dbs.isEmpty()) return "[]".toByteArray()
        data class Row(val num: String, val street: String, val city: String, val state: String, val zip: String, val lat: Double, val lon: Double, val norm: String)
        val rows = ArrayList<Row>()
        for (count in normWords.size downTo 1) {
            val street = normWords.take(count).joinToString(" ")
            if (normWords.take(count).all { it in words.values }) continue
            val city = normWords.drop(count).joinToString(" ")
            val conditions = ArrayList<String>(); val params = ArrayList<String>()
            conditions += "num IN (?, ?)"; params += number; params += number.lowercase()
            conditions += "norm >= ?"; params += street
            conditions += "norm < ?"; params += street + '\uffff'
            if (state.isNotEmpty()) { conditions += "state = ?"; params += state }
            if (postcode.isNotEmpty()) { conditions += "zip = ?"; params += postcode }
            if (city.isNotEmpty()) { conditions += "lower(city) LIKE ?"; params += "$city%" }
            val sql = "SELECT num,street,city,state,zip,lat,lon,norm FROM addr WHERE ${conditions.joinToString(" AND ")} ORDER BY length(norm),norm LIMIT ?"
            for (db in dbs) {
                runCatching {
                    db.rawQuery(sql, (params + (limit * 3).toString()).toTypedArray()).use { c ->
                        while (c.moveToNext()) rows += Row(c.getString(0), c.getString(1), c.getString(2), c.getString(3), c.getString(4), c.getDouble(5), c.getDouble(6), c.getString(7))
                    }
                }
            }
            if (rows.isNotEmpty()) break
        }
        val seen = HashSet<String>()
        val out = JSONArray()
        for (r in rows.sortedWith(compareBy({ it.norm.length }, {
            if (near == null) 0.0 else (it.lat - near.first).pow(2) + ((it.lon - near.second) * cos(Math.toRadians(near.first))).pow(2)
        }, { it.state }, { it.city }, { it.street }))) {
            val key = "${r.num}|${r.norm}|${round(r.lat * 100000)}|${round(r.lon * 100000)}"
            if (!seen.add(key)) continue
            out.put(JSONObject().apply {
                put("name", "${r.num} ${r.street}"); put("kind", "Street address")
                put("detail", listOf(r.city, r.state, r.zip).filter { it.isNotEmpty() }.joinToString(", "))
                put("lat", r.lat); put("lon", r.lon); put("source", "Overture Maps"); put("onMap", true)
            })
            if (out.length() >= limit) break
        }
        return out.toString().toByteArray()
    }
}
