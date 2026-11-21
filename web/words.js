/* Word handling for topic search: split, fold and match words in any script, not just a-z.
   Loaded before app.js. No DOM, no network: app/tests/test_topic_search.py runs these same functions in Node. */
(function (root) {
  'use strict';

  // Scripts written without spaces between words. A word in one of these matches anywhere in the text, at any length.
  const NO_SPACES = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\p{Script=Thai}\p{Script=Lao}\p{Script=Khmer}\p{Script=Myanmar}]/u;
  // Accent marks on Latin letters, once a word is decomposed. Only Latin, the same as the library's FTS5 index (unicode61).
  const LATIN_MARKS = /(\p{Script=Latin})\p{M}+/gu;
  // Anything that isn't a letter, mark or digit separates words, as [^a-z0-9] did for a-z.
  const NOT_WORD = /[^\p{L}\p{M}\p{N}]+/u;

  // The key two texts are compared by. Display text is never changed.
  // Order: lower-case, decompose (NFKD), then remove marks. Decomposing before removing marks is the part that
  // matters: NFC "İ" is one character with no mark to remove, and lower-casing it afterwards gives "i" plus a
  // combining dot (U+0307), so "İstanbul" would miss "istanbul". NFKD also splits é into e + accent.
  // Final ς folds to σ and ß stays, as in FTS5. One deliberate difference: NFKD also folds full-width Latin
  // ("ｗａｔｅｒ", typed on Chinese and Japanese keyboards) to "water", which FTS5 keeps apart.
  function fold(s) {
    return String(s).toLowerCase().normalize('NFKD').replace(LATIN_MARKS, '$1').normalize('NFC').replace(/ς/g, 'σ');
  }

  // Intl.Segmenter is in WebView2, WKWebView (macOS 14+) and WebKitGTK; the fallback below covers older engines
  // and any engine whose constructor throws.
  let seg;   // made once; null where Intl.Segmenter is missing or unusable
  function segmenter() {
    if (seg === undefined) {
      try { seg = typeof Intl !== 'undefined' && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: 'word' }) : null }
      catch (e) { seg = null }
    }
    return seg;
  }

  // Words of a text, folded. Segment first, then split each segment wherever there's no letter, mark or digit:
  // the segmenter keeps "water's", "first_aid" and "e.coli" whole, but here they split as they always have
  // (water + s, first + aid, e + coli), and ZWJ, ZWNJ and soft hyphens separate words, as in FTS5.
  // Folding comes after segmenting, so the segmenter sees the text as typed. Every segment is kept and that
  // split drops the spaces and punctuation, rather than trusting isWordLike: JavaScriptCore marks numbers
  // such as 112 as not word-like, V8 does not.
  // Without Intl.Segmenter that split is all there is: every script that uses spaces works, but a run of
  // Chinese or Thai stays one word.
  function splitWords(text) {
    const t = String(text), s = segmenter();
    const raw = s ? Array.from(s.segment(t), x => x.segment) : [t];
    const out = [];
    for (const w of raw) for (const part of w.split(NOT_WORD)) { const f = fold(part); if (f) out.push(f) }
    return out;
  }

  // Words worth searching for, counted in characters rather than UTF-16 units: words in scripts without spaces at
  // any length (水, 净化); two-letter words in scripts without case (आग, אש, دم); otherwise three or more, as before.
  function keep(w) {
    const n = Array.from(w).length;
    return NO_SPACES.test(w) || n > 2 || (n === 2 && /\p{L}/u.test(w) && !/\p{Ll}/u.test(w));
  }
  function queryWords(q, stop) {
    return splitWords(q).filter(w => keep(w) && !(stop && stop.has(w)));
  }

  // A test for one piece of text: does a query word start one of its words? For scripts without spaces,
  // is the word anywhere in it? No RegExp is built from what was typed.
  function matcher(text) {
    const words = splitWords(text), whole = fold(text);
    return w => NO_SPACES.test(w) ? whole.includes(w) : words.some(h => h.startsWith(w));
  }

  // Topic search, scored as before: a word found in a topic's title, short line or keywords counts 1,
  // a word found in one of its choices counts 1.5; topics within 60% of the best score, top 3.
  // A choice's "urgent" phrases ("not breathing") pick that choice for its topic whenever the search names one,
  // even if another choice matches more words ("fractured neck and not breathing"). They don't change the score.
  const cache = new WeakMap();   // topics are replaced, never edited in place
  const wordLists = list => (list || []).map(splitWords).filter(p => p.length);
  function topicMatchers(t) {
    let m = cache.get(t);
    if (!m) {
      const shown = (t.choices || []).filter(c => !c.goto);
      m = { hay: matcher([t.title, t.short, ...(t.keywords || [])].join(' ')),
            choices: shown.map(c => ({ c, has: matcher(c.label + ' ' + (c.hint || '')) })),
            urgent: shown.filter(c => c.urgent).map(c => ({ c, phrases: c.urgent.map(splitWords).filter(p => p.length) })),
            phrases: shown.filter(c => c.phrases || c.weak).map(c => ({ c,
              phrases: wordLists(c.phrases), weak: wordLists(c.weak), who: wordLists(c.who),
              own: new Set(splitWords(c.label + ' ' + (c.hint || ''))),
              beside: new Set(splitWords([c.label, c.hint || '', ...(c.alongside || [])].join(' '))),
              context: wordLists(c.context), unless: wordLists(c.unless) })) };
      cache.set(t, m);
    }
    return m;
  }
  // Does a phrase's words appear in order, as whole words, among all the search's words (stop words included)?
  function names(all, p) {
    return all.some((_, i) => p.every((w, j) => all[i + j] === w));
  }
  // Everyday words that never stop a phrase from counting, besides the search's stop words: pronouns, helping verbs,
  // question words and filler ("my water broke what should we do"). Words like down, through and back are not here,
  // because they change what a phrase means ("baby coming down with a fever"); a choice lists the other meanings that
  // these words would let through in "unless" ("our water", "baby coming from"). Numbers pass too, alone or with a
  // unit ("5", "5mins", "38wks").
  const PLAIN = new Set((
    'mine myself yours yourself us ours ourselves herself he itself they them their theirs these those whom whose ' +
    'whatever some any every each all both such but nor yet because whether whenever while as then than am were be ' +
    'been being has had having did doing done would shall should could may might must ought gonna wanna gotta needs ' +
    'gets getting go goes going went re ve ll d m im ive id youre theyre weve dont cant wont didnt doesnt isnt ' +
    'arent wasnt werent hasnt havent hadnt couldnt shouldnt wouldnt aint thats whats wheres hows theres heres shes ' +
    'hes never always often sometimes already still just only even also too very really quite now here there today ' +
    'tonight yesterday soon later again ever almost maybe perhaps please pls plz thanks thank ok okay yes yeah oh ' +
    'omg wtf idk asap rn next r u ur wat wut shud shld supposed expect pretty sure guess probably want wants help ' +
    'hey hi hello um uh god sorry at by about like isn aren wasn weren didn doesn hasn haven hadn couldn shouldn ' +
    'wouldn ain let lets himself themselves').split(' '));
  const NUMBER = /^\d+(st|nd|rd|th|am|pm|cm|s|h|secs?|mins?|minutes?|hrs?|hours?|days?|wks?|weeks?)?$/;
  // Where a search names entries of a list: the positions they cover, and their words.
  function spans(all, list) {
    const at = new Set(), found = [];
    for (const p of list) for (let i = 0; i + p.length <= all.length; i++)
      if (p.every((w, j) => all[i + j] === w)) { p.forEach((_, j) => at.add(i + j)); found.push(...p) }
    return { at, found };
  }
  // A choice's phrases count only in context: the search names one (or a weak phrase), names none of its "unless"
  // entries, and every other word is everyday (PLAIN, a number or a stop word), part of a "context" entry the search
  // names, a word of the choice's label or hint, or, next to a full phrase only, an "alongside" word. "the baby is
  // coming" counts; "the baby is coming down with a fever" doesn't, and a word nobody foresaw leaves the search ranked
  // as without the fields. Returns the words found for the choice (phrase and context words), and the search's other
  // words ("bleeding", "flood"): guides that find those stay listed.
  function namedWords(all, words, { phrases, weak, who, own, beside, context, unless }, stop) {
    // A weak phrase right after one of "who" is a full phrase: "my water broke", "wife s water broke".
    const strong = spans(all, [...phrases, ...weak.flatMap(p => who.map(w => [...w, ...p]))]);
    const loose = spans(all, weak), near = spans(all, context);
    const plain = w => PLAIN.has(w) || NUMBER.test(w) || !!(stop && stop.has(w));
    // Each word must stand where a phrase or context entry was named ("no water" after "my water broke" does not).
    const fits = (w, i) => strong.at.has(i) || loose.at.has(i) || near.at.has(i) || plain(w) || own.has(w) ||
      (strong.at.size > 0 && beside.has(w));
    const none = !(strong.at.size || loose.at.size) || unless.some(p => names(all, p)) || !all.every(fits);
    if (none) return { hit: [], also: [] };
    // With only a weak phrase, the guides its own words find stay listed too ("water broke last night": tap water).
    const hit = [...strong.found, ...loose.found, ...near.found], kept = strong.at.size ? hit : near.found;
    return { hit, also: words.filter(w => !kept.includes(w) && !plain(w)) };
  }
  function rankTopics(q, topics, stop) {
    const words = queryWords(q, stop);
    if (!words.length || !topics) return [];
    const all = splitWords(q), out = [], also = new Set(), found = new Map(), phrased = new Set();
    for (const t of topics) {
      const m = topicMatchers(t);
      // A choice's "phrases" ("my water broke") count their words as found for that choice and its guide, but only when
      // the search names the whole phrase in context; on their own, "water" and "broke" still point elsewhere.
      const named = new Map(m.phrases.map(x => {
        const { hit, also: more } = namedWords(all, words, x, stop);
        more.forEach(w => also.add(w));
        if (hit.length) phrased.add(t);
        return [x.c, hit];
      }));
      const inNamed = w => [...named.values()].some(ws => ws.includes(w));
      const s = words.filter(w => m.hay(w) || inNamed(w)).length;
      let best = null, bs = 0, bf = [];
      for (const { c, has } of m.choices) {
        const ws = named.get(c) || [], f = words.filter(w => has(w) || ws.includes(w));
        if (f.length > bs || (ws.length && f.length === bs)) { bs = f.length; best = c; bf = f }    // a choice whose phrase the search names wins a tie
      }
      found.set(t, bf);   // the words the shown choice found
      const u = m.urgent.find(x => x.phrases.some(p => names(all, p)));
      if (u) best = u.c;
      if (s || bs) out.push({ t, c: best, s: s + bs * 1.5, u: !!u });
    }
    out.sort((a, b) => phrased.has(b.t) - phrased.has(a.t) || b.s - a.s);   // a guide a phrase picked comes first
    // When a phrase picks the first guide, a guide whose shown choice finds the search's other words follows it, even
    // below the cut:
    // "umbilical cord bleeding" shows the pregnancy choice first and Bleeding after it. Without a phrase, as before.
    const kept = o => phrased.has(out[0]?.t) && o !== out[0] && !o.u && found.get(o.t).some(w => also.has(w));
    const shown = [out[0], ...out.filter(kept), ...out.filter(o => o !== out[0] && !kept(o) && o.s >= out[0].s * 0.6)]
      .filter(Boolean);
    // A guide whose urgent phrase the search names comes first, even below the cut ("unconscious in the flood water").
    // Without one, the list is exactly as before.
    const urgent = out.filter(o => o.u);
    return [...urgent, ...shown.filter(o => !o.u)].slice(0, 3).map(({ t, c, s }) => ({ t, c, s }));
  }

  root.SearchWords = Object.freeze({ fold, splitWords, queryWords, matcher, rankTopics, hasSegmenter: () => !!segmenter() });
})(globalThis);
