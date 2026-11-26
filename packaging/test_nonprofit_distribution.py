"""Nonprofit originals never enter general packs, even when a guide cites them."""
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


if __name__ == "__main__":
    unittest.main()
