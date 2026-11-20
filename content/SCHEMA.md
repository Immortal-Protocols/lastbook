# Curated topic files (`content/topics/<id>.json`)

Each file is one "need" in the app. The app shows, in order:
1. the title and a one-sentence intro,
2. **choices** ("What's happening?") — the person taps one situation and sees 1–4 recommended readings for it,
3. **limits** — when the source itself says to stop, get help, or that a professional/trained person is needed,
4. **prepare** — readings for getting ready before it happens,
5. **learn** — full manuals, videos, encyclopedia articles for deeper study,
6. for learning tracks, an ordered **route** of beginner-to-advanced steps.

Source facts (publisher, edition, date, file type, page count, video length, transcript) are filled in
automatically from `catalog.json` — do not copy them into the topic file.

```json
{
  "id": "water",
  "mode": "now",                     // "now" = urgent need, "learn" = longer-term learning track
  "title": "Get safe drinking water",
  "short": "Treat, store and find water",
  "intro": "One or two plain sentences in your own words. Describe what this section helps with; do not give procedures.",
  "keywords": ["water", "boil", "bleach", "purify", "filter", "thirsty", "drinking"],
  "choices": [
    {
      "id": "unsafe",
      "label": "Tap water is off or might be unsafe",
      "hint": "Boil-water notice, earthquake, flood, broken main",
      "urgent": ["not breathing"],     // optional: a search that names one of these phrases shows this guide and choice first
      "read": [
        {"doc": "<catalog id>", "page": 9,
         "label": "Short action-style headline of what the page helps with",
         "note": "What the reader will find on that page, <= 30 words, describing (not prescribing)."}
      ]
    }
  ],
  "limits": [
    {"text": "Faithful short paraphrase of a limit/warning/when-to-get-help statement from the source.",
     "doc": "<catalog id>", "page": 12}
  ],
  "prepare": [ {"doc": "...", "page": 21, "label": "...", "note": "..."} ],
  "learn":   [ {"doc": "...", "label": "...", "note": "..."},
               {"zim": "zim/<file>.zim/<Article_path>", "title": "Article title", "label": "...", "note": "..."} ],
  "route": [
    {"title": "Step 1: ...", "goal": "What the step is for, in plain words",
     "read": [ {"doc": "...", "page": 3, "label": "...", "note": "..."} ]}
  ],
  "related": ["sanitation", "food"]
}
```

Rules
- Every `doc` must be a real catalog id (not a `metadata-video-*` id). `page` is the PDF *file* page (1-based) as used by
  `libq.py page`; omit it for html/video/whole-document references. Verify each page by reading it.
- Use a video's own id (`video-...`) for videos. Prefer videos with captions/transcripts and reputable publishers.
- `label`/`note`/`intro`/`hint` are plain-language descriptions written for a stressed non-expert. They may describe what a
  page contains, but must not add steps, doses, quantities or advice that the page does not say.
- `limits` must be traceable to the cited page. Paraphrase faithfully; keep any quote under 15 words.
- Medical, chemical (bleach, fuels, pesticides), electrical and gas items: prefer current WHO/CDC/EPA/FEMA/Red Cross/
  Hesperian/MSF/USDA/extension sources; mention in `note` if a source is old (e.g. 1980s civil defense) or written for
  health workers or trained responders.
- `urgent` is only for a life-threatening choice that must win over any other choice in its topic. When a search names
  one of its phrases, that choice is shown for its topic and the topic is listed first, ahead of guides that matched more
  words and even below the usual 60% cut; the other guides that pass the cut follow in their usual order, at most three
  rows in all. A search that names no `urgent` phrase is ranked exactly as without the field. Each phrase is matched as
  whole words in order, so "not breathing" does not catch "trouble breathing".
- Favour fewer, better items: 1–4 readings per choice, 3–8 in prepare, 4–10 in learn.

## Tools in a choice (`tools`)

A choice may carry small tools, shown after its readings (`web/tools.js`). A tool does arithmetic on figures its cited pages
give, or keeps a time; it shows the figure and the page behind every result, and adds no advice of its own. Sources that
disagree are all shown, side by side, each with its own figures; none is picked. A tool whose sources are not in a library
is hidden there, like a reading.

```json
"tools": [
  {"kind": "dose", "id": "bleach", "title": "Work out the bleach for your amount of water",
   "note": "Optional line shown above the results, e.g. that sources disagree.",
   "sources": [
     {"doc": "<catalog id>", "page": 23, "strength": "For 5% bleach",
      "rates": [{"amount": 2, "per": "L"}, {"amount": 8, "per": "gal", "when": "Clear water"}],
      "note": "What else the page says, describing (not prescribing), <= 30 words."}]},
  {"kind": "clock", "id": "tourniquet", "title": "Keep the time a tourniquet went on",
   "now": "The tourniquet went on now", "at": "or the tourniquet went on at",
   "sources": [{"doc": "<catalog id>", "page": 170, "note": "Says to record the exact time ..."}]}
]
```

- `dose`: drops = the page's `amount` per `per` (`"L"` or `"gal"`, US gallon) × the amount the person types. The page's own
  rate for the unit chosen is used when it gives one; otherwise the rate is converted and the result says so. One result line
  per `when` (a condition the page names, such as clear or cloudy water). Results are rounded up to a whole drop, and say so.
- `clock`: the time the person says something happened, and how long ago that was, kept on this device until cleared.
  `now` and `at` name its button and its time field in words that stand alone (a screen reader or voice control may meet
  them without the heading); without them they read "It went on now" and "or it went on at".
- Every source needs `page`, and every figure must be on that page exactly as written: `tools/validate_topics.py` checks the
  ids, pages and the shape of each tool, and `app/tests/test_tools.py` checks the arithmetic on the real figures.
