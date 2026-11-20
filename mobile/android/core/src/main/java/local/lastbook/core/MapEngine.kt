package local.lastbook.core

import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.math.*

/**
 * The offline map: vector tiles, clustered pins, nearest help, resource records, terrain/crop/aerial images and place
 * search. Ported from server.py's map section and the iPad's MapAPI; the web UI in web/map.js is reused unchanged.
 */
class MapEngine(private val library: Library) {
    companion object {
        val HELP = mapOf(
            "hospital" to "Hospital", "clinic" to "Clinic", "doctors" to "Doctor", "pharmacy" to "Pharmacy", "chemist" to "Pharmacy",
            "dentist" to "Dentist", "fire_station" to "Fire station", "police" to "Police", "drinking_water" to "Drinking water tap",
            "fountain" to "Fountain (not necessarily drinkable)", "water_tower" to "Water tower", "water_works" to "Water works",
            "spring" to "Spring (untested)", "toilet" to "Public toilet", "shelter" to "Shelter (structure)",
            "community_centre" to "Community centre", "town_hall" to "Town hall", "school" to "School", "library" to "Library",
            "supermarket" to "Supermarket", "convenience" to "Convenience store", "doityourself" to "Hardware / DIY store",
            "hardware" to "Hardware store", "garden_centre" to "Garden centre", "post_office" to "Post office",
            "camp_site" to "Campsite", "veterinary" to "Vet", "nursing_home" to "Care home", "fuel" to "Fuel station",
            "car_repair" to "Car repair", "bicycle_shop" to "Bicycle shop", "wastewater_plant" to "Wastewater plant",
            "comms_tower" to "Communications tower", "park" to "Park", "courthouse" to "Courthouse",
            "college" to "College", "university" to "University", "kindergarten" to "Kindergarten", "beach" to "Beach",
            "embassy" to "Embassy", "mineral" to "Recorded mineral / mine", "oil_gas_well" to "Recorded oil / gas well",
            "boat_launch" to "Boating facility", "fish_stocking" to "Fish-stocking record",
            "dam" to "Dam (National Inventory of Dams)", "reservoir" to "Reservoir", "lake" to "Lake or pond", "pond" to "Pond",
            "orchard" to "Orchard", "vineyard" to "Vineyard", "berries" to "Berry field", "perennial_veg" to "Asparagus field",
            "city" to "City", "town" to "Town", "village" to "Village", "hamlet" to "Hamlet",
        )
        val CROP_KINDS = setOf("orchard", "vineyard", "berries", "perennial_veg")
        val RESOURCE_KINDS = setOf("mineral", "oil_gas_well", "boat_launch", "fish_stocking", "dam", "reservoir", "lake", "pond") + CROP_KINDS
    }

    fun mapDb(): SQLiteDatabase? = library.db("map.sqlite", true)
    fun nationalDb(): SQLiteDatabase? = library.db("national.sqlite", true)
    fun waterDb(): SQLiteDatabase? = library.db("water.sqlite", true)
    fun cropDb(): SQLiteDatabase? = library.db("crops.sqlite", true)
    fun terrainDb(): SQLiteDatabase? = library.db("terrain.sqlite", true)
    fun buildingDb(): SQLiteDatabase? = library.db("buildings.sqlite", true)
    fun atlasDb(): SQLiteDatabase? = library.db("geography/resources/atlas.sqlite", true)

    private fun resourceDbs(kinds: Set<String>): List<SQLiteDatabase> {
        val out = ArrayList<SQLiteDatabase>()
        if ((kinds - setOf("dam", "reservoir", "lake", "pond") - CROP_KINDS).isNotEmpty()) atlasDb()?.let { out += it }
        if (kinds.any { it in setOf("dam", "reservoir", "lake", "pond") }) waterDb()?.let { out += it }
        if (kinds.any { it in CROP_KINDS }) cropDb()?.let { out += it }
        return out
    }

