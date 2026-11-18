package local.lastbook.core

import org.json.JSONArray
import org.json.JSONObject

typealias Rec = Map<String, Any?>

fun JSONObject.toStringMap(): Map<String, Any?> {
    val out = LinkedHashMap<String, Any?>()
    for (k in keys()) out[k] = get(k)
    return out
}

fun Any?.toStringMap(): Map<String, Any?>? = when (this) {
    is JSONObject -> toStringMap()
    is Map<*, *> -> entries.associate { it.key.toString() to it.value }
    else -> null
}

fun Any?.recs(): List<Rec> = when (this) {
    is JSONArray -> (0 until length()).mapNotNull { opt(it).toStringMap() }
    is List<*> -> mapNotNull { it.toStringMap() }
    else -> emptyList()
}

fun Any?.strs(): List<String> = when (this) {
    is JSONArray -> (0 until length()).map { optString(it) }
    is List<*> -> map { it.toString() }
    else -> emptyList()
}

fun Rec.s(key: String): String = when (val v = this[key]) {
    null, JSONObject.NULL -> ""
    is String -> v
    else -> v.toString()
}

fun Rec.str(key: String): String? = (this[key] as? String)?.takeIf { it.isNotEmpty() }

fun Rec.d(key: String): Double = when (val v = this[key]) {
    is Number -> v.toDouble()
    is String -> v.toDoubleOrNull() ?: 0.0
    else -> 0.0
}

fun Rec.i(key: String): Int = when (val v = this[key]) {
    is Number -> v.toInt()
    is String -> v.toIntOrNull() ?: 0
    else -> 0
}

fun Rec.l(key: String): Long = when (val v = this[key]) {
    is Number -> v.toLong()
    is String -> v.toLongOrNull() ?: 0L
    else -> 0L
}

fun Rec.truthy(key: String): Boolean = when (val v = this[key]) {
    null, JSONObject.NULL -> false
    is Boolean -> v
    is Number -> v.toDouble() != 0.0
    is String -> v.isNotEmpty()
    is JSONArray -> v.length() > 0
    is Collection<*> -> v.isNotEmpty()
    else -> true
}

fun Rec.obj(key: String): Rec? = this[key].toStringMap()

fun Rec.arr(key: String): List<Rec> = this[key].recs()

fun Rec.array(key: String): List<String> = this[key].strs()

fun jsonObjectOf(vararg pairs: Pair<String, Any?>): JSONObject {
    val o = JSONObject()
    for ((k, v) in pairs) o.put(k, v ?: JSONObject.NULL)
    return o
}
