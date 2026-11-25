package local.lastbook.core.install

import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

class DownloadClientTest {
    private lateinit var origin: TestServer
    private lateinit var stranger: TestServer
    private val originHits = AtomicInteger()
    private val strangerHits = AtomicInteger()
    private val loopHits = AtomicInteger()

    @Before
    fun startServers() {
        stranger = TestServer {
            strangerHits.incrementAndGet()
            TestResponse(200)
        }
        origin = TestServer { path ->
            when (path) {
                "/pack" -> {
                    originHits.incrementAndGet()
                    TestResponse(200, body = "lastbook-download".toByteArray())
                }
                "/off-list" -> {
                    originHits.incrementAndGet()
                    TestResponse(302, mapOf("Location" to "http://localhost:${stranger.port}/stolen"))
                }
                "/loop" -> {
                    loopHits.incrementAndGet()
                    TestResponse(302, mapOf("Location" to "/loop"))
                }
                else -> TestResponse(404)
            }
        }
    }

    @After
    fun stopServers() {
        origin.close()
        stranger.close()
    }

    @Test
    fun `a permitted download works and a redirect outside the allowed hosts is refused before connecting`() {
        val client = DownloadClient(policy = testPolicy())

        client.open(originUrl("/pack")).use { response ->
            assertEquals(200, response.code)
            assertEquals("lastbook-download", response.body?.string())
        }
        assertEquals(1, originHits.get())
        assertEquals(0, strangerHits.get())

        val refused = assertThrows(DownloadRefusedException::class.java) {
            client.open(originUrl("/off-list")).close()
        }
        assertTrue(refused.message.orEmpty().contains("does not know"))
        assertEquals(2, originHits.get())   // the redirecting address was asked once
        assertEquals(0, strangerHits.get()) // its target was never contacted
    }

    @Test
    fun `a redirect chain stops at the desktop limit`() {
        val client = DownloadClient(policy = testPolicy())

        val refused = assertThrows(DownloadRefusedException::class.java) {
            client.open(originUrl("/loop")).close()
        }
        assertTrue(refused.message.orEmpty().contains("round in circles"))
        assertEquals(LASTBOOK_MAX_REDIRECTS + 1, loopHits.get())
    }

    @Test
    fun `the production policy permits only https to the download hosts`() {
        val policy = DownloadPolicy()
        fun permitted(url: String) = runCatching { policy.check(url.toHttpUrl()) }.isSuccess

        assertTrue(permitted("https://downloads.lastbook.org/packs/lastbook-small.zip"))
        assertTrue(permitted("https://huggingface.co/unsloth/gemma.gguf"))
        assertTrue(permitted("https://cas-bridge.xethub.hf.co/x/y"))
        assertTrue(permitted("https://r2.hf.co/x/y"))

        assertFalse(permitted("http://downloads.lastbook.org/packs/lastbook-small.zip"))
        assertFalse(permitted("https://downloads.lastbook.org:8443/packs/lastbook-small.zip"))
        assertFalse(permitted("https://downloads.lastbook.org.evil.example/x"))
        assertFalse(permitted("https://evil.example/x"))
        assertFalse(permitted("https://hf.co/x"))
        assertFalse(permitted("https://user:pass@huggingface.co/x"))
    }

    private fun testPolicy() = DownloadPolicy(
        allowedHosts = setOf("127.0.0.1"),
        allowedSuffixes = emptySet(),
        requireHttps = false,
        requireDefaultPort = false,
    )

    private fun originUrl(path: String) = "http://127.0.0.1:${origin.port}$path"

    private data class TestResponse(
        val status: Int,
        val headers: Map<String, String> = emptyMap(),
        val body: ByteArray = ByteArray(0),
    )

    /** One request per connection, enough for the downloader's plain GETs. */
    private class TestServer(private val handle: (String) -> TestResponse) : AutoCloseable {
        private val socket = ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))
        val port: Int get() = socket.localPort

        init {
            thread(isDaemon = true) {
                while (!socket.isClosed) {
                    val client = try { socket.accept() } catch (e: IOException) { break }
                    client.use { c ->
                        val input = c.getInputStream().bufferedReader()
                        val request = input.readLine() ?: return@use
                        val path = request.split(' ').getOrNull(1) ?: "/"
                        while (true) {
                            val line = input.readLine() ?: break
                            if (line.isEmpty()) break
                        }
                        val response = handle(path)
                        val head = buildString {
                            append("HTTP/1.1 ${response.status} ${reason(response.status)}\r\n")
                            response.headers.forEach { (k, v) -> append("$k: $v\r\n") }
                            append("Content-Length: ${response.body.size}\r\n")
                            append("Connection: close\r\n\r\n")
                        }
                        val out = c.getOutputStream()
                        out.write(head.toByteArray())
                        out.write(response.body)
                        out.flush()
                    }
                }
            }
        }

        override fun close() {
            socket.close()
        }

        private fun reason(status: Int) = when (status) {
            200 -> "OK"
            302 -> "Found"
            404 -> "Not Found"
            else -> "Status"
        }
    }
}
