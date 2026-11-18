// Minimal C bridge to libzim inside CoreKiwix.xcframework, for the iPhone app's encyclopedia reader.
#ifndef PHONE_ZIM_H
#define PHONE_ZIM_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void * lb_zim_open(const char * path);
void lb_zim_close(void * archive);
char * lb_zim_main_path(void * archive);
bool lb_zim_has_title_index(void * archive);
bool lb_zim_has_fulltext_index(void * archive);

/// The entry at `path` (or the main entry when empty). On success returns malloc'd bytes, writes the mime type and
/// length; the caller frees both with lb_zim_free. Returns NULL when the entry is not there.
char * lb_zim_item(void * archive, const char * path, char ** mime, size_t * length);

/// JSON array of {title,path,snippet}. `full` uses the full-text index, otherwise title suggestions.
char * lb_zim_search(void * archive, const char * query, bool full, int limit);

void lb_zim_free(void * p);

#ifdef __cplusplus
}
#endif

#endif
