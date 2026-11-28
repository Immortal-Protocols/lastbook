#include <jni.h>
#include <android/log.h>
#define LBLOG(...) __android_log_print(ANDROID_LOG_INFO, "LastbookLLM", __VA_ARGS__)
#include "lastbook_llm.h"

#include <string>
#include <vector>

static std::string g_last = "";

static void piece(const char * bytes, int length, void *) {
    if (bytes && length > 0) g_last.append(bytes, static_cast<size_t>(length));
}

extern "C" JNIEXPORT jstring JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeMeasure(JNIEnv * env, jobject, jstring path, jint n_ctx, jint threads) {
    const char * p = env->GetStringUTFChars(path, nullptr);
    LBLOG("measure start %s ctx=%d threads=%d", p, (int)n_ctx, (int)threads);
    char * raw = lb_measure(p, n_ctx, threads);
    LBLOG("measure end result=%s", raw ? raw : "");
    env->ReleaseStringUTFChars(path, p);
    if (!raw) return nullptr;
    jstring out = env->NewStringUTF(raw);
    lb_string_free(raw);
    return out;
}

extern "C" JNIEXPORT jlong JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeLoad(JNIEnv * env, jobject, jstring path, jint n_ctx, jint threads) {
    const char * p = env->GetStringUTFChars(path, nullptr);
    char * info = nullptr;
    char * error = nullptr;
    LBLOG("load start %s ctx=%d threads=%d", p, (int)n_ctx, (int)threads);
    lb_llm * m = lb_load(p, n_ctx, threads, nullptr, nullptr, &info, &error);
    LBLOG("load end handle=%p info=%s error=%s", (void*)m, info ? info : "", error ? error : "");
    env->ReleaseStringUTFChars(path, p);
    if (info) lb_string_free(info);
    if (error) lb_string_free(error);
    return reinterpret_cast<jlong>(m);
}

extern "C" JNIEXPORT jstring JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeGenerate(JNIEnv * env, jobject, jlong handle,
        jobjectArray texts, jbooleanArray special, jint max_tokens, jfloat temp, jint top_k, jfloat top_p) {
    auto * m = reinterpret_cast<lb_llm *>(handle);
    if (!m) return env->NewStringUTF("");
    const jsize n = env->GetArrayLength(texts);
    std::vector<std::string> owned(static_cast<size_t>(n));
    std::vector<const char *> ptrs(static_cast<size_t>(n));
    std::vector<bool> spec(static_cast<size_t>(n));
    std::vector<jboolean> specIn(static_cast<size_t>(n));
    if (special) env->GetBooleanArrayRegion(special, 0, n, specIn.data());
    for (jsize i = 0; i < n; i++) {
        auto s = (jstring) env->GetObjectArrayElement(texts, i);
        const char * c = env->GetStringUTFChars(s, nullptr);
        owned[i] = c ? c : "";
        if (c) env->ReleaseStringUTFChars(s, c);
        env->DeleteLocalRef(s);
        ptrs[i] = owned[i].c_str();
        spec[i] = special && specIn[static_cast<size_t>(i)];
    }
    std::vector<char> specBytes(static_cast<size_t>(n));
    for (jsize i = 0; i < n; i++) specBytes[static_cast<size_t>(i)] = spec[static_cast<size_t>(i)] ? 1 : 0;
    g_last.clear();
    lb_reset(m);
    LBLOG("generate start segments=%d max=%d", (int)n, (int)max_tokens);
    char * done = lb_generate(m, ptrs.data(), reinterpret_cast<const bool *>(specBytes.data()), n, max_tokens,
                              temp, top_k, top_p, 0.0f, 42u, nullptr, piece, nullptr);
    LBLOG("generate end bytes=%zu done=%s", g_last.size(), done ? done : "");
    if (done) lb_string_free(done);
    // Strip a Gemma thinking channel if the model emitted one.
    std::string out = g_last;
    for (;;) {
        auto a = out.find("<|channel>"), b = out.find("<channel|>");
        if (a == std::string::npos) break;
        if (b == std::string::npos || b < a) { out.erase(a); break; }
        out.erase(a, b + 10 - a);
    }
    if (auto b = out.find("<channel|>"); b != std::string::npos) {
        out.erase(0, b + 10);
    }
    while (!out.empty() && (out.back() == '\n' || out.back() == ' ')) out.pop_back();
    return env->NewStringUTF(out.c_str());
}

extern "C" JNIEXPORT void JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeCancel(JNIEnv *, jobject, jlong handle) {
    if (auto * m = reinterpret_cast<lb_llm *>(handle)) lb_cancel(m);
}

extern "C" JNIEXPORT void JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeReset(JNIEnv *, jobject, jlong handle) {
    if (auto * m = reinterpret_cast<lb_llm *>(handle)) lb_reset(m);
}

extern "C" JNIEXPORT void JNICALL
Java_local_lastbook_core_ai_LlamaAndroid_nativeFree(JNIEnv *, jobject, jlong handle) {
    if (auto * m = reinterpret_cast<lb_llm *>(handle)) lb_free(m);
}
