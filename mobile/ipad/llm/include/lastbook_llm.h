// The local AI inside the iPad app: the desktop runner (packaging/llm/lastbook_llm.cpp) as in-process calls instead of a
// program behind pipes. No socket, no port, no web address: it reads one file, the model it is given.
//
// Every call that returns a char * returns a JSON object (the same objects the desktop runner prints) that the caller frees
// with lb_string_free.
#ifndef LASTBOOK_LLM_H
#define LASTBOOK_LLM_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct lb_llm lb_llm;

/// llama.cpp's fitting (common_fit_params, as llama-server's default --fit) for this model and context, loading nothing.
/// Returns the desktop's {"ev":"fit",...} object, or {"ev":"error","code":"model_file",...}.
char * lb_measure(const char * path, int n_ctx, int n_threads);

/// Called while the model loads with 0...1. Returning false stops the load (lb_load then returns NULL).
typedef bool (*lb_progress_fn)(float progress, void * user);

/// Fits, then loads the model and makes a context of n_ctx tokens. NULL on failure (also when progress said stop), with *error an
/// {"ev":"error","code":"load|context|model_file",...} object. On success *info holds {"ev":"ready",...}.
lb_llm * lb_load(const char * path, int n_ctx, int n_threads, lb_progress_fn progress, void * user, char ** info, char ** error);

/// One visible piece of the answer (whole UTF-8 characters).
typedef void (*lb_piece_fn)(const char * bytes, int length, void * user);

/// Writes one answer for a prompt given as segments: texts[i] is template markup whose special tokens count when special[i]
/// is true, and plain text that can never start a turn when it is false. Reuses what the context already holds (the prompt
/// prefix of the previous round). Returns {"ev":"done","reason":"eog|stop|length|cancel",...} or {"ev":"error","code":...}.
char * lb_generate(lb_llm * m, const char * const * texts, const bool * special, int n_segments, int max_tokens,
                   float temp, int top_k, float top_p, float min_p, uint32_t seed, const char * stop,
                   lb_piece_fn piece, void * user);

/// Stops the answer being written (any thread). It stays stopped until lb_reset.
void lb_cancel(lb_llm * m);

/// Clears a stop, before the next lb_generate.
void lb_reset(lb_llm * m);

/// Frees the model and its context. Not while lb_generate runs on another thread.
void lb_free(lb_llm * m);

void lb_string_free(char * s);

#ifdef __cplusplus
}
#endif

#endif
