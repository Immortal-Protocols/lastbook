"""lookup_comms, bundled reference citations, and Morse encode.

Needs no library and no network. Never packaged.
"""
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import comms, morse  # noqa: E402
from engine.comms_data import TOPICS, all_entries  # noqa: E402
from engine.comms_data.equipment_rows import ROWS as EQUIPMENT_ROWS  # noqa: E402
import assistant  # noqa: E402


# --------------------------------------------------------------------------- Morse
# A reference decoder used only in tests: invert the ITU table and walk timings
# back to marks, then to text. Production decode() stays unimplemented.

def _invert():
    letters = {v: k for k, v in morse.letters_table().items()}
    for ch, sign in morse.LETTERS.items():
        letters.setdefault(sign, ch)
    pro = {v: k for k, v in morse.PROSIGNS.items()}
    return letters, pro


def reference_decode_morse(marks):
    """Decode a Morse string ('...' '---' words as ' / ') back to text."""
    letters, pro = _invert()
    marks = (marks or '').strip()
    if not marks:
        return ''
    if marks in pro:
        return pro[marks]
    words = []
    for word in marks.split(' / '):
        chars = []
        for sign in word.split(' '):
            if not sign:
                continue
            if sign in pro and sign not in letters:
                chars.append(pro[sign])
            elif sign in letters:
                chars.append(letters[sign])
            else:
                chars.append('?')
        words.append(''.join(chars))
    return ' '.join(words)


def reference_decode_timings(seq):
    """Rebuild a Morse mark string from a timings list, then decode it."""
    marks = []
    letter = []
    for item in seq:
        if item['kind'] == 'tone':
            letter.append('.' if item.get('mark') == '.' or item.get('units') == 1 else '-')
        else:
            units = item['units']
            if units <= 1:
                continue  # intra-character gap
            marks.append(''.join(letter))
            letter = []
            if units >= 6:
                marks.append('/')
    if letter:
        marks.append(''.join(letter))
    # 'SOS' prosign is one character: no letter gaps inside ...---...
    pieces, word = [], []
    for m in marks:
        if m == '/':
            pieces.append(' '.join(word))
            word = []
        else:
            word.append(m)
    if word:
        pieces.append(' '.join(word))
    return reference_decode_morse(' / '.join(pieces))


class MorseEncode(unittest.TestCase):
    def test_sos_is_the_distress_prosign(self):
        r = morse.encode('SOS')
        self.assertEqual(r['morse'], '...---...')
        self.assertTrue(r['prosign'])
        # With letter spaces, S O S is a different (non-distress) grouping.
        spaced = morse.encode('S O S')
        self.assertEqual(spaced['morse'], '... / --- / ...')
        self.assertFalse(spaced['prosign'])

    def test_round_trip_against_reference_decoder(self):
        samples = [
            'SOS', 'CQ DE K1ABC', 'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG',
            'WAIT 10', 'QTH 40.5N', 'HELLO, WORLD?',
        ]
        for text in samples:
            coded = morse.encode(text)
            back = reference_decode_morse(coded['morse'])
            if text == 'SOS':
                self.assertEqual(back, 'SOS')
            else:
                # Punctuation comes back as the ITU characters; letters and figures
                # must survive. Spaces are word gaps.
                self.assertEqual(back, text.upper().replace(',', ','))
            # Timings also round-trip (the decoder is test-only).
            seq = morse.timings(text, wpm=20)
            from_times = reference_decode_timings(seq)
            self.assertEqual(from_times, back, text)

    def test_unit_length_paris_standard(self):
        # 20 WPM → 60 ms per unit (1.2 / 20 seconds).
        self.assertAlmostEqual(morse.unit_seconds(20) * 1000, 60.0)
        e = morse.timings('E', wpm=20)
        self.assertEqual(e[0], {'kind': 'tone', 'units': 1, 'ms': 60, 'mark': '.'})

    def test_utf8_typography_is_normalized_and_unknowns_are_skipped(self):
        r = morse.encode('“CQ” — café')
        # Curly quotes become straight quotes; an em dash becomes a hyphen; é is skipped.
        self.assertTrue(any('é' in ch for ch in r['skipped']))
        self.assertIn('-.-.', r['morse'])   # C
        self.assertIn('--.-', r['morse'])   # Q
        self.assertIn('-....-', r['morse'])  # hyphen

    def test_decode_hook_is_reserved(self):
        with self.assertRaises(NotImplementedError) as ctx:
            morse.decode(samples=b'', sample_rate=8000, source='mic')
        self.assertIn('not in this build', str(ctx.exception))

    def test_web_table_matches_python(self):
        js = (ROOT / 'web' / 'morse.js').read_text(encoding='utf-8')
        # The practice page embeds the same ITU letters object the engine uses.
        m = re.search(r'const LETTERS = (\{.*?\});', js, re.S)
        self.assertIsNotNone(m)
        table = json.loads(m.group(1))
        self.assertEqual(table, morse.letters_table())


