"""Read aloud (web/speak.js): text pulled from a PDF is cleaned so it reads as sentences, then split into short pieces that
engines speak reliably, losing no words. Runs speak.js under Node. Needs Node on PATH; skipped without it. Never packaged."""
import json, re, shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')
RUN = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const Speak = new Function('$', 'navigator', src + '\nreturn Speak;')(() => null, { language: 'en-US' });
const out = JSON.parse(process.argv[2]).map(t => ({ clean: Speak._speakable(t), pieces: Speak._pieces(t) }));
process.stdout.write(JSON.stringify(out));
"""
# Shaped like the text tools/libq.py gives for a manual page: a running head, a page number alone, bullets, a word broken
# across lines, and a long sentence.
PAGE = """     NEW WHERE THERE IS NO DOCTOR: ADVANCE CHAPTERS
10   FIRST AID


   Tourniquets
   Use a tourniquet only as a last resort, when you are willing to risk the loss
   of an arm or leg in order to save a person's life.
      Use tourniquets only when:
   ··A limb is cut off or is so mangled that it clearly cannot be saved.
   ●  Heavy bleeding that does not slow down from an arm or leg with
      direct pressure. (Have you tried pressing harder first?)
   Other chemicals are not recom-
   mended and should not be used.
   """ + 'This sentence goes on and on, ' * 12 + """and ends here.

                                                                      27
"""


def words(s):
    return re.findall(r"[\w']+", s)


@unittest.skipUnless(NODE, 'needs Node')
class Speakable(unittest.TestCase):
    def run_js(self, *texts):
        r = subprocess.run([NODE, '-e', RUN, str(ROOT / 'web/speak.js'), json.dumps(texts)], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    def test_cleaned_for_listening(self):
        (got,) = self.run_js(PAGE)
        clean = got['clean']
        self.assertIn('recommended and should not be used', clean)        # the broken word is whole again
        self.assertNotIn('··', clean)
        self.assertNotIn('●', clean)
        self.assertNotRegex(clean, r'(^|\n)\s*27\s*($|\n)')                # the page number alone is gone
        self.assertIn('Use a tourniquet only as a last resort, when you are willing to risk the loss of an arm', clean)   # lines joined

    def test_pieces_are_short_and_lose_nothing(self):
        (got,) = self.run_js(PAGE)
        self.assertTrue(got['pieces'])
        self.assertTrue(all(len(p) <= 220 for p in got['pieces']), [len(p) for p in got['pieces']])
        self.assertEqual(words(' '.join(got['pieces'])), words(got['clean']))
        self.assertIn('(Have you tried pressing harder first?)', ' '.join(got['pieces']))

    def test_nothing_to_say(self):
        a, b = self.run_js('', '   12   \n\n  ●  \n')
        self.assertEqual(a['pieces'], [])
        self.assertEqual(b['pieces'], [])

    def test_other_scripts(self):
        (got,) = self.run_js('Agua segura: hiérvala un minuto. Después, déjela enfriar.')
        self.assertEqual(got['pieces'], ['Agua segura: hiérvala un minuto. Después, déjela enfriar.'])


if __name__ == '__main__':
    unittest.main()
