// The desktop runner (packaging/llm/lastbook_llm.cpp, llama.cpp dde879bc) as in-process calls for the iPad app. The same
// fitting, context settings, prompt-prefix reuse, sampling, stop handling and UTF-8 piece joining; only the pipes are gone.
// See include/lastbook_llm.h. Built by scripts/build_llama_ios.sh into build/llama/<platform>/liblastbook_llm.a.

#include "lastbook_llm.h"

#include "llama.h"
#include "ggml-backend.h"
#include "fit.h"
#include "log.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include <sys/sysctl.h>
#include <mach/mach.h>
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#  include <os/proc.h>
#endif

using json = nlohmann::ordered_json;

// log.cpp asks common.cpp whether the terminal takes colours; common.cpp is not built in (as on desktop).
bool tty_can_use_colors() { return false; }
bool tty_enable_ansi() { return false; }

static char * dup_json(const json & j) {
    const std::string s = j.dump(-1, ' ', false, json::error_handler_t::replace);
    char * out = (char *) malloc(s.size() + 1);
    memcpy(out, s.c_str(), s.size() + 1);
    return out;
}

static void log_quiet(ggml_log_level level, const char * text, void *) {
    if (level >= GGML_LOG_LEVEL_WARN) {
        fputs(text, stderr);
    }
}

static std::once_flag g_init;
static void init_once() {
    std::call_once(g_init, [] {
        llama_log_set(log_quiet, nullptr);
        common_log_set_verbosity_thold(LOG_LEVEL_WARN);
        llama_backend_init();
    });
}

static uint64_t ram_total() {
    uint64_t v = 0;
    size_t n = sizeof(v);
    return sysctlbyname("hw.memsize", &v, &n, nullptr, 0) == 0 ? v : 0;
}

static uint64_t ram_free() {
    vm_statistics64_data_t s;
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    if (host_statistics64(mach_host_self(), HOST_VM_INFO64, (host_info64_t) &s, &count) != KERN_SUCCESS) {
        return 0;
    }
    return (uint64_t) (s.free_count + s.inactive_count + s.purgeable_count) * (uint64_t) vm_page_size;
}

static uint64_t app_available() {   // what iPadOS lets this app still take (0 on a Mac)
#if TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
    return (uint64_t) os_proc_available_memory();
#else
    return 0;
#endif
}

struct lb_llm {
    llama_model * model = nullptr;
    llama_context * ctx = nullptr;
    const llama_vocab * vocab = nullptr;
    std::vector<llama_token> cached;   // the tokens the context holds, in order
    std::atomic<bool> cancel{false};
};

static void base_params(llama_model_params & mp, llama_context_params & cp, int n_ctx, int threads) {
    mp = llama_model_default_params();
    cp = llama_context_default_params();
    cp.n_ctx = n_ctx;
    cp.n_batch = 2048;
    cp.n_ubatch = 512;
    cp.n_seq_max = 1;
    if (threads > 0) {
        cp.n_threads = cp.n_threads_batch = threads;
    }
    cp.no_perf = true;
    cp.swa_full = false;   // as llama-server runs it: the sliding-window layers keep only their window
}

static json rows_json(const std::vector<common_memory_breakdown_row> & rows, uint64_t & device_bytes, uint64_t & host_bytes) {
    json out = json::array();
    device_bytes = host_bytes = 0;
    for (const auto & r : rows) {
        if (r.kind == common_memory_breakdown_row::BUFFER_TYPE) {
            continue;
        }
        const uint64_t used = r.model + r.context + r.compute;
        json j = {{"kind", r.kind == common_memory_breakdown_row::HOST ? "host" : "device"}, {"name", r.name}, {"desc", r.description},
                  {"model", r.model}, {"context", r.context}, {"compute", r.compute}};
        if (r.kind == common_memory_breakdown_row::DEVICE) {
            j["total"] = r.total;
            j["free"] = r.free;
            device_bytes += used;
        } else {
            host_bytes += used;
        }
        out.push_back(j);
    }
    return out;
}

