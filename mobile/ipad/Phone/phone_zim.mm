#include "phone_zim.h"

#include <zim/archive.h>
#include <zim/entry.h>
#include <zim/item.h>
#include <zim/search.h>
#include <zim/suggestion.h>

#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static zim::Archive * A(void * p) { return static_cast<zim::Archive *>(p); }

static char * dup(const std::string & s) {
    char * out = static_cast<char *>(std::malloc(s.size() + 1));
    if (!out) return nullptr;
    std::memcpy(out, s.c_str(), s.size() + 1);
    return out;
}

static std::string esc(const std::string & s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) { char b[7]; std::snprintf(b, sizeof b, "\\u%04x", c); out += b; }
                else out += static_cast<char>(c);
        }
    }
    return out;
}

void * lb_zim_open(const char * path) {
    try { return new zim::Archive(std::string(path)); } catch (...) { return nullptr; }
}

void lb_zim_close(void * archive) { delete A(archive); }

char * lb_zim_main_path(void * archive) {
    try { return dup(A(archive)->getMainEntry().getPath()); } catch (...) { return nullptr; }
}

bool lb_zim_has_title_index(void * archive) {
    try { return A(archive)->hasTitleIndex(); } catch (...) { return false; }
}

bool lb_zim_has_fulltext_index(void * archive) {
    try { return A(archive)->hasFulltextIndex(); } catch (...) { return false; }
}

char * lb_zim_item(void * archive, const char * path, char ** mime, size_t * length) {
    try {
        auto a = A(archive);
        std::string p = path ? path : "";
        zim::Entry e = p.empty() ? a->getMainEntry() : a->getEntryByPath(p);
        zim::Item item = e.getItem(true);
        zim::Blob blob = item.getData();
        char * out = static_cast<char *>(std::malloc(blob.size() ? blob.size() : 1));
        if (!out) return nullptr;
        if (blob.size()) std::memcpy(out, blob.data(), blob.size());
        if (mime) *mime = dup(item.getMimetype());
        if (length) *length = blob.size();
        return out;
    } catch (...) { return nullptr; }
}

char * lb_zim_search(void * archive, const char * query, bool full, int limit) {
    std::string out = "[";
    bool first = true;
    try {
        auto a = A(archive);
        auto add = [&](const std::string & title, const std::string & path, const std::string & snippet) {
            if (!first) out += ",";
            first = false;
            out += "{\"title\":\"" + esc(title) + "\",\"path\":\"" + esc(path) + "\",\"snippet\":\"" + esc(snippet) + "\"}";
        };
        if (full && a->hasFulltextIndex()) {
            zim::Searcher searcher(*a);
            zim::Query q(query ? query : "");
            auto search = searcher.search(q);
            auto results = search.getResults(0, limit);
            for (auto it = results.begin(); it != results.end(); ++it) add(it->getTitle(), it->getPath(), "");
        } else if (a->hasTitleIndex()) {
            zim::SuggestionSearcher searcher(*a);
            auto search = searcher.suggest(query ? query : "");
            auto results = search.getResults(0, limit);
            for (auto it = results.begin(); it != results.end(); ++it) add(it->getTitle(), it->getPath(), it->getSnippet());
        }
    } catch (...) { }
    out += "]";
    return dup(out);
}

void lb_zim_free(void * p) { std::free(p); }
