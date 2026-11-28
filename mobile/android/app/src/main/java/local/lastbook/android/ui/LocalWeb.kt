package local.lastbook.android.ui

import android.net.Uri
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import local.lastbook.core.LastbookCore
import local.lastbook.core.WebResponse
import java.io.ByteArrayInputStream

/**
 * The only origin the in-app WebViews may load from. Anything else is answered locally with a 403 or left un-navigated,
 * so a ZIM article, map link or library page cannot reach the network even if it embeds an absolute URL.
 */
internal object LocalWeb {
    const val HOST = "lastbook.local"

    fun isLocal(url: Uri?): Boolean = url?.host == HOST

    fun forbidden(): WebResourceResponse = WebResourceResponse(
        "text/plain", "utf-8", 403, "Forbidden", emptyMap(), ByteArrayInputStream(ByteArray(0)),
    )
}

/** Serves https://lastbook.local from the engine and blocks every other host, for requests and navigation alike. */
internal open class LocalWebViewClient : WebViewClient() {
    override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
        val url = request?.url ?: return null
        if (!LocalWeb.isLocal(url)) return LocalWeb.forbidden()
        val path = url.encodedPath.orEmpty().ifEmpty { "/" }
        val query = url.queryParameterNames.associate { it to (url.getQueryParameter(it) ?: "") }
        val r: WebResponse = LastbookCore.web.handle(path, query, request.method ?: "GET")
        val headers = HashMap<String, String>()
        headers["Cache-Control"] = r.headers["Cache-Control"] ?: "no-store"
        r.headers["Content-Security-Policy"]?.let { headers["Content-Security-Policy"] = it }
        return WebResourceResponse(
            r.mime.substringBefore(';'), null, r.status, if (r.status in 200..299) "OK" else "Not Found",
            headers, ByteArrayInputStream(r.bytes),
        )
    }

    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean =
        !LocalWeb.isLocal(request?.url)

    @Deprecated("Deprecated in Java")
    override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean =
        !LocalWeb.isLocal(url?.let(Uri::parse))
}
