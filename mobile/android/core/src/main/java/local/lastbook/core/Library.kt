package local.lastbook.core

import android.database.sqlite.SQLiteDatabase
import java.io.File

/**
 * The LastbookData folder and its read-only databases. The layout is the desktop's: library-data/ and derived/geo/.
 * A library is only used once its catalog is present, so a half-finished install never looks complete.
 */
class Library(val paths: LastbookPaths) {
    @Volatile var root: File? = null
        private set

    /** Call after an install or when the chosen folder changes. */
    fun locate(): Boolean {
        val candidates = listOfNotNull(paths.root, paths.defaultRoot)
        root = candidates.firstOrNull { looksLikeLibrary(it) }
        Catalog.reset()
        return root != null
    }

    val lib: File? get() = root?.resolve("library-data")
    val geo: File? get() = root?.resolve("derived/geo")

    companion object {
        fun looksLikeLibrary(dir: File): Boolean = File(dir, "library-data/catalog.json").isFile
    }

    fun db(rel: String, inGeo: Boolean = false): SQLiteDatabase? {
        val base = if (inGeo) geo else lib ?: return null
        val f = File(base, rel)
        if (!f.isFile) return null
        return runCatching {
            SQLiteDatabase.openDatabase(f.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
        }.getOrNull()
    }

    fun packInfo(): Rec? {
        val f = root?.resolve("pack.json") ?: return null
        return runCatching { org.json.JSONObject(f.readText()).toStringMap() }.getOrNull()
    }

    fun zimFiles(): List<File> {
        val dir = lib?.resolve("collections") ?: return emptyList()
        return dir.listFiles()?.filter { it.isFile && it.name.lowercase().endsWith(".zim") }?.sortedBy { it.name } ?: emptyList()
    }
}

/** Read-only helper that closes a cursor with the database. */
inline fun <T> SQLiteDatabase.queryOne(sql: String, vararg args: String, body: (android.database.Cursor) -> T?): T? {
    rawQuery(sql, args).use { c -> return if (c.moveToFirst()) body(c) else null }
}