    // ---------------------------------------------------------------- tiles ----
    fun tile(z: Int, x: Int, y: Int): ByteArray {
        val (lon0, lat0, lon1, lat1) = Geo.tileBounds(z, x, y).let { Quad(it[0], it[1], it[2], it[3]) }.destructure()
        val pad = (lon1 - lon0) * 0.04
        val features = ArrayList<Feature>()
        fun load(db: SQLiteDatabase?, sqlSuffix: String = "") {
            db ?: return
            val sql = "SELECT f.layer,f.cls,f.name,f.geom FROM feat_idx i JOIN feat f ON f.id=i.id " +
                "WHERE i.maxx>=? AND i.minx<=? AND i.maxy>=? AND i.miny<=? AND i.minz<=? ORDER BY f.id"
            runCatching {
                db.rawQuery(sql, arrayOf((lon0 - pad).toString(), (lon1 + pad).toString(), (lat0 - pad).toString(), (lat1 + pad).toString(), z.toString())).use { c ->
                    while (c.moveToNext()) features += Feature(c.getString(0) ?: "", c.getString(1) ?: "", c.getString(2) ?: "", c.getBlob(3))
                }
            }
        }
        load(mapDb())
        if (z >= 11) load(nationalDb())
        load(waterDb())

        val layers = LinkedHashMap<String, MutableList<Any?>>()
        val tol = if (z <= 6) 2.0 else if (z <= 9) 1.2 else if (z < 15) 0.7 else 0.4
        for (f in features) {
            if (f.layer == "bldg" && z < 15) continue
            val polygon = f.layer in setOf("water", "wet", "land", "beach", "bldg", "ocean", "island")
            val geo = ArrayList<Any?>()
            for (part in Geo.unpack(f.geom)) {
                var pts = part.map { (lo, la) -> Geo.project(lo, la, z, x, y) }
                if (polygon && pts.size > 200) pts = Geo.clipRing(pts, -16.0, -16.0, Geo.EXT + 16, Geo.EXT + 16)
                val q = ArrayList<Double>(); var last: Pair<Double, Double>? = null
                for (p in pts) {
                    if (last == null || abs(p.first - last.first) > tol || abs(p.second - last.second) > tol) {
                        q.add(round(p.first * 10) / 10); q.add(round(p.second * 10) / 10); last = p
                    }
                }
                if (polygon && q.size < 6) continue
                if (!polygon && f.layer != "place" && q.size < 4 && z < 12) continue
                if (f.layer == "place") { q.clear(); pts.firstOrNull()?.let { q.add(round(it.first * 10) / 10); q.add(round(it.second * 10) / 10) } }
                if (q.isNotEmpty()) geo.add(q)
            }
            if (geo.isNotEmpty()) {
                val arr = layers.getOrPut(f.layer) { ArrayList() }
                arr.add(listOf(f.cls, f.name, geo))
            }
        }
        val o = JSONObject()
        o.put("z", z); o.put("layers", JSONObject(layers.mapValues { JSONArray(it.value) }))
        return o.toString().toByteArray()
    }

    private data class Quad(val lon0: Double, val lat0: Double, val lon1: Double, val lat1: Double) {
        fun destructure() = DoubleArray(4).also { it[0] = lon0; it[1] = lat0; it[2] = lon1; it[3] = lat1 }
    }
    private data class Feature(val layer: String, val cls: String, val name: String, val geom: ByteArray)

