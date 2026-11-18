"""packaging/make_torrents.py: the torrents for the published files. Never shipped.
Each torrent is checked against a plain, separate computation of what BEP 3 (v1) and BEP 52 (v2) say it must hold.

Run:  python3 app/tests/test_torrents.py
"""
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT)]
spec = importlib.util.spec_from_file_location('make_torrents', ROOT / 'packaging' / 'make_torrents.py')
mt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mt)

BASE = 'https://downloads.lastbook.org'
BLOCK = 16 * 1024


def bdecode(b):
    def go(i):
        c = b[i:i + 1]
        if c == b'i':
            j = b.index(b'e', i)
            return int(b[i + 1:j]), j + 1
        if c == b'l':
            out, i = [], i + 1
            while b[i:i + 1] != b'e':
                v, i = go(i)
                out.append(v)
            return out, i + 1
        if c == b'd':
            out, i, last = {}, i + 1, None
            while b[i:i + 1] != b'e':
                k, i = go(i)
                assert last is None or k > last, 'keys out of order'
                last = k
                out[k], i = go(i)
            return out, i + 1
        j = b.index(b':', i)
        n = int(b[i:j])
        return b[j + 1:j + 1 + n], j + 1 + n
    v, end = go(0)
    assert end == len(b), 'bytes after the end'
    return v


