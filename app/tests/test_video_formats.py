#!/usr/bin/env python3
"""tools/check_video_formats.py against a made-up library: formats read from MP4 and WebM files, and which H.264 copies count.

  python3 -B -m unittest app.tests.test_video_formats [-v]

Builds tiny files whose index is real and whose pictures are not, so no video library is needed. Never packaged."""
import contextlib, importlib.util, io, json, os, struct, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('check_video_formats', ROOT / 'tools' / 'check_video_formats.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def box(name, body=b''):
    return struct.pack('>I4s', 8 + len(body), name) + body


def big(name, body):   # a box with a 64-bit length
    return struct.pack('>I4sQ', 1, name, 16 + len(body)) + body


def trak(fmt):
    stsd = box(b'stsd', b'\0' * 4 + struct.pack('>I', 1) + struct.pack('>I4s', 16, fmt) + b'\0' * 8)
    return box(b'trak', box(b'tkhd', b'\0' * 84) + box(b'mdia', box(b'mdhd', b'\0' * 24) + box(b'minf', box(b'stbl', stsd))))


def mp4(*fmts, moov_last=False):
    ftyp, moov, mdat = box(b'ftyp', b'isom\0\0\2\0isom'), box(b'moov', box(b'mvhd', b'\0' * 100) + b''.join(trak(f) for f in fmts)), big(b'mdat', b'\x55' * 5000)
    return ftyp + mdat + moov if moov_last else ftyp + moov + mdat


def webm(codec):
    return b'\x1a\x45\xdf\xa3' + b'\0' * 40 + b'\x86' + bytes([0x80 | len(codec)]) + codec + b'\0' * 200


FILES = {
    'videos/a/av1.mp4': mp4(b'av01', b'mp4a', moov_last=True),
    'videos/a/av1-sound-first.mp4': mp4(b'mp4a', b'av01'),
    'videos/a/h264.mp4': mp4(b'avc1', b'mp4a'),
    'videos/a/vp9.webm': webm(b'V_VP9'),
    'videos/a/av1-no-copy.mp4': mp4(b'av01'),
    'videos/a/cut.mp4': mp4(b'av01', moov_last=True)[:-30],
    'videos/a/junk.mp4': b'not a video at all' * 100,
    'videos-external/b/vp9-wrong-size.mp4': mp4(b'vp09'),
}


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        lib = self.data / 'library-data'
        recs = []
        for i, (rel, body) in enumerate(FILES.items()):
            (lib / rel).parent.mkdir(parents=True, exist_ok=True)
            (lib / rel).write_bytes(body)
            recs.append({'id': f'v{i}', 'kind': 'video', 'path': rel})
        recs.append({'id': 'gone', 'kind': 'video', 'path': 'videos/a/not-on-this-computer.mp4'})
        recs.append({'id': 'doc', 'kind': 'pdf', 'path': 'documents/x.pdf'})
        (lib / 'catalog.json').write_text(json.dumps(recs))
        d = self.data / 'derived' / 'video-compat' / 'h264-v1'
        d.mkdir(parents=True)
        (d / 'one.mp4').write_bytes(b'c' * 100)
        (d / 'two.mp4').write_bytes(b'c' * 100)
        (self.data / 'outside.mp4').write_bytes(b'c' * 100)
        it = lambda f, n=100, src='av01', video='avc1': {'file': f, 'bytes': n, 'source_video': src, 'video': video}
        self.items = {
            'videos/a/av1.mp4': it('one.mp4'),
            'videos/a/av1-sound-first.mp4': it('two.mp4'),
            'videos/a/vp9.webm': it('two.mp4', src='vp09'),
            'videos/a/av1-no-copy.mp4': it('../../../outside.mp4'),          # not a plain file name
            'videos-external/b/vp9-wrong-size.mp4': it('one.mp4', n=99, src='vp09'),   # partial
            'videos/a/cut.mp4': it('one.mp4', video='hvc1'),                  # a copy that isn't H.264
        }
        self.write_manifest()

    def write_manifest(self, man=None):
        p = self.data / 'derived' / 'video-compat' / 'h264-v1' / 'manifest.json'
        p.write_text(json.dumps(man if man is not None else {'version': 'h264-v1', 'items': self.items}))

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = C.main(['--data', str(self.data), *extra])
        return code, out.getvalue()

    def test_formats_from_the_file_index(self):
        lib = self.data / 'library-data'
        self.assertEqual(C.formats(lib / 'videos/a/av1.mp4'), ['av01', 'mp4a'])   # index after the pictures
        self.assertEqual(C.formats(lib / 'videos/a/av1-sound-first.mp4'), ['mp4a', 'av01'])
        self.assertEqual(C.formats(lib / 'videos/a/h264.mp4'), ['avc1', 'mp4a'])
        self.assertEqual(C.formats(lib / 'videos/a/vp9.webm'), ['vp09'])
        self.assertEqual(C.formats(lib / 'videos/a/cut.mp4'), [])                  # index cut short
        self.assertEqual(C.formats(lib / 'videos/a/junk.mp4'), [])
        self.assertEqual(C.formats(lib / 'videos/a/missing.mp4'), [])

    def test_only_usable_copies_count(self):
        self.assertEqual(sorted(C.usable_copies(self.data)), ['videos/a/av1-sound-first.mp4', 'videos/a/av1.mp4', 'videos/a/vp9.webm'])

    def test_lists_what_needs_a_copy_and_fails_on_a_missing_one(self):
        code, out = self.run_tool()
        self.assertEqual(code, 1)
        self.assertIn('AV1  copy    videos/a/av1.mp4', out)
        self.assertIn('AV1  copy    videos/a/av1-sound-first.mp4', out)
        self.assertIn('VP9  copy    videos/a/vp9.webm', out)
        self.assertIn('AV1  NO COPY videos/a/av1-no-copy.mp4', out)
        self.assertIn('VP9  NO COPY videos-external/b/vp9-wrong-size.mp4', out)
        self.assertNotIn('h264.mp4', out)
        self.assertIn('8 videos on this computer, 5 in AV1 or VP9, 2 of those without a usable H.264 copy', out)
        self.assertIn('h264.mp4', self.run_tool('--all')[1])

    def test_passes_when_every_one_has_a_copy(self):
        lib = self.data / 'library-data'
        (lib / 'videos/a/av1-no-copy.mp4').unlink()
        (lib / 'videos-external/b/vp9-wrong-size.mp4').unlink()
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)

    def test_links_hard_links_and_bad_entries(self):
        d = self.data / 'derived' / 'video-compat' / 'h264-v1'
        os.link(self.data / 'outside.mp4', d / 'hard.mp4')                       # also a file outside the library
        self.items['videos/a/av1-no-copy.mp4'] = {'file': 'hard.mp4', 'bytes': 100, 'source_video': 'av01', 'video': 'avc1'}
        self.items['videos/a/junk.mp4'] = 'not an item'                          # skipped, as the server skips it
        self.write_manifest()
        self.assertEqual(sorted(C.usable_copies(self.data)), ['videos/a/av1-sound-first.mp4', 'videos/a/av1.mp4', 'videos/a/vp9.webm'])
        real = self.data / 'derived' / 'video-compat'
        moved = self.data / 'elsewhere'
        real.rename(moved)
        try:
            os.symlink(moved, real, target_is_directory=True)                    # the copies folder now leads elsewhere
        except OSError:
            self.skipTest('no right to make links here')
        self.assertEqual(C.usable_copies(self.data), {})

    def test_a_bad_manifest_counts_no_copies(self):
        for man in ([], {'version': 'h264-v2', 'items': self.items}, {'version': 'h264-v1', 'items': 5}, {'version': 'h264-v1', 'items': {'x': 5}}):
            self.write_manifest(man)
            self.assertEqual(C.usable_copies(self.data), {}, man)
        (self.data / 'derived' / 'video-compat' / 'h264-v1' / 'manifest.json').write_text('{')
        self.assertEqual(C.usable_copies(self.data), {})

    def test_no_library(self):
        with self.assertRaises(SystemExit):
            C.main(['--data', str(self.data / 'nowhere')])


if __name__ == '__main__':
    unittest.main()
