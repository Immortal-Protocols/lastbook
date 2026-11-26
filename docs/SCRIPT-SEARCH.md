# Arabic words and Chinese substrings

Typing `مبكرا` now finds the saved word `مبكرًا`. Marked and unmarked Arabic
queries stay whole words instead of being split into fragments at vowel marks.
Results and assistant excerpts retain the exact saved spelling and marks; reader
highlights surround the original word. `دوار` finds `دوّار` without matching a
longer word that only contains those letters.

Only U+064B–U+0652 and U+0670 are optional in Arabic matching. Hamza, maddah,
other combining marks and different letters remain distinct. This is not Arabic
stemming, translation, transliteration, spelling correction or general Unicode
normalization. Searching without vowel marks can find multiple meanings of the
same letters; the original source wording remains visible.

Chinese queries retain literal Han substring matching, including short terms
inside unsegmented text. Simplified and Traditional characters are not converted.
Mixed Arabic/Han/Latin queries use the same idea groups as other searches. Latin
terms retain FTS word matching, so `water` does not match `waterproof`. Existing
multiword relaxation can still return results matching only some ideas.

The shared helper is used by reader search, local assistant keyword retrieval and
`tools/libq.py`. Query terms and allowed document IDs remain SQL parameters. Arabic
regular expressions contain escaped literal characters separated by optional
vowel marks; query punctuation cannot become a regular expression. Whole-word
checks retain other combining marks as part of a word. ID filters apply before
the result limit, including an empty allowed set. Overlapping highlights merge
and saved markup is escaped by the reader.

This is a read-only scan of the existing title/body fields for the affected query
terms. It adds no dependency, tokenizer, index, migration, source rewrite or
network behavior. Other query terms keep their existing FTS path. A data-only
supplement cannot update an older executable's search behavior; use matching
source/runtime. Large libraries may take longer than indexed FTS searches.

Fourteen Arabic tests and eight Chinese tests exercise actual search, original
snippets, mixed-script groups, word and letter distinctions, scoped retrieval,
video mapping, literal parameters and the read-only CLI. The required test command
includes both modules. The independent upstream change also carries the existing
synthetic setup-capacity fixture correction shared with PR487/491/493; production
disk reserves are unchanged.

Tokenizer context: [SQLite unicode61](https://www.sqlite.org/fts5.html#unicode61_tokenizer)
folds Latin diacritics; the [Unicode Arabic chart](https://www.unicode.org/charts/PDF/U0600.pdf)
distinguishes the vowel-mark range from combining hamza/maddah. No source chart or
font data is redistributed.
