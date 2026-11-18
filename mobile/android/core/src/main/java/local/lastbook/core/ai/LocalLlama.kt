package local.lastbook.core.ai

import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/**
 * One native model context and the serialization around it. The bridge shares one context and one output buffer, so
 * only one generation may run at a time, and the context may only be freed while no generation is using it.
 */
internal class LocalLlama(private val runtime: LlamaRuntime = NativeLlamaRuntime) {
    private val handle = AtomicLong(0L)
    @Volatile private var loadedPath: String? = null
    private val genLock = java.util.concurrent.locks.ReentrantLock()
    private val life = Any()
    private val releaseExecutor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "lastbook-llm-release").apply { isDaemon = true }
    }

    /** Returns null when another answer is already running or the runtime cannot load/write. */
    fun generate(path: String, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                 temp: Float, topK: Int, topP: Float): String? {
        if (!genLock.tryLock()) return null
        return try {
            var h = handle.get()
            if (h == 0L || loadedPath != path) {
                if (h != 0L && handle.compareAndSet(h, 0L)) free(h)
                val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 6)
                h = runCatching { runtime.nativeLoad(path, 2048, threads) }.getOrDefault(0L)
                if (h == 0L) return null
                handle.set(h); loadedPath = path
            }
            runCatching { runtime.nativeGenerate(h, texts, special, maxTokens, temp, topK, topP) }
                .getOrNull()?.trim()?.takeIf { it.isNotEmpty() }
        } finally {
            genLock.unlock()
        }
    }

    fun stop() = synchronized(life) {
        val h = handle.get()
        if (h != 0L) runCatching { runtime.nativeCancel(h) }
    }

    /**
     * Cancels an answer at once, then frees the context on a background thread while holding the generation lock, so
     * the UI never waits and [runtime.nativeFree] never overlaps [runtime.nativeGenerate].
     */
    fun release() {
        val held = handle.getAndSet(0L)
        loadedPath = null
        if (held != 0L) runCatching { runtime.nativeCancel(held) }
        releaseExecutor.execute {
            genLock.lock()
            try {
                val late = handle.getAndSet(0L)
                loadedPath = null
                if (held != 0L) free(held)
                if (late != 0L) free(late)
            } finally {
                genLock.unlock()
            }
        }
    }

    private fun free(h: Long) = synchronized(life) {
        runCatching { runtime.nativeFree(h) }
    }
}