class CommsLookup(unittest.TestCase):
    def test_topics_and_unique_ids(self):
        self.assertIn('equipment', TOPICS)
        self.assertIn('email', TOPICS)
        ids = [e['id'] for e in all_entries()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 35)
        self.assertEqual(len(EQUIPMENT_ROWS), 108)

    def test_frequency_and_channel_tables(self):
        cases = {
            '146.52': 'ham-calling-simplex',
            '146.520': 'ham-calling-simplex',
            'CB 9': 'cb-channels',
            'FRS 2': 'frs-channels',
            '121.5': 'aviation-emergency',
            '156.8': 'marine-vhf',
            '162.55': 'noaa-weather-radio',
        }
        for q, expect in cases.items():
            hits = comms.lookup(q, limit=3)['hits']
            self.assertTrue(hits, q)
            self.assertEqual(hits[0]['id'], expect, (q, [h['id'] for h in hits]))

    def test_emergency_rules_and_no_authority(self):
        r = comms.lookup('97.403', limit=3)
        self.assertEqual(r['hits'][0]['id'], 'part97-403-405')
        text = r['hits'][0]['text']
        self.assertIn('any means of radiocommunication at its disposal', text)
        self.assertIn('immediate safety of human life', text)
        gov = comms.lookup('no government', limit=3)
        self.assertEqual(gov['hits'][0]['id'], 'no-functioning-government')
        gtext = gov['hits'][0]['text']
        self.assertIn('97.403', gtext)
        self.assertIn('MAYDAY', gtext)
        # Plain operational facts, not a sermon.
        self.assertNotIn('you should never', gtext.lower())

    def test_email_over_radio_and_winlink_modes(self):
        r = comms.lookup('winlink VARA Pactor radio-only', topic='email', limit=5)
        ids = [h['id'] for h in r['hits']]
        self.assertIn('winlink-architecture', ids)
        self.assertIn('winlink-modes', ids)
        self.assertIn('winlink-clients-offline', ids)
        modes = next(h for h in r['hits'] if h['id'] == 'winlink-modes')['text']
        for needle in ('VARA HF', 'VARA FM', 'ARDOP', 'Pactor', 'FCC 23-93', 'Packet (AX.25)'):
            self.assertIn(needle, modes)
        arch = next(h for h in r['hits'] if h['id'] == 'winlink-architecture')['text']
        self.assertIn('Peer-to-peer', arch)
        self.assertIn('Radio-only', arch)
        self.assertIn('Winlink Express', arch)
        self.assertIn('Pat', arch)

    def test_morse_encode_via_lookup(self):
        r = comms.lookup('encode SOS')
        self.assertIsNotNone(r['encode'])
        self.assertEqual(r['encode']['morse']['morse'], '...---...')
        self.assertEqual(r['hits'][0]['topic'], 'signaling')

    def test_equipment_inventory_and_interop(self):
        r = comms.lookup('PRC-25', limit=4)
        ids = [h['id'] for h in r['hits']]
        self.assertEqual(ids[0], 'equipment-inventory-match')
        self.assertIn('equipment-interop', ids)
        self.assertIn('PRC-25', r['hits'][0]['text'] or r['hits'][0]['title'])
        # Interop states the real limits: no 146.52, no 52.525 on 50 kHz steps.
        inter = comms.lookup('will PRC-25 talk to 146.52', topic='equipment', limit=4)
        blob = '\n'.join(h['text'] for h in inter['hits'])
        self.assertIn('146.520', blob)
        self.assertIn('52.525', blob)
        manuals = comms.lookup('TM 11-333', topic='equipment', limit=4)
        mids = [h['id'] for h in manuals['hits']]
        self.assertIn('manuals-pd-candidates', mids)
        mtext = next(h for h in manuals['hits'] if h['id'] == 'manuals-pd-candidates')['text']
        for needle in ('TM 11-333', 'TM 11-5820-398-12', 'TM 11-5820-919-12', '47 CFR Part 97', 'Do not bundle'):
            self.assertIn(needle, mtext)
        # A bare frequency must not dump the 108-row catalog on top of the calling table.
        freq = comms.lookup('146.52', limit=3)
        self.assertEqual(freq['hits'][0]['id'], 'ham-calling-simplex')
        self.assertFalse(any(h['id'] == 'equipment-inventory-match' for h in freq['hits']))

    def test_miss_and_utf8_source_text(self):
        r = comms.lookup('xyzzyqwxplughzz')
        self.assertEqual(r['count'], 0)
        self.assertIn('No bundled comms reference', r['miss'])
        # Section signs and other non-ASCII must be real UTF-8, not mojibake.
        blob = '\n'.join(e['text'] for e in all_entries())
        self.assertIn('§ 97.403', blob)
        self.assertNotIn('Â', blob)
        blob.encode('utf-8')

    def test_no_http_urls_in_web_morse_page(self):
        text = (ROOT / 'web' / 'morse.js').read_text(encoding='utf-8')
        self.assertNotRegex(text, r'https?://')


