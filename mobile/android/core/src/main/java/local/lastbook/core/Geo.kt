package local.lastbook.core

import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

object Geo {
    const val EXT = 512.0

    fun tileBounds(z: Int, x: Int, y: Int): DoubleArray {
        val n = 2.0.pow(z)
        val lon0 = x / n * 360 - 180
        val lon1 = (x + 1) / n * 360 - 180
        val lat0 = Math.toDegrees(atan(sinh(PI * (1 - 2 * (y + 1) / n))))
        val lat1 = Math.toDegrees(atan(sinh(PI * (1 - 2 * y / n))))
        return doubleArrayOf(lon0, lat0, lon1, lat1)
    }

    fun project(lon: Double, lat: Double, z: Int, x: Int, y: Int): Pair<Double, Double> {
        val n = 2.0.pow(z)
        val px = ((lon + 180) / 360 * n - x) * EXT
        val s = sin(Math.toRadians(lat.coerceIn(-85.0, 85.0)))
        val py = ((0.5 - ln((1 + s) / (1 - s)) / (4 * PI)) * n - y) * EXT
        return px to py
    }

    /** Decode the compressed int32 geometry used by feat.geom. */
    fun unpack(blob: ByteArray): List<List<Pair<Double, Double>>> {
        if (blob.size < 4) return emptyList()
        val b = ByteBuffer.wrap(blob).order(ByteOrder.LITTLE_ENDIAN)
        val parts = b.int
        val out = ArrayList<List<Pair<Double, Double>>>(parts)
        repeat(parts) {
            if (b.remaining() < 4) return@repeat
            val n = b.int
            var x = 0; var y = 0
            val pts = ArrayList<Pair<Double, Double>>(n)
            repeat(n) {
                if (b.remaining() < 8) return@repeat
                x += b.int; y += b.int
                pts += (x / 1e6) to (y / 1e6)
            }
            out += pts
        }
        return out
    }

    fun clipRing(pts: List<Pair<Double, Double>>, x0: Double, y0: Double, x1: Double, y1: Double): List<Pair<Double, Double>> {
        var p = pts
        fun clip(src: List<Pair<Double, Double>>, inside: (Pair<Double, Double>) -> Boolean, inter: (Pair<Double, Double>, Pair<Double, Double>) -> Pair<Double, Double>): List<Pair<Double, Double>> {
            val out = ArrayList<Pair<Double, Double>>()
            for (i in src.indices) {
                val a = src[(i - 1 + src.size) % src.size]
                val b = src[i]
                if (inside(b)) {
                    if (!inside(a)) out += inter(a, b)
                    out += b
                } else if (inside(a)) out += inter(a, b)
            }
            return out
        }
        fun ix(xv: Double): (Pair<Double, Double>, Pair<Double, Double>) -> Pair<Double, Double> =
            { a, b -> xv to (a.second + (b.second - a.second) * (xv - a.first) / ((b.first - a.first).takeIf { it != 0.0 } ?: 1e-9)) }
        fun iy(yv: Double): (Pair<Double, Double>, Pair<Double, Double>) -> Pair<Double, Double> =
            { a, b -> (a.first + (b.first - a.first) * (yv - a.second) / ((b.second - a.second).takeIf { it != 0.0 } ?: 1e-9)) to yv }
        p = clip(p, { it.first >= x0 }, ix(x0)); if (p.isEmpty()) return p
        p = clip(p, { it.first <= x1 }, ix(x1)); if (p.isEmpty()) return p
        p = clip(p, { it.second >= y0 }, iy(y0)); if (p.isEmpty()) return p
        p = clip(p, { it.second <= y1 }, iy(y1))
        return p
    }

    fun haversine(la1: Double, lo1: Double, la2: Double, lo2: Double): Pair<Double, String> {
        val r = 6371.0
        val p1 = Math.toRadians(la1); val p2 = Math.toRadians(la2)
        val dp = p2 - p1; val dl = Math.toRadians(lo2 - lo1)
        val a = sin(dp / 2).pow(2) + cos(p1) * cos(p2) * sin(dl / 2).pow(2)
        val d = 2 * r * asin(sqrt(a))
        val b = (Math.toDegrees(atan2(sin(dl) * cos(p2), cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl))) + 360) % 360
        val dirs = arrayOf("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
        return d to dirs[((b + 22.5) / 45).toInt() % 8]
    }

    fun summary(cls: String, detail: Rec): String {
        val keys = mapOf(
            "mineral" to listOf("commod1", "commod2", "dev_stat"), "oil_gas_well" to listOf("WellTypeLabel", "FieldName", "API"),
            "fish_stocking" to listOf("FishType", "Counties"), "boat_launch" to listOf("Water_Body", "Facility_Type"),
            "dam" to listOf("purpose", "river", "county"), "reservoir" to listOf("reservoir_type", "water_type", "state"),
            "orchard" to listOf("crop"), "vineyard" to listOf("crop"), "berries" to listOf("crop"),
            "perennial_veg" to listOf("crop"), "lake" to listOf("water_type", "state"), "pond" to listOf("water_type", "state"),
        )[cls] ?: emptyList()
        val out = ArrayList<String>()
        if (detail.truthy("not_drinking_water")) out += "NOT drinking water"
        if (detail.truthy("area_acres")) out += "${detail.d("area_acres")} acres"
        for (k in keys) if (detail.truthy(k)) out += detail.s(k)
        if (detail.truthy("crop_acres")) out += "about ${detail.d("crop_acres").roundToInt()} acres in this block"
        if (detail.truthy("normal_storage_af")) out += "${detail.d("normal_storage_af").toLong()} acre-ft stored"
        return out.joinToString(" · ")
    }
}

fun Double.roundTo(n: Int): Double = if (!isFinite()) this else Math.round(this * 10.0.pow(n)) / 10.0.pow(n)
