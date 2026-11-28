package local.lastbook.core.ai

/** The on-device llama.cpp runtime, built from the iPad's pinned source and bridge (JNI). No network, no port. */
object LlamaAndroid {
    init {
        System.loadLibrary("lastbook_llm")
    }

    external fun nativeMeasure(path: String, nCtx: Int, threads: Int): String?
    external fun nativeLoad(path: String, nCtx: Int, threads: Int): Long
    external fun nativeGenerate(handle: Long, texts: Array<String>, special: BooleanArray, maxTokens: Int,
                                temp: Float, topK: Int, topP: Float): String
    external fun nativeCancel(handle: Long)
    external fun nativeReset(handle: Long)
    external fun nativeFree(handle: Long)
}
