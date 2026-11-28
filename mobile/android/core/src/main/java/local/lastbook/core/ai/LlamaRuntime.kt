package local.lastbook.core.ai

/** The JNI surface of the on-device llama.cpp bridge, indirected so the lifecycle can be tested without native code. */
internal interface LlamaRuntime {
    fun nativeMeasure(path: String, nCtx: Int, threads: Int): String?
    fun nativeLoad(path: String, nCtx: Int, threads: Int): Long
    fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                       temp: Float, topK: Int, topP: Float): String
    fun nativeCancel(handle: Long)
    fun nativeFree(handle: Long)
}

internal object NativeLlamaRuntime : LlamaRuntime {
    override fun nativeMeasure(path: String, nCtx: Int, threads: Int): String? =
        LlamaAndroid.nativeMeasure(path, nCtx, threads)

    override fun nativeLoad(path: String, nCtx: Int, threads: Int): Long =
        LlamaAndroid.nativeLoad(path, nCtx, threads)

    override fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                                temp: Float, topK: Int, topP: Float): String =
        LlamaAndroid.nativeGenerate(handle, texts, special, maxTokens, temp, topK, topP)

    override fun nativeCancel(handle: Long) = LlamaAndroid.nativeCancel(handle)

    override fun nativeFree(handle: Long) = LlamaAndroid.nativeFree(handle)
}
