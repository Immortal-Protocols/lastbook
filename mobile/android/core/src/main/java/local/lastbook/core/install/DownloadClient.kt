package local.lastbook.core.install

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.net.Proxy
import java.util.concurrent.TimeUnit

internal val LASTBOOK_DOWNLOAD_HOSTS = setOf(
    "downloads.lastbook.org",
    "huggingface.co",
    "cas-bridge.xethub.hf.co",
)
internal val LASTBOOK_DOWNLOAD_SUFFIXES = setOf(".hf.co")   // Hugging Face's download hosts and their siblings
internal const val LASTBOOK_MAX_REDIRECTS = 5

/** Raised before a connection is opened when an address is outside the download rules. */
internal class DownloadRefusedException(message: String) : IllegalStateException(message)

/**
 * The desktop downloader's network rules (engine/setup/download.py): HTTPS on port 443 to the known hosts only,
 * and redirects followed only to those addresses, at most [LASTBOOK_MAX_REDIRECTS] times. Every address, including
 * each redirect target, is checked before a request is sent.
 */
internal class DownloadPolicy(
    private val allowedHosts: Set<String> = LASTBOOK_DOWNLOAD_HOSTS,
    private val allowedSuffixes: Set<String> = LASTBOOK_DOWNLOAD_SUFFIXES,
    private val requireHttps: Boolean = true,
    private val requireDefaultPort: Boolean = true,
) {
    fun check(url: HttpUrl) {
        if (requireHttps && url.scheme != "https") refuse()
        if (url.username.isNotEmpty() || url.password.isNotEmpty()) refuse()
        if (requireDefaultPort && url.port != 443) refuse()
        if (!hostAllowed(url.host)) refuse()
    }

    private fun hostAllowed(host: String): Boolean {
        val h = host.lowercase().trimEnd('.')
        return h in allowedHosts ||
            allowedSuffixes.any { suffix -> h.endsWith(suffix) && h.length > suffix.length }
    }

    companion object {
        fun refuse(): Nothing = throw DownloadRefusedException(
            "Lastbook refused to download from an address it does not know."
        )
    }
}

/**
 * Opens one GET, following only allowed redirects. The caller owns the returned [Response].
 * Automatic redirects and proxies are off, so no hop can bypass [policy].
 */
internal class DownloadClient(
    private val policy: DownloadPolicy = DownloadPolicy(),
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.MINUTES)
        .followRedirects(false)
        .followSslRedirects(false)
        .proxy(Proxy.NO_PROXY)
        .build(),
    private val maxRedirects: Int = LASTBOOK_MAX_REDIRECTS,
) {
    fun open(url: String, startAt: Long = 0L): Response {
        var target = url.toHttpUrlOrNull() ?: DownloadPolicy.refuse()
        var followed = 0
        while (true) {
            policy.check(target)
            val builder = Request.Builder()
                .url(target)
                .header("Accept-Encoding", "identity")
            if (startAt > 0) builder.header("Range", "bytes=$startAt-")
            val response = http.newCall(builder.build()).execute()
            if (response.code !in REDIRECT_CODES) return response

            val location = response.header("Location")
            response.close()
            if (location.isNullOrEmpty()) {
                throw DownloadRefusedException("The download server answered with a move to nowhere.")
            }
            if (followed >= maxRedirects) {
                throw DownloadRefusedException("The download server sent Lastbook round in circles.")
            }
            followed++
            target = target.resolve(location)
                ?: throw DownloadRefusedException("The download server sent Lastbook to an address it does not know.")
        }
    }

    private companion object {
        val REDIRECT_CODES = setOf(301, 302, 303, 307, 308)
    }
}
