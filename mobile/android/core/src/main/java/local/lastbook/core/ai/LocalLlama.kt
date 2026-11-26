package local.lastbook.core.ai

import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/** Result of evaluating llama.cpp's pre-load fit measurement against this phone's RAM. */
internal data class FitDecision(
    val fits: Boolean,
    val needsBytes: Long = 0L,
    val ramTotalBytes: Long = 0L,
    val reason: String? = null,
)

/**
 * One native model context and the serialization around it. The bridge shares one context and one output buffer, so
 * only one generation may run at a time, and the context may only be freed while no generation is using it.
 */
internal class LocalLlama(
    private val runtime: LlamaRuntime = NativeLlamaRuntime,
    private val fileSize: (String) -> Long = { File(it).length() },
) {
    private val handle = AtomicLong(0L)
    @Volatile private var loadedPath: String? = null
    @Volatile private var lastFailure: String? = null
    private val genLock = java.util.concurrent.locks.ReentrantLock()
    private val life = Any()
    private val releaseExecutor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "lastbook-llm-release").apply { isDaemon = true }
    }

    fun lastError(): String? = lastFailure

    /** Returns null when another answer is already running, the model does not fit RAM, or the runtime cannot load/write. */
    fun generate(path: String, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                 temp: Float, topK: Int, topP: Float): String? {
        if (!genLock.tryLock()) return null
        return try {
            lastFailure = null
            var h = handle.get()
            if (h == 0L || loadedPath != path) {
                if (h != 0L && handle.compareAndSet(h, 0L)) free(h)
                val threads = Runtime.getRuntime().availableProcessors().coerceIn(2, 6)
                val measured = runCatching { runtime.nativeMeasure(path, 2048, threads) }.getOrNull()
                val fit = judgeFit(measured, runCatching { fileSize(path) }.getOrDefault(0L))
                if (!fit.fits) {
                    lastFailure = fit.reason
                    return null
                }
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
        lastFailure = null
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

    companion object {
        /** Headroom kept for Android and the rest of Lastbook beyond the model weights, context and compute buffers. */
        const val RESERVE_BYTES: Long = 2L * 1024 * 1024 * 1024

        /**
         * Matches desktop `llm_local.judge`: llama.cpp's `common_fit_params` only budgets GPU devices and treats host
         * RAM as unlimited, and on CPU-only Android mapped weights outside llama.cpp's `model` count are still paged
         * into RAM during load and inference. Count both against `ram_total` plus [RESERVE_BYTES] before loading.
         */
        internal fun judgeFit(measureJson: String?, fileSizeBytes: Long): FitDecision {
            if (measureJson.isNullOrBlank()) {
                return FitDecision(false, reason = "The local AI could not read the model file. These library pages match your question.")
            }
            val o = runCatching { JSONObject(measureJson) }.getOrNull()
                ?: return FitDecision(false, reason = "The local AI could not read the model file. These library pages match your question.")
            if (o.optString("ev") != "fit") {
                return FitDecision(false, reason = "The local AI could not read the model file. These library pages match your question.")
            }
            val ramTotal = o.optLong("ram_total", 0L)
            val deviceBytes = o.optLong("device_bytes", 0L)
            val hostBytes = o.optLong("host_bytes", 0L)
            var modelMeasured = 0L
            val mem = o.optJSONArray("memory")
            if (mem != null) {
                for (i in 0 until mem.length()) {
                    modelMeasured += mem.optJSONObject(i)?.optLong("model", 0L) ?: 0L
                }
            }
            val mapped = maxOf(0L, fileSizeBytes - modelMeasured)
            val inRam = deviceBytes + hostBytes + mapped
            val needs = inRam + RESERVE_BYTES
            if (o.optString("status") != "fits") {
                return FitDecision(
                    fits = false,
                    needsBytes = needs,
                    ramTotalBytes = ramTotal,
                    reason = "This model does not fit this phone’s memory. These library pages match your question.",
                )
            }
            if (ramTotal > 0L && needs > ramTotal) {
                return FitDecision(
                    fits = false,
                    needsBytes = needs,
                    ramTotalBytes = ramTotal,
                    reason = "This model does not fit this phone’s memory (needs about ${gb(needs)}, phone has ${gb(ramTotal)}). These library pages match your question.",
                )
            }
            return FitDecision(fits = true, needsBytes = needs, ramTotalBytes = ramTotal)
        }

        private fun gb(bytes: Long): String =
            if (bytes >= 10_000_000_000L) String.format(Locale.US, "%.0f GB", bytes / 1e9)
            else String.format(Locale.US, "%.1f GB", bytes / 1e9)
    }
}
