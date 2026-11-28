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

        override fun nativeMeasure(path: String, nCtx: Int, threads: Int): String =
            """{"ev":"fit","status":"fits","ram_total":16000000000,"device_bytes":0,"host_bytes":3000000000,"memory":[{"kind":"host","model":2500000000,"context":200000000,"compute":300000000}]}"""

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

        override fun nativeMeasure(path: String, nCtx: Int, threads: Int): String =
            """{"ev":"fit","status":"fits","ram_total":16000000000,"device_bytes":0,"host_bytes":3000000000,"memory":[{"kind":"host","model":2500000000,"context":200000000,"compute":300000000}]}"""

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

    private class MeasureOnlyRuntime(private val measureJson: String?) : LlamaRuntime {
        val events: MutableList<String> = Collections.synchronizedList(mutableListOf())

        override fun nativeMeasure(path: String, nCtx: Int, threads: Int): String? {
            events += "measure"
            return measureJson
        }

        override fun nativeLoad(path: String, nCtx: Int, threads: Int): Long {
            events += "load"
            return 1L
        }

        override fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                                    temp: Float, topK: Int, topP: Float): String {
            events += "generate"
            return "answer"
        }

        override fun nativeCancel(handle: Long) { events += "cancel" }
        override fun nativeFree(handle: Long) { events += "free" }
    }

    @Test
    fun `oversized model refuses before nativeLoad even when CPU fit reports fits`() {
        // Real Pixel 10 Pro measurement for Gemma 4 26B A4B (16.95 GB file on 16.33 GB RAM):
        // CPU-only llama.cpp reports status="fits" with 7.28 GB host_bytes, leaving 10.60 GB mapped weights uncounted.
        val measureJson = """{"ev":"fit","status":"fits","ram_total":16331776000,"ram_free":2732249088,"device_bytes":0,"host_bytes":7281262528,"memory":[{"kind":"host","model":6349572032,"context":356515840,"compute":575174656}]}"""
        val runtime = MeasureOnlyRuntime(measureJson)
        val llama = LocalLlama(runtime, fileSize = { 16_947_541_728L })

        val out = llama.generate("/models/gemma-4-26B.gguf", arrayOf("q"), booleanArrayOf(true), 8, 0.2f, 40, 0.95f)
        assertNull("oversized model must be refused", out)
        assertEquals(listOf("measure"), runtime.events)
        val err = llama.lastError()
        assertNotNull(err)
        assertTrue("error should explain memory fit: $err", err!!.contains("does not fit this phone’s memory"))
    }

    @Test
    fun `does_not_fit and unreadable model refuse before nativeLoad`() {
        val doesNotFit = MeasureOnlyRuntime("""{"ev":"fit","status":"does_not_fit","ram_total":8000000000,"device_bytes":0,"host_bytes":6000000000,"memory":[]}""")
        val llama1 = LocalLlama(doesNotFit, fileSize = { 5_000_000_000L })
        assertNull(llama1.generate("/models/big.gguf", arrayOf("q"), booleanArrayOf(true), 8, 0.2f, 40, 0.95f))
        assertEquals(listOf("measure"), doesNotFit.events)
        assertTrue(llama1.lastError()!!.contains("memory"))

        val unreadable = MeasureOnlyRuntime("""{"ev":"error","code":"model_file","msg":"bad file"}""")
        val llama2 = LocalLlama(unreadable, fileSize = { 1_000L })
        assertNull(llama2.generate("/models/bad.gguf", arrayOf("q"), booleanArrayOf(true), 8, 0.2f, 40, 0.95f))
        assertEquals(listOf("measure"), unreadable.events)
        assertTrue(llama2.lastError()!!.contains("could not read"))
    }

    @Test
    fun `fitting model passes measure and loads normally`() {
        // Gemma 4 12B (~7.37 GB file) on a 16 GB phone: ~8.1 GB in RAM + 2 GiB reserve ≈ 10.2 GB <= 16.33 GB.
        val measureJson = """{"ev":"fit","status":"fits","ram_total":16331776000,"device_bytes":0,"host_bytes":3500000000,"memory":[{"kind":"host","model":2800000000,"context":300000000,"compute":400000000}]}"""
        val runtime = MeasureOnlyRuntime(measureJson)
        val llama = LocalLlama(runtime, fileSize = { 7_366_423_360L })

        val out = llama.generate("/models/gemma-4-12b.gguf", arrayOf("q"), booleanArrayOf(true), 8, 0.2f, 40, 0.95f)
        assertEquals("answer", out)
        assertNull(llama.lastError())
        assertEquals(listOf("measure", "load", "generate"), runtime.events)
    }
}