    // ---------------------------------------------------------------- pins ----
    fun pins(west0: Double, south0: Double, east0: Double, north0: Double, zoom0: Int, kinds: Set<String>): ByteArray {
        val zoom = zoom0.coerceIn(3, 18)
        var cx = 360.0 / 2.0.pow(zoom) * (if (zoom <= 5) 72 else if (zoom <= 8) 58 else 46) / 256.0
        var cy = cx * max(0.2, cos(Math.toRadians((south0 + north0) / 2)))
        var west = west0; var south = south0; var east = east0; var north = north0
        if (zoom >= 17) { cx = 1e-6; cy = 1e-6 }
        else {
            cy = round(cy / cx * 8) / 8 * cx
            west = floor((west + 180) / cx) * cx - 180; east = ceil((east + 180) / cx) * cx - 180
            south = floor((south + 90) / cy) * cy - 90; north = ceil((north + 90) / cy) * cy - 90
        }
        west = west.coerceAtLeast(-180.0); south = south.coerceAtLeast(-85.0)
        east = east.coerceAtMost(180.0); north = north.coerceAtMost(85.0)

        val services = kinds.filter { it in HELP && it !in RESOURCE_KINDS }
        val resources = kinds.filter { it in RESOURCE_KINDS }
        val cells = LinkedHashMap<Long, Cell>()

        fun add(kind: String, n: Int, sites: Int, lat: Double, lon: Double, x0: Double, x1: Double, y0: Double, y1: Double,
                name: String, detail: Rec, source: String) {
            val key = (floor((lon + 180) / cx).toLong() * 100000L + floor((lat + 90) / cy).toLong())
            val c = cells.getOrPut(key) { Cell() }
            c.lat += lat * sites; c.lon += lon * sites
            c.count += sites; c.records += n
            c.kinds[kind] = (c.kinds[kind] ?: 0) + sites
            c.bbox = doubleArrayOf(min(c.bbox[0], x0), min(c.bbox[1], y0), max(c.bbox[2], x1), max(c.bbox[3], y1))
            if (c.cls.isEmpty()) c.cls = kind
            if (c.name.isEmpty()) c.name = name
            if (c.detail.isEmpty()) c.detail = detail
            if (c.source.isEmpty()) c.source = source
        }

        if (services.isNotEmpty()) {
            val q = services.joinToString(",") { "?" }
            val args = (services + listOf(west.toString(), east.toString(), south.toString(), north.toString(), cx.toString(), cy.toString())).toTypedArray()
            for (db in listOfNotNull(mapDb(), nationalDb())) {
                runCatching {
                    db.rawQuery("SELECT cls,COUNT(*),AVG(lat),AVG(lon),MIN(lon),MAX(lon),MIN(lat),MAX(lat),MIN(name) FROM poi " +
                        "WHERE cls IN ($q) AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ? " +
                        "GROUP BY cls, CAST((lon+180)/? AS INT), CAST((lat+90)/? AS INT)", args).use { c ->
                        while (c.moveToNext()) add(c.getString(0), c.getInt(1), c.getInt(1), c.getDouble(2), c.getDouble(3),
                            c.getDouble(4), c.getDouble(5), c.getDouble(6), c.getDouble(7), c.getString(8) ?: "", emptyMap(), "")
                    }
                }
            }
        }
        if (resources.isNotEmpty()) {
            val q = resources.joinToString(",") { "?" }
            for (db in resourceDbs(resources.toSet())) {
                val g = if (db === cropDb() && cx > 1e-5) 3 else 1
                val args = (listOf(west.toString(), east.toString(), south.toString(), north.toString()) + resources +
                    listOf((cx * g).toString(), (cy * g).toString())).toTypedArray()
                runCatching {
                    db.rawQuery("SELECT r.kind,COUNT(*),AVG(r.lat),AVG(r.lon),MIN(r.lon),MAX(r.lon),MIN(r.lat),MAX(r.lat),r.name,r.detail,r.source,COUNT(DISTINCT r.source_id) " +
                        "FROM spatial s CROSS JOIN resource r ON r.id=s.id WHERE s.minx>=? AND s.maxx<=? AND s.miny>=? AND s.maxy<=? " +
                        "AND r.kind IN ($q) GROUP BY r.kind, CAST((r.lon+180)/? AS INT), CAST((r.lat+90)/? AS INT)", args).use { c ->
                        while (c.moveToNext()) {
                            val detail = runCatching { c.getString(9)?.let { JSONObject(it).toStringMap() } ?: emptyMap() }.getOrElse { emptyMap() }
                            val sites = c.getInt(11).coerceAtLeast(1)
                            add(c.getString(0), c.getInt(1), sites, c.getDouble(2), c.getDouble(3), c.getDouble(4), c.getDouble(5),
                                c.getDouble(6), c.getDouble(7), if (sites == 1) c.getString(8) ?: "" else "", if (sites == 1) detail else emptyMap(), c.getString(10) ?: "")
                        }
                    }
                }
            }
        }

        val points = JSONArray()
        var total = 0
        for (c in cells.values) {
            c.lat /= c.count; c.lon /= c.count
            total += c.count
            val o = JSONObject()
            val single = c.count == 1
            val cls = if (single) c.cls else c.kinds.maxByOrNull { it.value }?.key ?: c.cls
            o.put("cls", cls); o.put("lat", c.lat); o.put("lon", c.lon); o.put("count", c.count); o.put("records", c.records)
            o.put("bbox", JSONArray(c.bbox.toList())); o.put("kinds", JSONObject(c.kinds))
            o.put("label", HELP[cls] ?: cls)
            o.put("spot", c.count > 1 && c.bbox[2] - c.bbox[0] < 1e-4 && c.bbox[3] - c.bbox[1] < 1e-4)
            if (single) {
                o.put("name", c.name); o.put("detail", JSONObject(c.detail)); o.put("source", c.source)
                o.put("summary", Geo.summary(cls, c.detail))
            } else {
                o.put("name", c.name); o.put("detail", JSONObject()); o.put("source", "")
                o.put("summary", "")
            }
            points.put(o)
        }
        val out = JSONObject()
        out.put("points", points); out.put("sites", total); out.put("truncated", cells.size > 2500)
        out.put("cell", JSONArray(listOf(cx, cy)))
        return out.toString().toByteArray()
    }

