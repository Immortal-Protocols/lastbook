package local.lastbook.core.ai

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

class LocalLlamaTest {

    private class FakeRuntime : LlamaRuntime {
        val events: MutableList<String> = Collections.synchronizedList(mutableListOf())
        val started = CountDownLatch(1)
        val cancelled = CountDownLatch(1)
        val allowedToReturn = CountDownLatch(1)
        val finished = CountDownLatch(1)
        val freed = CountDownLatch(1)
        private val nextHandle = AtomicLong(1)
        @Volatile var freeCount = 0

        override fun nativeLoad(path: String, nCtx: Int, threads: Int): Long {
            events += "load"
            return nextHandle.getAndIncrement()
        }

        override fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                                    temp: Float, topK: Int, topP: Float): String {
            events += "generate:start"
            started.countDown()
            cancelled.await()
            allowedToReturn.await(10, TimeUnit.SECONDS)
            events += "generate:return"
            finished.countDown()
            return "answer"
        }

        override fun nativeCancel(handle: Long) {
            events += "cancel"
            cancelled.countDown()
        }

        override fun nativeFree(handle: Long) {
            events += "free"
            freeCount++
            freed.countDown()
        }
    }

    @Test
    fun `release frees only after generate returns and a second generate is refused`() {
        val runtime = FakeRuntime()
        val llama = LocalLlama(runtime)
        val texts = arrayOf("question")
        val special = booleanArrayOf(true)
        fun generate() = llama.generate("/models/a.gguf", texts, special, 8, 0.2f, 40, 0.95f)

        val generation = Thread { generate() }.apply { start() }
        assertTrue("generation did not start", runtime.started.await(5, TimeUnit.SECONDS))

        assertNull("a second answer must not overlap the first", generate())

        val releaseReturned = CountDownLatch(1)
        Thread {
            llama.release()
            releaseReturned.countDown()
        }.apply { isDaemon = true; start() }

        assertTrue("release must not wait for the running generation", releaseReturned.await(2, TimeUnit.SECONDS))
        assertEquals("generation must still be running while free waits", 1L, runtime.finished.count)

        runtime.allowedToReturn.countDown()
        assertTrue("generation did not return", runtime.finished.await(5, TimeUnit.SECONDS))
        assertTrue("model was not freed", runtime.freed.await(5, TimeUnit.SECONDS))
        generation.join(5_000)

        val generateAt = runtime.events.indexOf("generate:return")
        val freeAt = runtime.events.indexOf("free")
        assertTrue("free must follow generate return, but was $freeAt vs $generateAt: ${runtime.events}", freeAt > generateAt)
        assertEquals("the context must be freed exactly once", 1, runtime.freeCount)
    }

    private class GatedCancelRuntime : LlamaRuntime {
        val events: MutableList<String> = Collections.synchronizedList(mutableListOf())
        val cancelEntered = CountDownLatch(1)
        val allowCancel = CountDownLatch(1)
        val freed = CountDownLatch(1)
        private val cancels = AtomicInteger(0)

        override fun nativeLoad(path: String, nCtx: Int, threads: Int): Long = 1L

        override fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                                    temp: Float, topK: Int, topP: Float): String = "answer"

        override fun nativeCancel(handle: Long) {
            if (cancels.getAndIncrement() == 0) {
                events += "cancel:blocked"
                cancelEntered.countDown()
                allowCancel.await(10, TimeUnit.SECONDS)
            }
        }

        override fun nativeFree(handle: Long) {
            events += "free"
            freed.countDown()
        }
    }

    @Test
    fun `stop cancel cannot overlap a concurrent free`() {
        val runtime = GatedCancelRuntime()
        val llama = LocalLlama(runtime)
        assertNotNull(llama.generate("/models/a.gguf", arrayOf("q"), booleanArrayOf(true), 8, 0.2f, 40, 0.95f))

        val stopThread = Thread { llama.stop() }.apply { isDaemon = true; start() }
        assertTrue("stop did not enter cancel", runtime.cancelEntered.await(5, TimeUnit.SECONDS))

        val releaseReturned = CountDownLatch(1)
        Thread {
            llama.release()
            releaseReturned.countDown()
        }.apply { isDaemon = true; start() }
        assertTrue("release must not wait for the cancel in progress", releaseReturned.await(2, TimeUnit.SECONDS))

        assertFalse("free must wait until the cancel returns", runtime.freed.await(200, TimeUnit.MILLISECONDS))

        runtime.allowCancel.countDown()
        assertTrue("model was not freed", runtime.freed.await(5, TimeUnit.SECONDS))
        stopThread.join(5_000)

        val cancelAt = runtime.events.indexOf("cancel:blocked")
        val freeAt = runtime.events.indexOf("free")
        assertTrue("free must follow cancel, but was $freeAt vs $cancelAt: ${runtime.events}", freeAt > cancelAt)
    }
}