class CommsToolAndCitations(unittest.TestCase):
    def setUp(self):
        self.saved = assistant.S
        assistant.S = mock.Mock()
        assistant.S.catalog.return_value = {'by_id': {}}

    def tearDown(self):
        assistant.S = self.saved

    def test_tool_is_registered(self):
        names = [t['function']['name'] for t in assistant.TOOLS]
        self.assertIn('lookup_comms', names)
        self.assertIn('lookup_comms', assistant.SYSTEM)
        self.assertIn('97.403', assistant.SYSTEM)

    def test_run_tool_citations_validate(self):
        sess = assistant.Session()
        text, summary = assistant.run_tool('lookup_comms', {'query': '97.403'}, sess, [])
        self.assertGreaterEqual(summary['count'], 1)
        self.assertIn('[S1]', text)
        self.assertIn('97.403', text)
        keys = list(sess.sources)
        self.assertTrue(keys)
        for k, src in sess.sources.items():
            self.assertEqual(src['kind'], 'reference')
            self.assertTrue(assistant.source_known(src), src)
            self.assertTrue(src.get('title') and src.get('publisher') and src.get('section'))
        # The model citing those keys is accepted; a made-up key is not.
        answer = 'Any means available when life is immediately at risk [S1].'
        out, valid, invalid = assistant.validate_citations(answer, sess)
        self.assertEqual(invalid, [])
        self.assertIn('S1', valid)
        _, _, bad = assistant.validate_citations('Made-up source [S99].', sess)
        self.assertEqual(bad, ['S99'])

    def test_reference_sources_do_not_collapse_together(self):
        sess = assistant.Session()
        assistant.run_tool('lookup_comms', {'query': 'Winlink VARA', 'topic': 'email'}, sess, [])
        refs = [s for s in sess.sources.values() if s['kind'] == 'reference']
        self.assertGreaterEqual(len(refs), 2)
        self.assertEqual(len({s['ref_id'] for s in refs}), len(refs))

    def test_source_known_rejects_an_incomplete_reference(self):
        self.assertFalse(assistant.source_known({'kind': 'reference', 'title': 'X'}))
        self.assertTrue(assistant.source_known({
            'kind': 'reference', 'title': '47 CFR 97.403',
            'publisher': 'FCC', 'section': '47 CFR 97.403',
        }))

    def test_morse_encode_argument(self):
        sess = assistant.Session()
        text, summary = assistant.run_tool(
            'lookup_comms', {'query': 'morse', 'encode': 'SOS'}, sess, [])
        self.assertIn('...---...', text)
        self.assertGreaterEqual(summary['count'], 1)


if __name__ == '__main__':
    unittest.main()