    private class Cell {
        val kinds = LinkedHashMap<String, Int>()
        var count = 0; var records = 0; var lat = 0.0; var lon = 0.0
        var bbox = doubleArrayOf(Double.MAX_VALUE, Double.MAX_VALUE, -Double.MAX_VALUE, -Double.MAX_VALUE)
        var cls = ""; var name = ""; var detail: Rec = emptyMap(); var source = ""
    }

    // ---------------------------------------------------------------- near ----
    fun near(lat: Double, lon: Double, classes: List<String>, limit0: Int = 8): ByteArray {
        val limit = limit0.coerceIn(1, 50)
        data class P(val cls: String, val label: String, val name: String, val lat: Double, val lon: Double, val km: Double, val dir: String, val summary: String, val source: String)
        val out = ArrayList<P>()
        for (cls in classes) {
            if (cls in RESOURCE_KINDS) {
                val db = resourceDbs(setOf(cls)).firstOrNull() ?: continue
                var radius = 0.15
                while (radius <= 19.2) {
                    val rows = ArrayList<Array<Any?>>()
                    runCatching {
                        db.rawQuery("SELECT r.name,r.lat,r.lon,r.detail,r.source FROM spatial s CROSS JOIN resource r ON r.id=s.id " +
                            "WHERE r.kind=? AND s.minx>=? AND s.maxx<=? AND s.miny>=? AND s.maxy<=?",
                            arrayOf(cls, (lon - radius).toString(), (lon + radius).toString(), (lat - radius).toString(), (lat + radius).toString())).use { c ->
                            while (c.moveToNext()) rows += arrayOf(c.getString(0), c.getDouble(1), c.getDouble(2), c.getString(3), c.getString(4))
                        }
                    }
                    if (rows.size >= limit) {
                        // Pick by distance before truncating: the SQL has no ORDER BY, so the rows arrive in arbitrary order.
                        val nearest = rows.sortedBy { r ->
                            Geo.haversine(lat, lon, r[1] as Double, r[2] as Double).first
                        }
                        for (r in nearest.take(limit)) {
                            val (d, b) = Geo.haversine(lat, lon, r[1] as Double, r[2] as Double)
                            val detail = runCatching { JSONObject(r[3] as String).toStringMap() }.getOrElse { emptyMap() }
                            out += P(cls, HELP[cls] ?: cls, r[0] as String, r[1] as Double, r[2] as Double, round(d * 100) / 100, b, Geo.summary(cls, detail), r[4] as String)
                        }
                        break
                    }
                    radius *= 2
                }
                continue
            }
            var d = 0.02
            var rows: List<Array<Any?>> = emptyList()
            while (d < 1.5 && rows.size < limit) {
                val found = ArrayList<Array<Any?>>()
                for (db in listOfNotNull(mapDb(), nationalDb())) {
                    runCatching {
                        db.rawQuery("SELECT cls,name,lon,lat FROM poi WHERE cls=? AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?",
                            arrayOf(cls, (lon - d).toString(), (lon + d).toString(), (lat - d).toString(), (lat + d).toString())).use { c ->
                            while (c.moveToNext()) found += arrayOf(c.getString(0), c.getString(1), c.getDouble(2), c.getDouble(3))
                        }
                    }
                }
                rows = found.distinctBy { "${it[0]}|${it[1]}|${(it[2] as Double).roundTo(5)}|${(it[3] as Double).roundTo(5)}" }
                d *= 2
            }
            for (r in rows) {
                val (km, brg) = Geo.haversine(lat, lon, r[3] as Double, r[2] as Double)
                out += P(cls, HELP[cls] ?: cls, r[1] as String, r[3] as Double, r[2] as Double, round(km * 100) / 100, brg, "", "")
            }
        }
        val sorted = out.sortedBy { it.km }
        val per = HashMap<String, Int>(); val res = ArrayList<P>()
        for (p in sorted) { val n = per[p.cls] ?: 0; if (n < limit) { per[p.cls] = n + 1; res += p } }
        val arr = JSONArray()
        for (p in res) arr.put(JSONObject().apply {
            put("cls", p.cls); put("label", p.label); put("name", p.name); put("lat", p.lat); put("lon", p.lon)
            put("km", p.km); put("dir", p.dir); put("detail", p.summary); put("source", p.source)
        })
        return arr.toString().toByteArray()
    }

