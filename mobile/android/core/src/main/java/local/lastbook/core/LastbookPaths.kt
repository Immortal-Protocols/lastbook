package local.lastbook.core

import android.content.Context
import java.io.File

/**
 * Where the library, downloads and settings live. The default is app-specific external storage, which needs no
 * permission and keeps atomic renames on one volume. A person may choose another folder; that choice is remembered
 * in settings.json in the app's internal files directory.
 */
class LastbookPaths(private val context: Context) {
    val settingsDir: File = File(context.filesDir, "settings").apply { mkdirs() }
    private val settingsFile = File(settingsDir, "library-path.txt")

    val defaultRoot: File
        get() = File(context.getExternalFilesDir(null) ?: context.filesDir, "LastbookData")

    var root: File
        get() = settingsFile.takeIf { it.isFile }?.readText()?.trim()?.takeIf { it.isNotEmpty() }?.let(::File) ?: defaultRoot
        set(value) {
            settingsFile.parentFile?.mkdirs()
            settingsFile.writeText(value.absolutePath)
        }

    /** Work in progress, beside the target folder, as the desktop uses LastbookData.setup. */
    fun workDir(root: File = this.root): File = File(root.parentFile ?: context.filesDir, "${root.name}.setup")

    val libraryDir: File get() = File(root, "library-data")
    val modelsDir: File get() = File(root, "models")
    val geoDir: File get() = File(root, "derived/geo")
    val addressesDir: File get() = File(geoDir, "addresses")
    val installCatalogFile: File get() = File(settingsDir, "install-catalog.json")
    val installJobFile: File get() = File(settingsDir, "install-job.json")
}