def tree_layers(data, plen):
    """The whole v2 tree, the plain way: every 16 KiB block hashed, zero leaves out to a power of two that holds whole pieces."""
    leaves = [hashlib.sha256(data[i:i + BLOCK]).digest() for i in range(0, len(data), BLOCK)]
    n = 1
    while n < len(leaves):
        n *= 2
    if len(data) > plen:
        n = max(n, plen // BLOCK)
    layers = [leaves + [bytes(32)] * (n - len(leaves))]
    while len(layers[-1]) > 1:
        x = layers[-1]
        layers.append([hashlib.sha256(x[i] + x[i + 1]).digest() for i in range(0, len(x), 2)])
    return layers


def expect(data, plen):
    layers = tree_layers(data, plen)
    root = layers[-1][0]
    npieces = -(-len(data) // plen)
    height = (plen // BLOCK).bit_length() - 1
    layer = b''.join(layers[height][:npieces]) if len(data) > plen else b''
    v1 = b''.join(hashlib.sha1(data[i:i + plen]).digest() for i in range(0, len(data), plen))
    return root, layer, v1


class Fixture:
    def __init__(self, sizes):
        self.tmp = tempfile.TemporaryDirectory()
        Torrents.current.addCleanup(self.tmp.cleanup)
        self.files = Path(self.tmp.name) / 'published'
        self.out = Path(self.tmp.name) / 'torrents'
        self.files.mkdir()
        self.data = {}
        rnd = __import__('random').Random(7)
        packs, maps = [], []
        for i, size in enumerate(sizes):
            name = f'Lastbook-Map-T{i}.zip' if i % 2 else f'Lastbook-Test{i}.zip'
            data = rnd.randbytes(size)
            (self.files / name).write_bytes(data)
            self.data[name] = data
            f = {'name': name, 'url': f'{BASE}/{name}', 'size': size, 'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}
            (maps if i % 2 else packs).append(f)
        self.manifest = {'version': 1, 'packs': [{'id': 'test', 'title': 'Test', 'installed_bytes': 1, 'available': True, 'files': packs}],
                         'maps': [{'id': f'T{i}', 'title': f'T{i}', 'installed_bytes': 1, 'available': True, 'files': [f]} for i, f in enumerate(maps)],
                         'models': [{'id': 'm', 'file': 'model.gguf', 'url': 'https://huggingface.co/x/model.gguf', 'size': 1, 'sha256': '0' * 64, 'memory_bytes': 1}]}

    def build(self, **kw):
        with redirect_stdout(io.StringIO()):
            m = mt.manifest.validate(self.manifest)
            assert m is not None, 'the test manifest does not pass validate'
            return mt.build(m, self.files, self.out, progress=lambda name: (lambda d, t: None), **kw)

    def torrent(self, name):
        return bdecode((self.out / f'{name}.torrent').read_bytes())


class Torrents(unittest.TestCase):
    current = None

    def setUp(self):
        Torrents.current = self
        p = mock.patch.multiple(mt, MIN_PIECE=BLOCK, TARGET_PIECES=4)      # small pieces, so small files have several
        p.start()
        self.addCleanup(p.stop)

    def test_bencode(self):
        self.assertEqual(mt.bencode({'b': [1, 'x'], 'a': b'\x00', 'é': -3}), b'd1:a1:\x001:bli1e1:xe2:\xc3\xa9i-3ee')
        with self.assertRaises(TypeError):
            mt.bencode(True)

    def test_piece_length(self):
        with mock.patch.multiple(mt, MIN_PIECE=256 * 1024, TARGET_PIECES=4096):
            self.assertEqual(mt.piece_length(1), 256 * 1024)
            self.assertEqual(mt.piece_length(387_878_571_619), 64 << 20)       # the All pack: 5,780 pieces
            self.assertEqual(mt.piece_length(10 ** 15), mt.MAX_PIECE)
            for s in (1, 821_000_000, 7_691_528_852, 67_492_034_038):
                n = mt.piece_length(s)
                self.assertEqual(n & (n - 1), 0)
                self.assertTrue(-(-s // n) <= 4096 or n == mt.MAX_PIECE)

    def test_hashes_match_the_bep(self):
        # under one block, one block, between, one piece, a partial last piece, whole pieces, many pieces out to an odd count
        sizes = [100, BLOCK, BLOCK + 5, 4 * BLOCK, 4 * BLOCK + 1, 8 * BLOCK, 23 * BLOCK + 777]
        fx = Fixture(sizes)
        self.assertEqual(fx.build(), [])
        for name, data in fx.data.items():
            with self.subTest(size=len(data)):
                t = fx.torrent(name)
                info = t[b'info']
                plen = info[b'piece length']
                self.assertEqual(plen, mt.piece_length(len(data)))
                root, layer, v1 = expect(data, plen)
                self.assertEqual(info[b'name'], name.encode())
                self.assertEqual(info[b'length'], len(data))
                self.assertEqual(info[b'pieces'], v1)
                self.assertEqual(info[b'meta version'], 2)
                self.assertEqual(info[b'file tree'], {name.encode(): {b'': {b'length': len(data), b'pieces root': root}}})
                if len(data) > plen:
                    self.assertEqual(t[b'piece layers'], {root: layer})
                else:
                    self.assertNotIn(b'piece layers', t)
                self.assertEqual(t[b'url-list'], [f'{BASE}/{name}'.encode()])
                self.assertNotIn(b'creation date', t)
                self.assertNotIn(b'announce', t)

    def test_listing_and_magnets(self):
        fx = Fixture([5 * BLOCK + 3, 300])
        self.assertEqual(fx.build(trackers=('udp://tracker.example:1337/announce', 'https://t.example/announce')), [])
        listing = json.loads((fx.out / 'torrents.json').read_text())['torrents']
        self.assertEqual([x['name'] for x in listing], list(fx.data))           # packs, then maps; the model is left out
        for x in listing:
            raw = (fx.out / x['torrent']).read_bytes()
            t = bdecode(raw)
            info = mt.bencode(t[b'info'])
            self.assertIn(info, raw)                                            # the info dictionary as written, so the hashes are of the same bytes
            self.assertEqual(x['btih'], hashlib.sha1(info).hexdigest())
            self.assertEqual(x['btmh'], '1220' + hashlib.sha256(info).hexdigest())
            self.assertEqual(t[b'announce'], b'udp://tracker.example:1337/announce')
            self.assertEqual(t[b'announce-list'], [[b'udp://tracker.example:1337/announce'], [b'https://t.example/announce']])
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(x['magnet']).query)
            self.assertEqual(q['xt'], [f'urn:btih:{x["btih"]}', f'urn:btmh:{x["btmh"]}'])
            self.assertEqual(q['dn'], [x['name']])
            self.assertEqual(q['xl'], [str(x['size'])])
            self.assertEqual(q['ws'], [f'{BASE}/{x["name"]}'])
            self.assertEqual(len(q['tr']), 2)

    def test_pin_and_one_piece_length(self):
        fx = Fixture([10 * BLOCK + 1, 3 * BLOCK])
        self.assertEqual(fx.build(plen=4 * BLOCK), [])
        for x in json.loads((fx.out / 'torrents.json').read_text())['torrents']:
            t = fx.torrent(x['name'])
            root, _, _ = expect(fx.data[x['name']], 4 * BLOCK)
            self.assertEqual(t[b'info'][b'piece length'], 4 * BLOCK)
            self.assertEqual(x['pin'], {'torrent': {'url': f'{BASE}/{x["name"]}.torrent', 'pieces_root': root.hex(),
                                                    'infohash_v2': x['btmh'][4:], 'piece_length': 4 * BLOCK}})
            self.assertEqual(set(t), {b'info', b'url-list'} | ({b'piece layers'} if x['size'] > 4 * BLOCK else set()))       # no creator or date: the same bytes from any tool that builds the same info
        for bad in (0, 1, 3 * BLOCK, BLOCK // 2):
            with self.assertRaises(ValueError):
                mt.check_piece_length(bad)

    def test_same_output_every_time(self):
        fx = Fixture([9 * BLOCK + 11])
        name = next(iter(fx.data))
        fx.build()
        first = (fx.out / f'{name}.torrent').read_bytes()
        fx.build()
        self.assertEqual((fx.out / f'{name}.torrent').read_bytes(), first)

    def test_refuses_what_does_not_match(self):
        fx = Fixture([3 * BLOCK, 2 * BLOCK, 700])
        names = list(fx.data)
        fx.manifest['packs'][0]['files'][0]['sha256'] = '0' * 64           # changed content
        (fx.files / names[1]).write_bytes(b'short')                         # a different size
        os.remove(fx.files / names[2])                                      # not there
        problems = fx.build()
        why = {p.split(':')[0]: p for p in problems}
        self.assertEqual(set(why), set(names))
        self.assertIn('SHA-256', why[names[0]])
        self.assertIn('bytes', why[names[1]])
        self.assertIn('not in', why[names[2]])
        self.assertEqual(list(fx.out.iterdir()), [])

    def test_only(self):
        fx = Fixture([1000, 2000])
        a, b = list(fx.data)
        self.assertEqual(fx.build(only={b}), [])
        self.assertEqual(sorted(p.name for p in fx.out.iterdir()), sorted([f'{b}.torrent', 'torrents.json']))

    def test_the_command_line(self):
        fx = Fixture([2 * BLOCK + 9])
        man = Path(fx.tmp.name) / 'manifest-v1.json'
        man.write_text(json.dumps(fx.manifest))
        import subprocess
        r = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'packaging' / 'make_torrents.py'), '--files', str(fx.files),
                            '--manifest', str(man), '--out', str(fx.out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(list(fx.out.glob('*.torrent'))), 1)
        (fx.files / next(iter(fx.data))).write_bytes(b'x')
        r = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'packaging' / 'make_torrents.py'), '--files', str(fx.files),
                            '--manifest', str(man), '--out', str(fx.out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn('not written', r.stderr)

    def test_libtorrent_reads_them(self):
        try:
            import libtorrent as lt
        except ImportError:
            self.skipTest('python libtorrent is not installed')
        fx = Fixture([7 * BLOCK + 1, 500])
        fx.build()
        for x in json.loads((fx.out / 'torrents.json').read_text())['torrents']:
            ti = lt.torrent_info(str(fx.out / x['torrent']))
            ih = ti.info_hashes()
            self.assertEqual(str(ih.v1), x['btih'])
            self.assertEqual(str(ih.v2), x['btmh'][4:])
            self.assertEqual(list(ti.web_seeds())[0]['url'], f'{BASE}/{x["name"]}')


if __name__ == '__main__':
    unittest.main()