    // ---------------------------------------------------------------- members ----
    fun members(west: Double, south: Double, east: Double, north: Double, kinds: Set<String>, lat: Double, lon: Double, limit: Int = 60): ByteArray {
        val rows = ArrayList<Rec>()
        val services = kinds.filter { it in HELP && it !in RESOURCE_KINDS }
        val resources = kinds.filter { it in RESOURCE_KINDS }
        if (services.isNotEmpty()) {
            val q = services.joinToString(",") { "?" }
            for (db in listOfNotNull(mapDb(), nationalDb())) {
                runCatching {
                    db.rawQuery("SELECT cls,name,lon,lat FROM poi WHERE cls IN ($q) AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?",
                        (services + listOf(west.toString(), east.toString(), south.toString(), north.toString())).toTypedArray()).use { c ->
                        while (c.moveToNext()) rows += mapOf("cls" to c.getString(0), "label" to (HELP[c.getString(0)] ?: c.getString(0)),
                            "name" to (c.getString(1) ?: ""), "lon" to c.getDouble(2), "lat" to c.getDouble(3), "summary" to "", "source" to "")
                    }
                }
            }
        }
        if (resources.isNotEmpty()) {
            val q = resources.joinToString(",") { "?" }
            for (db in resourceDbs(resources.toSet())) {
                runCatching {
                    db.rawQuery("SELECT r.kind,r.name,r.lat,r.lon,r.detail,r.source FROM spatial s CROSS JOIN resource r ON r.id=s.id " +
                        "WHERE s.minx>=? AND s.maxx<=? AND s.miny>=? AND s.maxy<=? AND r.kind IN ($q) LIMIT 500",
                        (listOf(west.toString(), east.toString(), south.toString(), north.toString()) + resources).toTypedArray()).use { c ->
                        while (c.moveToNext()) {
                            val detail = runCatching { JSONObject(c.getString(4) ?: "{}").toStringMap() }.getOrElse { emptyMap() }
                            rows += mapOf("cls" to c.getString(0), "label" to (HELP[c.getString(0)] ?: c.getString(0)), "name" to (c.getString(1) ?: ""),
                                "lat" to c.getDouble(2), "lon" to c.getDouble(3), "summary" to Geo.summary(c.getString(0), detail), "source" to (c.getString(5) ?: ""))
                        }
                    }
                }
            }
        }
        val withDist = rows.map { r ->
            val (d, b) = Geo.haversine(lat, lon, r.d("lat"), r.d("lon"))
            r + mapOf("km" to round(d * 100) / 100, "dir" to b)
        }.sortedBy { it.d("km") }.take(limit)
        return JSONArray(withDist).toString().toByteArray()
    }

    fun resources(west: Double, south: Double, east: Double, north: Double, zoom: Int, kinds: List<String>): ByteArray {
        val db = atlasDb() ?: return JSONObject().put("points", JSONArray()).put("records", 0).toString().toByteArray()
        val ks = kinds.filter { it in RESOURCE_KINDS }
        if (ks.isEmpty()) return JSONObject().put("points", JSONArray()).put("records", 0).toString().toByteArray()
        val cell = 180.0 / 2.0.pow(zoom.coerceIn(3, 18))
        val q = ks.joinToString(",") { "?" }
        val out = JSONArray(); var records = 0
        runCatching {
            db.rawQuery("SELECT r.kind,AVG(r.lat),AVG(r.lon),COUNT(*),r.name,r.detail,r.source,COUNT(DISTINCT r.source_id) FROM spatial s " +
                "CROSS JOIN resource r ON r.id=s.id WHERE s.minx>=? AND s.maxx<=? AND s.miny>=? AND s.maxy<=? AND r.kind IN ($q) " +
                "GROUP BY r.kind, CAST((r.lon+180)/? AS INT), CAST((r.lat+90)/? AS INT) ORDER BY COUNT(*) DESC LIMIT 2001",
                (listOf(west.toString(), east.toString(), south.toString(), north.toString()) + ks + listOf(cell.toString(), cell.toString())).toTypedArray()).use { c ->
                while (c.moveToNext() && out.length() < 2000) {
                    val n = c.getInt(3); records += n
                    out.put(JSONObject().apply {
                        put("cls", c.getString(0)); put("lat", c.getDouble(1)); put("lon", c.getDouble(2)); put("count", n)
                        put("record_count", n); put("name", if (n == 1) c.getString(4) else "$n locations")
                        put("label", HELP[c.getString(0)] ?: c.getString(0))
                        put("detail", runCatching { JSONObject(c.getString(5) ?: "{}") }.getOrElse { JSONObject() })
                        put("source", c.getString(6) ?: "")
                    })
                }
            }
        }
        return JSONObject().put("points", out).put("records", records).toString().toByteArray()
    }

