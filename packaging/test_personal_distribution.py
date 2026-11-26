"""Personal sources never enter public packs, even when a guide cites them."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import io
import shutil
from contextlib import redirect_stdout
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('packs', HERE / 'build_packs.py')
packs = importlib.util.module_from_spec(spec); spec.loader.exec_module(packs)


class Distribution(unittest.TestCase):
    def test_nonprofit_originals_and_associated_media_stay_out_of_general_packs(self):
        source=json.loads((HERE.parent/'content/regions/au/nonprofit-trauma-source.json').read_text(encoding='utf-8'))['source']
        source={**source,'path':'documents/au-nonprofit/source.pdf'}
        public={'id':'public-document','kind':'pdf','path':'documents/public.pdf'}
        video={'id':'nonprofit-video','kind':'video','path':'videos/nonprofit.mp4','title':'Synthetic video',
               'publisher':'Example','collection':'Example','category':'first-aid','distribution':'nonprofit-only'}
        transcript={'id':'nonprofit-transcript','kind':'transcript','path':'transcripts/nonprofit.txt','video_path':video['path']}
        rows=[public,source,video,transcript]
        with tempfile.TemporaryDirectory() as d:
            snap=Path(d);(snap/'remote-videos.json').write_text('{}',encoding='utf-8')
            with patch.object(packs,'video_groups',return_value=({video['id']:{'verdict':'keep'}},{video['id']:''})), \
                    patch.object(packs,'guide_ids',return_value={r['id'] for r in rows}), \
                    patch.dict(packs.SIZES,{'small':{**packs.SIZES['small'],'video_include':[],'video_exclude':[]}}):
                for size in ['small','medium','all']:
                    chosen,left,_=packs.select(size,rows,snap,0)
                    self.assertEqual(set(chosen),{public['id']})
                    self.assertIn('nonprofit only',next(why for uid,_,why in left if uid==source['id']))

    def test_nonprofit_guide_absences_are_intentional_for_general_packs(self):
        spec=importlib.util.spec_from_file_location('verify_nonprofit',HERE/'verify_packs.py')
        verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'packaging').mkdir();(root/'content/topics').mkdir(parents=True)
            for name in ['ship_app_files.py','ship_edits.json']:shutil.copy2(HERE/name,root/'packaging'/name)
            (root/'content/topics/example.json').write_text(json.dumps({'learn':[{'doc':'nonprofit-doc'},{'doc':'public-doc'}]}),encoding='utf-8')
            snap=root/'snapshot';snap.mkdir();public={'id':'public-doc','kind':'pdf','path':'documents/public.pdf'}
            (snap/'catalog.json').write_text(json.dumps([public,{'id':'nonprofit-doc','kind':'pdf','path':'documents/nonprofit.pdf','distribution':'nonprofit-only'}]),encoding='utf-8')
            lib=root/'pack/library-data';lib.mkdir(parents=True)
            with patch.object(verify,'PROJECT',root),redirect_stdout(io.StringIO()) as output:
                (lib/'catalog.json').write_text('[]',encoding='utf-8');self.assertEqual(verify.guides(snap,[lib.parent]),1)
                (lib/'catalog.json').write_text(json.dumps([public]),encoding='utf-8');self.assertEqual(verify.guides(snap,[lib.parent]),0)
            self.assertIn('nonprofit source excluded from general packs',output.getvalue())

    def test_actual_first_aid_guide_links_never_promote_originals_into_public_packs(self):
        root = HERE.parent
        private = json.loads((root / 'content/regions/au/personal-bls-first-aid-sources.json').read_text())['sources']
        public = next(r for r in json.loads((root / 'content/regions/au/manifest.json').read_text())['sources']
                      if r['id'] == 'qld-poisons')
        self.assertTrue({r['id'] for r in private} <= packs.guide_ids())
        with tempfile.TemporaryDirectory() as d:
            snap = Path(d); (snap / 'remote-videos.json').write_text('{}')
            with patch.object(packs, 'video_groups', return_value=({}, {})), \
                 patch.dict(packs.SIZES, {'small': {**packs.SIZES['small'], 'video_include': [], 'video_exclude': []}}):
                for size in ['small', 'medium', 'all']:
                    chosen, left, _ = packs.select(size, [public] + private, snap, 0)
                    self.assertIn(public['id'], chosen)
                    self.assertTrue({r['id'] for r in private}.isdisjoint(chosen))
                    self.assertTrue(all('not redistributable' in why for uid, _, why in left
                                        if uid in {r['id'] for r in private}))

    def test_guide_verifier_distinguishes_restricted_sources_from_missing_public_sources(self):
        spec = importlib.util.spec_from_file_location('verify', HERE / 'verify_packs.py')
        verify = importlib.util.module_from_spec(spec); spec.loader.exec_module(verify)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'packaging').mkdir(); (root / 'content/topics').mkdir(parents=True)
            for name in ['ship_app_files.py', 'ship_edits.json']:
                shutil.copy2(HERE / name, root / 'packaging' / name)
            (root / 'content/topics/example.json').write_text(json.dumps({'learn': [{'doc': 'public-document'}, {'doc': 'personal-au-example'}]}), encoding='utf-8')
            snap = root / 'snapshot'; snap.mkdir()
            public = {'id': 'public-document', 'kind': 'pdf', 'path': 'documents/public.pdf'}
            personal = {'id': 'personal-au-example', 'kind': 'pdf', 'path': 'documents/personal.pdf', 'distribution': 'personal-only'}
            (snap / 'catalog.json').write_text(json.dumps([public, personal]), encoding='utf-8')
            lib = root / 'pack/library-data'; lib.mkdir(parents=True)
            with patch.object(verify, 'PROJECT', root), redirect_stdout(io.StringIO()) as output:
                (lib / 'catalog.json').write_text('[]', encoding='utf-8')
                self.assertEqual(verify.guides(snap, [lib.parent]), 1)
                (lib / 'catalog.json').write_text(json.dumps([public]), encoding='utf-8')
                self.assertEqual(verify.guides(snap, [lib.parent]), 0)
            self.assertIn('not redistributable', output.getvalue())

    def test_guide_references_do_not_override_personal_use_restrictions(self):
        public = {'id': 'public-document', 'kind': 'pdf', 'path': 'documents/public.pdf'}
        private = {'id': 'personal-au-example', 'kind': 'pdf', 'path': 'documents/personal-au/example.pdf',
                   'distribution': 'personal-only'}
        hub = {'id': 'personal-au-reference', 'kind': 'html', 'path': 'pages/personal-au/index.html',
               'distribution': 'personal-only'}
        video = {'id': 'personal-au-video', 'kind': 'video', 'path': 'videos/personal.mp4',
                 'title': 'Synthetic video', 'publisher': 'Example', 'collection': 'Personal',
                 'category': 'first-aid', 'distribution': 'personal-only'}
        transcript = {'id': 'personal-video-transcript', 'kind': 'transcript', 'path': 'transcripts/personal.txt',
                      'video_path': video['path']}
        rows = [public, private, hub, video, transcript]
        with tempfile.TemporaryDirectory() as d:
            snap = Path(d); (snap / 'remote-videos.json').write_text('{}', encoding='utf-8')
            with patch.object(packs, 'video_groups', return_value=({video['id']: {'verdict': 'keep'}}, {video['id']: ''})), \
                    patch.object(packs, 'guide_ids', return_value={r['id'] for r in rows}), \
                    patch.dict(packs.SIZES, {'small': {**packs.SIZES['small'], 'video_include': [], 'video_exclude': []}}):
                for size in ['small', 'medium', 'all']:
                    with self.subTest(size=size):
                        chosen, left, _ = packs.select(size, rows, snap, 0)
                        self.assertIn(public['id'], chosen)
                        self.assertNotIn(private['id'], chosen)
                        self.assertNotIn(hub['id'], chosen)
                        self.assertNotIn(video['id'], chosen)
                        self.assertNotIn(transcript['id'], chosen)
                        self.assertTrue(all('not redistributable' in why for uid, _, why in left if uid.startswith('personal-au-')))


if __name__ == '__main__': unittest.main()
