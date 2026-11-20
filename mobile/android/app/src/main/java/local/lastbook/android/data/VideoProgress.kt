package local.lastbook.android.data

import android.content.Context

/** Where each video was left, on this phone only. */
class VideoProgress(context: Context) {
    private val prefs = context.getSharedPreferences("lastbook.progress", Context.MODE_PRIVATE)

    fun get(id: String): Double = prefs.getFloat(id, 0f).toDouble()
    fun set(id: String, t: Double) { prefs.edit().putFloat(id, t.toFloat()).apply() }
    fun clear(id: String) { prefs.edit().remove(id).apply() }
}