    // ---------------------------------------------------------------- images ----
    fun blobTile(db: SQLiteDatabase?, table: String, column: String, z: Int, x: Int, y: Int): ByteArray? {
        db ?: return null
        return runCatching {
            db.rawQuery("SELECT $column FROM $table WHERE z=? AND x=? AND y=?", arrayOf(z.toString(), x.toString(), y.toString())).use { c ->
                if (c.moveToFirst()) c.getBlob(0) else null
            }
        }.getOrNull()
    }

    fun terrainTile(z: Int, x: Int, y: Int): ByteArray? = blobTile(terrainDb(), "tile", "png", z, x, y)
    fun cropTile(z: Int, x: Int, y: Int): ByteArray? = blobTile(cropDb(), "tile", "png", z, x, y)
    fun aerialTile(z: Int, x: Int, y: Int): ByteArray? = blobTile(library.db("aerial.sqlite", true), "tile", "jpg", z, x, y)

    // ---------------------------------------------------------------- contents ----
    fun mapContents(): Rec {
        val kinds = LinkedHashSet<String>()
        fun distinct(db: SQLiteDatabase?, table: String, col: String) {
            db ?: return
            runCatching { db.rawQuery("SELECT DISTINCT $col FROM $table", null).use { c -> while (c.moveToNext()) c.getString(0)?.let { kinds += it } } }
        }
        distinct(waterDb(), "resource", "kind"); distinct(cropDb(), "resource", "kind")
        distinct(mapDb(), "poi", "cls"); distinct(nationalDb(), "poi", "cls")
        distinct(atlasDb(), "resource", "kind")
        return mapOf("layers" to kinds.sorted(), "bounds" to JSONObject.NULL, "detail" to true, "contours" to (terrainDb() != null))
    }

    fun homeCenter(): Pair<Double, Double> {
        var west = Double.MAX_VALUE; var south = Double.MAX_VALUE; var east = -Double.MAX_VALUE; var north = -Double.MAX_VALUE
        for (db in listOfNotNull(mapDb(), nationalDb())) {
            runCatching {
                db.rawQuery("SELECT MIN(lon),MIN(lat),MAX(lon),MAX(lat) FROM poi", null).use { c ->
                    if (c.moveToFirst() && !c.isNull(0)) {
                        west = min(west, c.getDouble(0)); south = min(south, c.getDouble(1))
                        east = max(east, c.getDouble(2)); north = max(north, c.getDouble(3))
                    }
                }
            }
        }
        if (west == Double.MAX_VALUE) return 39.0 to -98.0
        return ((south + north) / 2) to ((west + east) / 2)
    }

    fun info(): ByteArray {
        val o = JSONObject()
        val layers = (mapContents()["layers"] as? List<*>)?.filterIsInstance<String>() ?: emptyList()
        o.put("aerial", library.db("aerial.sqlite", true) != null)
        o.put("layers", JSONArray(layers))
        o.put("national", if (nationalDb() != null) "complete" else "missing")
        o.put("detail", true)
        o.put("contours", terrainDb() != null)
        o.put("terrain_detail", JSONObject.NULL)
        o.put("terrain_circle", JSONObject.NULL)
        o.put("aerial_detail", JSONObject.NULL)
        o.put("version", System.currentTimeMillis() / 60000)
        return o.toString().toByteArray()
    }

    fun places(q: String, near: Pair<Double, Double>?, limit: Int = 20): ByteArray = Places(this, library).find(q, near, limit)
}