// The fit, exactly as the desktop runner's main(): only settings left at llama.cpp's defaults change; the context stays n_ctx.
static json fit(const char * path, llama_model_params & mp, llama_context_params & cp, int n_ctx,
                std::vector<float> & split, std::vector<llama_model_tensor_buft_override> & overrides, bool & ok) {
    split.assign(llama_max_devices(), 0.0f);
    overrides.assign(llama_max_tensor_buft_overrides(), llama_model_tensor_buft_override{});
    std::vector<size_t> margins(llama_max_devices(), (size_t) 1024 * 1024 * 1024);
    const auto t0 = std::chrono::steady_clock::now();
    auto st = common_fit_params(path, &mp, &cp, split.data(), overrides.data(), margins.data(), (uint32_t) n_ctx, nullptr, GGML_LOG_LEVEL_ERROR);
    if (st == COMMON_PARAMS_FIT_STATUS_ERROR) {
        ok = false;
        return {{"ev", "error"}, {"code", "model_file"}, {"msg", "llama.cpp could not read the model file"}};
    }
    ok = true;
    json f = {{"ev", "fit"}, {"status", st == COMMON_PARAMS_FIT_STATUS_SUCCESS ? "fits" : "does_not_fit"}, {"n_ctx", n_ctx},
              {"n_gpu_layers", mp.n_gpu_layers}, {"cpu_only", false}, {"ram_total", ram_total()}, {"ram_free", ram_free()},
              {"app_available", app_available()}};
    int n_over = 0;
    for (const auto & o : overrides) {
        if (!o.pattern) {
            break;
        }
        n_over++;
    }
    f["host_overrides"] = n_over;
    try {
        uint32_t n_train = 0, n_got = 0;
        uint64_t dev = 0, host = 0;
        f["memory"] = rows_json(common_fit_measure(path, &mp, &cp, &n_train, &n_got, GGML_LOG_LEVEL_ERROR), dev, host);
        f["device_bytes"] = dev;
        f["host_bytes"] = host;
    } catch (const std::exception & ex) {
        f["measure_error"] = ex.what();
    }
    f["fit_ms"] = (long long) std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
    return f;
}

extern "C" char * lb_measure(const char * path, int n_ctx, int n_threads) {
    init_once();
    llama_model_params mp;
    llama_context_params cp;
    base_params(mp, cp, n_ctx, n_threads);
    std::vector<float> split;
    std::vector<llama_model_tensor_buft_override> overrides;
    bool ok = false;
    try {
        return dup_json(fit(path, mp, cp, n_ctx, split, overrides, ok));
    } catch (const std::exception & ex) {
        return dup_json({{"ev", "error"}, {"code", "model_file"}, {"msg", ex.what()}});
    }
}

struct Progress {
    lb_progress_fn fn;
    void * user;
};

static bool on_progress(float p, void * data) {
    auto * pr = (Progress *) data;
    return pr->fn ? pr->fn(p, pr->user) : true;
}

static bool on_abort(void * data) {
    return ((lb_llm *) data)->cancel.load();
}

extern "C" lb_llm * lb_load(const char * path, int n_ctx, int n_threads, lb_progress_fn progress, void * user, char ** info, char ** error) {
    init_once();
    *info = nullptr;
    *error = nullptr;
    llama_model_params mp;
    llama_context_params cp;
    base_params(mp, cp, n_ctx, n_threads);
    std::vector<float> split;
    std::vector<llama_model_tensor_buft_override> overrides;   // must outlive the load: mp points into it
    bool ok = false;
    json f;
    try {
        f = fit(path, mp, cp, n_ctx, split, overrides, ok);
    } catch (const std::exception & ex) {
        f = {{"ev", "error"}, {"code", "model_file"}, {"msg", ex.what()}};
    }
    if (!ok) {
        *error = dup_json(f);
        return nullptr;
    }
    auto * m = new lb_llm();
    cp.abort_callback = on_abort;
    cp.abort_callback_data = m;
    Progress pr{progress, user};
    mp.progress_callback = on_progress;
    mp.progress_callback_user_data = &pr;
    const auto t_load = std::chrono::steady_clock::now();
    m->model = llama_model_load_from_file(path, mp);
    if (!m->model) {   // also when the progress callback stopped it: the app knows whether it asked
        *error = dup_json({{"ev", "error"}, {"code", "load"}, {"msg", "the model could not be loaded"}});
        delete m;
        return nullptr;
    }
    m->ctx = llama_init_from_model(m->model, cp);
    if (!m->ctx) {
        *error = dup_json({{"ev", "error"}, {"code", "context"}, {"msg", "there was not enough memory for the model's working space"}});
        llama_model_free(m->model);
        delete m;
        return nullptr;
    }
    m->vocab = llama_model_get_vocab(m->model);
    char desc[256] = {0};
    llama_model_desc(m->model, desc, sizeof(desc));
    *info = dup_json({{"ev", "ready"}, {"n_ctx", llama_n_ctx(m->ctx)}, {"desc", desc}, {"threads", llama_n_threads(m->ctx)},
                      {"n_gpu_layers", mp.n_gpu_layers}, {"fit", f},
                      {"load_ms", (long long) std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t_load).count()},
                      {"ram_free", ram_free()}, {"app_available", app_available()}});
    return m;
}

