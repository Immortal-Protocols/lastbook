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

  // Another form of the same English word: "tourniquets" and "tourniquet", "fainting" and "fainted", "choked" and
  // "choking". forms(w) is the word itself, then what is left when one common ending comes off: a plural -s, -es
  // (boxes, stitches) or -ies (batteries), and -ed or -ing, also with the dropped e put back (choking: choke) or a
  // doubled letter undone (stopped: stop). Two words are forms of each other when their lists share an entry.
  // Irregular forms (stung, frozen) are not covered.
  function forms(w) {
    const out = [w], add = (f, min) => { if (f.length >= min && !out.includes(f)) out.push(f) };
    const cut = end => w.endsWith(end) ? w.slice(0, -end.length) : null;
    let f;
    if ((f = cut('ies')) !== null) add(f + 'y', 4);
    else if ((f = cut('es')) !== null && /(?:s|x|z|ch|sh)$/.test(f)) add(f, 3);
    else if ((f = cut('s')) !== null && !f.endsWith('s')) add(f, 3);
    for (const end of ['ed', 'ing']) {
      if ((f = cut(end)) === null) continue;
      add(f, 4); add(f + 'e', 4);
      if (/([^aeiou])\1$/.test(f)) add(f.slice(0, -1), 4);
    }
    return out;
  }
  // A test for one piece of text: is a query word another form of one of its words? A form that is a stop word
  // doesn't count ("cans" is not "can"). Scripts without spaces have no such endings.
  function formMatcher(text) {
    const have = new Set(splitWords(text).flatMap(forms));
    return (w, stop) => !NO_SPACES.test(w) && forms(w).some(f => have.has(f) && !(stop && stop.has(f)));
  }

  // Topic search, scored as before: a word found in a topic's title, short line or keywords counts 1,
  // a word found in one of its choices counts 1.5; topics within 60% of the best score, top 3.
  // A choice's "urgent" phrases ("not breathing") pick that choice for its topic whenever the search names one,
  // even if another choice matches more words ("fractured neck and not breathing"). They don't change the score.
  // Only a search that finds nothing at all ("tourniquets", "he is fainting") is tried again by word form, scored
  // the same way. A search that finds any guide gives exactly what it gave before.
  const cache = new WeakMap();   // topics are replaced, never edited in place
  const wordLists = list => (list || []).map(splitWords).filter(p => p.length);
  function topicMatchers(t) {
    let m = cache.get(t);
    if (!m) {
      const shown = (t.choices || []).filter(c => !c.goto);
      const hay = [t.title, t.short, ...(t.keywords || [])].join(' '), text = c => c.label + ' ' + (c.hint || '');
      m = { hay: matcher(hay), hayForm: formMatcher(hay),
            choices: shown.map(c => ({ c, has: matcher(text(c)), hasForm: formMatcher(text(c)) })),
            urgent: shown.filter(c => c.urgent || c.weakUrgent).map(c => ({ c, phrases: wordLists(c.urgent),
              weak: wordLists(c.weakUrgent), own: new Set(splitWords(text(c))) })),
            phrases: shown.filter(c => c.phrases || c.weak).map(c => ({ c,
              phrases: wordLists(c.phrases), weak: wordLists(c.weak), who: wordLists(c.who),
              own: new Set(splitWords(text(c))),
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
    const at = new Set(), found = [], starts = [];
    for (const p of list) for (let i = 0; i + p.length <= all.length; i++)
      if (p.every((w, j) => all[i + j] === w)) {
        p.forEach((_, j) => at.add(i + j));
        found.push(...p);
        starts.push([i, p]);
      }
    return { at, found, starts };
  }
  // A choice's phrases count only in context: the search names one (or a weak phrase), names none of its "unless"
  // entries, and every other word is everyday (PLAIN, a number or a stop word), part of a "context" entry the search
  // names, a word of the choice's label or hint, or, next to a full phrase only, an "alongside" word. "the baby is
  // coming" counts; "the baby is coming down with a fever" doesn't, and a word nobody foresaw leaves the search ranked
  // as without the fields. Returns the words found for the choice (phrase and context words), and the search's other
  // words ("bleeding", "flood"): guides that find those stay listed.
  function namedWords(all, words, { phrases, weak, who, own, beside, context, unless }, stop) {
    const loose = spans(all, weak), near = spans(all, context), strong = spans(all, phrases);
    // A weak phrase right after one of "who" is a full phrase: "my water broke", "wife s water broke".
    for (const [i, p] of loose.starts) for (const w of who)
      if (i >= w.length && w.every((x, j) => all[i - w.length + j] === x)) {
        for (let j = i - w.length; j < i + p.length; j++) strong.at.add(j);
        strong.found.push(...w, ...p);
      }
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
  // Words that start an object after "pass out" ("pass out the cots", "passing out to neighbors"), though they are
  // stop words or everyday words; and words that never do, though they are neither ("passing out after giving blood").
  const OBJECT_START = new Set('a an the this that these those them some any all each every both extra our their your its to for of'.split(' '));
  const NO_OBJECT = new Set('after before during until since because'.split(' '));
  // Does the search name one of a choice's urgent phrases? An "urgent" phrase always counts (true). A "weakUrgent"
  // phrase also means something else ("pass out food"), so it counts only when no object can follow it: it ends the
  // search, or the next word is everyday (PLAIN or a stop word, but not one of OBJECT_START), one of NO_OBJECT, or a
  // number with a unit ("passing out", "passing out when i stand", "keeps passing out what do i do", "passing out
  // 5mins"). Followed by anything else ("pass out food", "pass out 50 meals"), it returns 'maybe', and rankTopics
  // lists the choice second instead of first.
  function urgentNamed(all, { phrases, weak }, stop) {
    if (phrases.some(p => names(all, p))) return true;
    // A number is an amount ("pass out 50 meals") unless it has a unit, in the word or right after it ("5 minutes ago").
    const time = i => NUMBER.test(all[i]) && (!/^\d+$/.test(all[i]) || NUMBER.test(all[i] + (all[i + 1] || '')));
    const none = i => i >= all.length || NO_OBJECT.has(all[i]) || time(i) ||
      ((PLAIN.has(all[i]) || !!(stop && stop.has(all[i]))) && !OBJECT_START.has(all[i]));
    const ends = weak.flatMap(p => all.map((_, i) => i).filter(i => p.every((w, j) => all[i + j] === w)).map(i => i + p.length));
    return ends.some(none) || (ends.length ? 'maybe' : false);
  }
  // Words of the urgent phrases a search names that their choice's own label and hint don't use, where they appear
  // nowhere else in the search: "out" in "passing out" is not the "out" of a power outage. They pick the choice; they
  // don't score. "breathing" in "not breathing" is the choice's own word and scores as before.
  function urgentWords(all, topics) {
    const at = new Set();
    for (const t of topics) {
      for (const x of topicMatchers(t).urgent) for (const p of [...x.phrases, ...x.weak])
        for (let i = 0; i + p.length <= all.length; i++)
          if (p.every((w, j) => all[i + j] === w)) p.forEach((w, j) => { if (!x.own.has(w)) at.add(i + j) });
    }
    return new Set(all.filter((w, i) => at.has(i) && all.every((v, k) => v !== w || at.has(k))));
  }
  function rankTopics(q, topics, stop) {
    if (!topics) return [];
    const all = splitWords(q), every = queryWords(q, stop);
    if (!every.length) return [];
    const named = urgentWords(all, topics);
    let words = every.filter(w => !named.has(w));
    const score = byForm => {
      const out = [], also = new Set(), found = new Map(), phrased = new Set();
      for (const t of topics) {
        const m = topicMatchers(t), hay = byForm ? w => m.hayForm(w, stop) : m.hay;
        const named = byForm ? new Map() : new Map(m.phrases.map(x => {
          const { hit, also: more } = namedWords(all, words, x, stop);
          more.forEach(w => also.add(w));
          if (hit.length) phrased.add(t);
          return [x.c, hit];
        }));
        const inNamed = w => [...named.values()].some(ws => ws.includes(w));
        const s = words.filter(w => hay(w) || inNamed(w)).length;
        let best = null, bs = 0, bf = [];
        for (const { c, has, hasForm } of m.choices) {
          const match = byForm ? w => hasForm(w, stop) : has;
          const ws = named.get(c) || [], f = words.filter(w => match(w) || ws.includes(w));
          if (f.length > bs || (ws.length && f.length === bs)) { bs = f.length; best = c; bf = f }
        }
        found.set(t, bf);
        const said = m.urgent.map(x => [x, urgentNamed(all, x, stop)]);
        const u = said.find(([, v]) => v === true)?.[0], maybe = !u && said.find(([, v]) => v === 'maybe')?.[0];
        if (u) best = u.c;
        // a named phrase counts even if no single word does
        if (s || bs || u || maybe) out.push({ t, c: best, s: s + bs * 1.5, u: !!u, maybe: maybe && maybe.c });
      }
      return { out, also, found, phrased };
    };
    // A search that finds no guide by its words is tried again by word form ("tourniquets"). If it still finds none and
    // names a weak urgent phrase that may mean something else ("pass out rice"), it is ranked with the phrase's words,
    // as without the field, and the urgent choice is listed second.
    let { out, also, found, phrased } = score(false);
    if (!out.some(o => o.s)) ({ out, also, found, phrased } = score(true));
    if (!out.some(o => o.s) && out.some(o => o.maybe) && words.length < every.length) {
      words = every;
      ({ out, also, found, phrased } = score(false));
    }
    out.sort((a, b) => phrased.has(b.t) - phrased.has(a.t) || b.s - a.s);
    const kept = o => phrased.has(out[0]?.t) && o !== out[0] && !o.u && found.get(o.t).some(w => also.has(w));
    const shown = [out[0], ...out.filter(kept), ...out.filter(o => o !== out[0] && !kept(o) && o.s >= out[0].s * 0.6)]
      .filter(Boolean);
    // A guide whose urgent phrase the search names comes first, even below the cut ("unconscious in the flood water").
    // Without one, the list is exactly as before.
    const urgent = out.filter(o => o.u);
    let list = [...urgent, ...shown.filter(o => !o.u)];
    // A weak urgent phrase that may mean something else ("pass out food") doesn't put its choice first, but the choice
    // is always listed, second at the latest. When its guide comes first anyway with another choice its words found
    // ("passing out chest pain": Sudden illness), the urgent choice follows it as a row of its own.
    const maybe = out.find(o => o.maybe), row = maybe && { ...maybe, c: maybe.maybe };
    if (maybe && list[0] !== maybe) list = [list[0], row, ...list.slice(1).filter(o => o !== maybe)];
    else if (maybe && !maybe.c) list = [row, ...list.slice(1)];
    else if (maybe && maybe.c !== maybe.maybe) list = [list[0], row, ...list.slice(1)];
    return list.slice(0, 3).map(({ t, c, s }) => ({ t, c, s }));
  }

  root.SearchWords = Object.freeze({ fold, splitWords, queryWords, matcher, rankTopics, hasSegmenter: () => !!segmenter() });
})(globalThis);
