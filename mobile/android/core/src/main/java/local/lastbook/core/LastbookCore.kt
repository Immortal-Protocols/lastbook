package local.lastbook.core

import android.content.Context
import local.lastbook.core.install.InstallCatalog
import local.lastbook.core.install.InstallEngine

/**
 * The one process-wide entry point to the Lastbook engine: paths, the library, the installer and the local AI.
 * Android uses this directly; the WebView map/reader uses [WebRoutes] with the same engine.
 */
object LastbookCore {
    @Volatile private var appContext: Context? = null

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    val context: Context
        get() = appContext ?: error("LastbookCore.init was not called")

    val paths: LastbookPaths by lazy { LastbookPaths(context) }
    val library: Library by lazy { Library(paths).also { it.locate() } }
    val catalog: Catalog get() = Catalog.shared
    val videos: Videos by lazy { Videos(library, context) }
    val map: MapEngine by lazy { MapEngine(library) }
    val chat: ChatEngine by lazy { ChatEngine(context, library, videos, Catalog.shared, paths) }
    val installCatalog: InstallCatalog by lazy { InstallCatalog.load(context) }
    val installer: InstallEngine by lazy { InstallEngine(context, paths, library, installCatalog) }
    val zim: ZimReader by lazy { ZimReader(context, library) }
    val web: WebRoutes by lazy { WebRoutes(context, library, videos, map, chat, zim) }

    fun reloadLibrary(): Boolean {
        Catalog.reset()
        return library.locate()
    }
}