extern "C" void lb_cancel(lb_llm * m) {
    if (m) {
        m->cancel = true;
    }
}

extern "C" void lb_reset(lb_llm * m) {
    if (m) {
        m->cancel = false;
    }
}

extern "C" void lb_free(lb_llm * m) {
    if (!m) {
        return;
    }
    if (m->ctx) {
        llama_free(m->ctx);
    }
    if (m->model) {
        llama_model_free(m->model);
    }
    delete m;
}

extern "C" void lb_string_free(char * s) { free(s); }

// ------------------------------------------------------------------------------------------------------------ generation --
static std::vector<llama_token> tokenize(const llama_vocab * vocab, const std::string & text, bool special) {
    std::vector<llama_token> out(text.size() + 8);
    int n = llama_tokenize(vocab, text.data(), (int32_t) text.size(), out.data(), (int32_t) out.size(), false, special);
    if (n < 0) {
        out.resize(-n);
        n = llama_tokenize(vocab, text.data(), (int32_t) text.size(), out.data(), (int32_t) out.size(), false, special);
    }
    out.resize(n > 0 ? n : 0);
    return out;
}

static std::string piece(const llama_vocab * vocab, llama_token t) {
    char buf[256];
    int n = llama_token_to_piece(vocab, t, buf, sizeof(buf), 0, true);
    if (n < 0) {
        std::string big(-n, '\0');
        n = llama_token_to_piece(vocab, t, big.data(), (int32_t) big.size(), 0, true);
        return big.substr(0, n > 0 ? n : 0);
    }
    return std::string(buf, n);
}

static size_t complete_utf8(const std::string & s) {   // how much of s ends on a whole character; the rest waits for the next piece
    size_t n = s.size();
    for (size_t back = 1; back <= 4 && back <= n; back++) {
        unsigned char c = (unsigned char) s[n - back];
        if ((c & 0xC0) == 0x80) {
            continue;
        }
        size_t need = c < 0x80 ? 1 : (c >> 5) == 6 ? 2 : (c >> 4) == 14 ? 3 : (c >> 3) == 30 ? 4 : 1;
        return back >= need ? n : n - back;
    }
    return n;
}

static bool decode_all(lb_llm & e, const std::vector<llama_token> & toks, size_t from, int & err) {
    const int n_batch = (int) llama_n_batch(e.ctx);
    for (size_t i = from; i < toks.size(); i += n_batch) {
        if (e.cancel) {
            err = 2;
            return false;
        }
        int n = (int) std::min<size_t>(n_batch, toks.size() - i);
        int rc = llama_decode(e.ctx, llama_batch_get_one(const_cast<llama_token *>(toks.data() + i), n));
        if (rc != 0) {
            err = rc == 2 ? 2 : 1;
            return false;
        }
        e.cached.insert(e.cached.end(), toks.begin() + i, toks.begin() + i + n);
    }
    return true;
}

extern "C" char * lb_generate(lb_llm * mp, const char * const * texts, const bool * special, int n_segments, int max_tokens_in,
                              float temp, int top_k, float top_p, float min_p, uint32_t seed, const char * stop,
                              lb_piece_fn emit, void * user) {
    using clock = std::chrono::steady_clock;
    if (!mp || !mp->ctx) {
        return dup_json({{"ev", "error"}, {"code", "not_loaded"}, {"msg", "the model is not loaded"}});
    }
    lb_llm & e = *mp;
    const auto t0 = clock::now();
    std::vector<llama_token> toks;
    if (llama_vocab_get_add_bos(e.vocab)) {
        toks.push_back(llama_vocab_bos(e.vocab));
    }
    for (int i = 0; i < n_segments; i++) {
        auto part = tokenize(e.vocab, texts[i] ? std::string(texts[i]) : std::string(), special[i]);
        toks.insert(toks.end(), part.begin(), part.end());
    }
    const int n_ctx = (int) llama_n_ctx(e.ctx);
    int max_tokens = std::max(1, max_tokens_in);
    if ((int) toks.size() + 16 >= n_ctx) {
        return dup_json({{"ev", "error"}, {"code", "too_long"},
                         {"msg", "the question and its sources are " + std::to_string(toks.size()) + " tokens; the model holds " + std::to_string(n_ctx)}});
    }
    max_tokens = std::min(max_tokens, n_ctx - (int) toks.size());

    // Reuse what the context already holds: a follow-up round repeats the conversation so far.
    size_t keep = 0;
    while (keep < e.cached.size() && keep < toks.size() && e.cached[keep] == toks[keep]) {
        keep++;
    }
    if (keep == toks.size()) {
        keep--;
    }
    llama_memory_t mem = llama_get_memory(e.ctx);
    if (keep < e.cached.size()) {
        if (!llama_memory_seq_rm(mem, 0, (llama_pos) keep, -1)) {
            llama_memory_clear(mem, true);   // the sliding-window layers cannot always go back: start over
            keep = 0;
        }
        e.cached.resize(keep);
    }
    const size_t reused = keep;

    int err = 0;   // e.cancel is cleared by lb_reset, under the app's lock, so a stop that comes first is never lost
    if (!decode_all(e, toks, keep, err)) {
        llama_memory_clear(mem, true);
        e.cached.clear();
        if (err == 2) {
            return dup_json({{"ev", "done"}, {"reason", "cancel"}, {"n_prompt", toks.size()}, {"n_reused", reused}, {"n_gen", 0}});
        }
        return dup_json({{"ev", "error"}, {"code", "decode"}, {"msg", "the model could not read the question (llama_decode failed)"}});
    }
    const auto t1 = clock::now();

    llama_sampler * smpl = llama_sampler_chain_init(llama_sampler_chain_default_params());
    llama_sampler_chain_add(smpl, llama_sampler_init_top_k(top_k));
    llama_sampler_chain_add(smpl, llama_sampler_init_top_p(top_p, 1));
    llama_sampler_chain_add(smpl, llama_sampler_init_min_p(min_p, 1));
    llama_sampler_chain_add(smpl, llama_sampler_init_temp(temp));
    llama_sampler_chain_add(smpl, llama_sampler_init_dist(seed));

    const std::string stop_s = stop ? stop : "";
    std::string pending, why = "length", stopped_by;
    int n_gen = 0;
    for (; n_gen < max_tokens; n_gen++) {
        if (e.cancel) {
            why = "cancel";
            break;
        }
        llama_token t = llama_sampler_sample(smpl, e.ctx, -1);
        if (llama_vocab_is_eog(e.vocab, t)) {
            why = "eog";
            break;
        }
        std::string p = piece(e.vocab, t);
        if (!stop_s.empty() && p == stop_s) {
            why = "stop";
            stopped_by = stop_s;
            break;
        }
        pending += p;
        size_t ok = complete_utf8(pending);
        if (ok && emit) {
            emit(pending.data(), (int) ok, user);
            pending.erase(0, ok);
        }
        llama_token one = t;
        if (llama_decode(e.ctx, llama_batch_get_one(&one, 1)) != 0) {
            why = e.cancel ? "cancel" : "decode";
            break;
        }
        e.cached.push_back(t);
    }
    llama_sampler_free(smpl);
    if (!pending.empty() && emit) {
        emit(pending.data(), (int) pending.size(), user);
    }
    if (why == "decode") {
        llama_memory_clear(mem, true);
        e.cached.clear();
        return dup_json({{"ev", "error"}, {"code", "decode"}, {"msg", "the model stopped while writing (llama_decode failed)"}});
    }
    const auto t2 = clock::now();
    auto ms = [](auto a, auto b) { return (long long) std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count(); };
    json done = {{"ev", "done"}, {"reason", why}, {"n_prompt", toks.size()}, {"n_reused", reused}, {"n_gen", n_gen},
                 {"prompt_ms", ms(t0, t1)}, {"gen_ms", ms(t1, t2)}};
    if (!stopped_by.empty()) {
        done["stop"] = stopped_by;
    }
    return dup_json(done);
}
