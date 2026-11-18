#!/usr/bin/env python3
"""Regression tests for setup bugs found in the audit. Same harness as test_setup.py.

  .venv/bin/python -B -m unittest app.tests.test_setup_fixes
"""
import json, os, shutil, sys, threading, time, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
from app.tests.test_setup import Base, Manage, make_map, Maps, Control, ALLOWED, MiB, make_pack, sha, api, download, hardware, install, manifest  # noqa: E402,F401


class SwitchFailure(Base):

    def lib(self, where, marker):
        (where / 'library-data').mkdir(parents=True)
        (where / 'library-data' / 'catalog.json').write_text(marker)
        return where

    def old_with_files(self):
        cur = self.lib(self.parent / 'LastbookData', 'old')
        (cur / 'models').mkdir()
        (cur / 'models' / 'model.gguf').write_bytes(self.model)
        (cur / 'derived' / 'geo' / 'addresses').mkdir(parents=True)
        (cur / 'derived' / 'geo' / 'addresses' / 'NJ.sqlite').write_bytes(b'addr')
        new = self.lib(self.parent / 'LastbookData.setup' / 'unpack' / 'LastbookData', 'new')
        return cur, new

    def fail_nth_replace(self, n):
        real, calls = os.replace, []

        def flaky(a, b, *x, **k):
            calls.append((str(a), str(b)))
            if len([c for c in calls if 'LastbookData.old' in c[1] or c[1].endswith('LastbookData')]) == n and Path(b).name in ('LastbookData',) or (n == 1 and 'LastbookData.old' in str(b)):
                raise OSError('nope')
            return real(a, b, *x, **k)
        return mock.patch.object(os, 'replace', flaky)

    def check_intact(self, cur):
        self.assertEqual((cur / 'library-data' / 'catalog.json').read_text(), 'old')
        self.assertTrue((cur / 'models' / 'model.gguf').is_file())
        self.assertTrue((cur / 'derived' / 'geo' / 'addresses' / 'NJ.sqlite').is_file())

    def test_old_library_keeps_model_when_it_cannot_be_moved_aside(self):
        cur, new = self.old_with_files()
        real = os.replace

        def flaky(a, b, *x, **k):
            if Path(a) == cur:
                raise OSError('busy')
            return real(a, b, *x, **k)
        with mock.patch.object(os, 'replace', flaky), self.assertRaises(install.Refused):
            install.switch(new, cur)
        self.check_intact(cur)
        self.assertFalse((new / 'models').exists() and any((new / 'models').iterdir()))

    def test_old_library_keeps_model_when_new_cannot_be_put_in_place(self):
        cur, new = self.old_with_files()
        real = os.replace

        def flaky(a, b, *x, **k):
            if Path(a) == new:
                raise OSError('busy')
            return real(a, b, *x, **k)
        with mock.patch.object(os, 'replace', flaky), self.assertRaises(install.Refused):
            install.switch(new, cur)
        self.check_intact(cur)

    def test_old_library_keeps_model_when_carrying_fails_part_way(self):
        cur, new = self.old_with_files()
        real = os.replace

        def flaky(a, b, *x, **k):
            if Path(a).name == 'NJ.sqlite' and Path(b).is_relative_to(new):   # the model has moved; the address index will not
                raise OSError('busy')
            return real(a, b, *x, **k)
        with mock.patch.object(os, 'replace', flaky), self.assertRaises(install.Refused):
            install.switch(new, cur)
        self.check_intact(cur)
        self.assertFalse((new / 'models' / 'model.gguf').exists())

    def test_opened_keeps_work_folder_when_switch_failed(self):
        cur, new = self.old_with_files()
        work = self.parent / 'LastbookData.setup'
        (work / 'marker').write_text('x')
        (self.settings).mkdir(parents=True, exist_ok=True)
        (self.settings / 'setup.json').write_text(json.dumps({'work': str(work)}))
        jf = api._job_file(self.settings)
        jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text(json.dumps({'state': 'done'}))
        api.opened(self.settings, cur, {'target': str(cur), 'old': None, 'error': 'It broke.'})
        self.assertTrue((work / 'marker').exists())
        self.assertFalse(jf.exists())


class NewJob(Base):
    def failed_job(self, s):
        zipdata = self.files.data.pop('Lastbook-Small.zip')
        with fast_backoff():
            s.start('small', False)
            j = self.wait(s)
        self.assertEqual(j['state'], 'failed', j)
        self.files.data['Lastbook-Small.zip'] = zipdata

    def test_new_job_does_not_unpack_on_a_failed_jobs_leftovers(self):
        s = self.setup()
        self.failed_job(s)
        work = api._work_for(self.parent / 'LastbookData')
        stale = work / 'unpack' / 'LastbookData' / 'stale-from-old-job.txt'
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('old')
        s.start('small', False)
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertFalse(stale.exists())
        self.assertTrue((work / 'unpack' / 'LastbookData' / 'pack.json').is_file())

    def test_retry_keeps_the_unpack_folder(self):
        s = self.setup()
        self.failed_job(s)
        work = api._work_for(self.parent / 'LastbookData')
        keep = work / 'unpack' / 'keep.txt'
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text('x')
        with mock.patch.object(api.Setup, '_run'):       # only the state change: retry must not touch the folders
            s.retry()
        self.assertTrue(keep.exists())


class Sources(Base):
    def test_file_that_failed_its_checksum_is_forgotten(self):
        bad = bytearray(self.zip)
        bad[100] ^= 0xff
        mine = self.tmp / 'elsewhere' / 'Lastbook-Small.zip'
        mine.parent.mkdir()
        mine.write_bytes(bad)
        s = self.setup()
        s.use(str(mine))
        self.assertEqual(self.wait(s)['error']['code'], 'found_mismatch')
        hashed = []
        real = api._sha256
        self.files.log.clear()
        with mock.patch.object(api, '_sha256', lambda p, *a, **k: hashed.append(str(p)) or real(p, *a, **k)):
            s.start('small', False)         # a new start downloads; it does not hash the rejected file again
            self.assertEqual(self.wait(s)['state'], 'done')
        self.assertNotIn(str(mine), hashed)
        self.assertEqual(s.public_job()['items'][0]['source'], 'download')


class RepairKeepsMap(Base):
    installed_library = Manage.installed_library

    def lib_with_map(self):
        lib = self.installed_library()
        files = make_map(self.tmp / 'm.zip')
        for rel, data in files.items():
            (lib / rel).parent.mkdir(parents=True, exist_ok=True)
            (lib / rel).write_bytes(data)
        return lib, files

    def test_repair_keeps_the_installed_state_map(self):
        lib, files = self.lib_with_map()
        path = lib / 'library-data' / 'big.bin'
        data = bytearray(path.read_bytes())
        data[0] ^= 1
        path.write_bytes(data)
        s = self.setup('manage', current=lib)
        self.assertEqual(s.current_info()['map'], 'CA')
        s.start(repair=True)
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertEqual(sorted(n for n, _, _ in self.files.log), ['Lastbook-Small.zip'])      # the map is not fetched
        new, note = api.startup(self.settings)
        self.assertEqual(install.map_name(new), 'CA')
        self.assertEqual((new / 'derived/geo/map.sqlite').read_bytes(), files['derived/geo/map.sqlite'])

    def test_repair_space_check_counts_the_kept_map(self):
        lib, files = self.lib_with_map()
        path = lib / 'library-data' / 'big.bin'
        data = bytearray(path.read_bytes())
        data[0] ^= 1
        path.write_bytes(data)
        s = self.setup('manage', current=lib)
        with mock.patch.object(install, 'need_bytes', lambda *a, **k: 1000), mock.patch.object(hardware, 'disk_of', lambda p: (2000, 10 ** 12)):
            s.start(repair=True)
            j = self.wait(s)
        self.assertEqual(j['state'], 'failed', j)
        self.assertIn('files need fetching again', j['error']['message'])      # the repair's own check, with the map's bytes in it


class StaleWorker(Base):
    """A worker that outlives cancel() (which gives up joining) must not write into the cancelled job or a newer one."""

    def run_stuck(self, then):
        s = self.setup()
        entered, release = threading.Event(), threading.Event()
        errors = []

        def stuck(self_, it, plan, work, control):
            entered.set()
            release.wait(10)
            try:
                self_._set(it, 'unpacking')
                self_._fail(it, 'network', 'late failure')
            except Exception as e:
                errors.append(e)
        with mock.patch.object(api.Setup, '_do_pack', stuck), \
                mock.patch.object(api.Setup, '_join', lambda self_: self_.thread.join(0.2)):
            s.start('small', False)
            self.assertTrue(entered.wait(10))
            j = s.cancel()
            old_thread = s.thread
            then(s)
            release.set()
            old_thread.join(10)
        return s, j

    def test_late_worker_does_not_overwrite_a_cancelled_job(self):
        s, j = self.run_stuck(lambda s: None)
        self.assertEqual(j['error']['code'], 'cancelled')
        self.assertNotIn('Nothing was changed', j['error']['message'])      # the worker was still running: that would not be true
        after = s.public_job()
        self.assertEqual(after['state'], 'failed')
        self.assertEqual(after['error']['code'], 'cancelled')

    def test_late_worker_does_not_touch_a_newer_job(self):
        newer = {'id': 'newer', 'state': 'waiting', 'items': [], 'error': None, 'plan': {'work': str(self.tmp / 'w'), 'target': str(self.tmp / 't')}}

        def swap(s):
            s.job = newer
        s, j = self.run_stuck(swap)
        self.assertEqual((newer['state'], newer['error']), ('waiting', None))

    def test_cancel_with_nothing_running_still_says_nothing_changed(self):
        s = self.setup()
        self.files.data.pop('Lastbook-Small.zip')
        with fast_backoff():
            s.start('small', False)
            self.wait(s)
        self.assertIn('Nothing was changed', s.cancel()['error']['message'])


class UseFile(Base):
    def test_use_zip_keeps_the_folder_and_ai_chosen_on_screen(self):
        mine = self.tmp / 'elsewhere' / 'Lastbook-Small.zip'
        mine.parent.mkdir()
        mine.write_bytes(self.zip)
        chosen = self.tmp / 'chosen'
        s = self.setup()
        j = s.use(str(mine), folder=str(chosen), ai=True)
        self.assertIsNone(j.get('error'), j)
        self.assertEqual(j['folder'], str(chosen / 'LastbookData'))
        self.assertEqual([i['kind'] for i in j['items']], ['pack', 'model'])
        self.assertEqual(self.wait(s)['state'], 'done')

    def test_use_zip_passes_the_chosen_state_map(self):
        mf, _ = Maps.map_manifest(self)
        mine = self.tmp / 'elsewhere' / 'Lastbook-Small.zip'
        mine.parent.mkdir()
        mine.write_bytes(self.zip)
        s = self.setup(manifest=mf)
        j = s.use(str(mine), map_id='CA')
        self.assertEqual([i['kind'] for i in j['items']], ['pack', 'map'])
        self.wait(s)

    def failed_job(self, s):
        zipdata = self.files.data.pop('Lastbook-Small.zip')
        with fast_backoff():
            s.start('small', False)
            self.assertEqual(self.wait(s)['state'], 'failed')
        self.files.data['Lastbook-Small.zip'] = zipdata

    def test_noted_file_in_first_run_is_not_a_stale_job(self):
        model = self.home / 'Downloads' / 'model.gguf'
        model.write_bytes(self.model)
        s = self.setup()
        self.failed_job(s)
        r = s.use(str(model))
        self.assertEqual((r.get('noted'), r.get('kind')), (True, 'model'))
        self.assertNotIn('state', r)

    def test_noted_map_file_says_map(self):
        mf, _ = Maps.map_manifest(self)
        mine = self.tmp / 'elsewhere' / 'Lastbook-Map-CA.zip'
        mine.parent.mkdir()
        mine.write_bytes((self.tmp / 'Lastbook-Map-CA.zip').read_bytes())
        s = self.setup(manifest=mf)
        r = s.use(str(mine))
        self.assertEqual((r.get('noted'), r.get('kind')), (True, 'map'))


class ErrorCodes(Base):
    def fails_with(self, exc, state=None):
        s = self.setup()

        def boom(self_, it, plan, work, control):
            if state:
                self_._set(it, state)
            raise exc
        with mock.patch.object(api.Setup, '_do_pack', boom):
            s.start('small', False)
            return self.wait(s)['error']

    def test_local_file_error_is_not_a_network_error(self):
        e = self.fails_with(PermissionError(13, 'Permission denied'), 'downloading')
        self.assertEqual(e['code'], 'folder')
        self.assertIn('Permission denied', e['message'])

    def test_local_file_error_while_unpacking_stays_unpack(self):
        self.assertEqual(self.fails_with(PermissionError(13, 'Permission denied'), 'unpacking')['code'], 'unpack')

    def test_unexpected_error_is_internal_not_activate(self):
        e = self.fails_with(ValueError('odd'))
        self.assertEqual(e['code'], 'internal')
        self.assertIn('ValueError', e['message'])


class ManifestRace(Base):
    """Running from source there is no bundled manifest: the first state() must not answer with an empty list while the fetch runs."""

    def remote_manifest(self):
        m = self.manifest().current
        return json.dumps(m).encode()

    def empty_setup(self, fetch):
        mf = manifest.Manifest(bundled={'version': 1, 'published': '', 'packs': [], 'models': [], 'maps': []},
                               remote='https://127.0.0.1/manifest-v1.json', allowed=ALLOWED, context=self.ctx)
        self.mf = mf
        with mock.patch.object(download, 'fetch_small', fetch):
            return self.setup(manifest=mf), mf

    def test_first_state_waits_for_the_fetch(self):
        data = self.remote_manifest()

        def slow(*a, **k):
            time.sleep(0.4)
            return data
        s, mf = self.empty_setup(slow)
        with mock.patch.object(download, 'fetch_small', slow):
            st = s.state()
        self.assertEqual([p['id'] for p in st['manifest']['packs']], ['small', 'all'])

    def test_failed_fetch_is_tried_again_by_a_later_state(self):
        data = self.remote_manifest()
        calls = []

        def flaky(*a, **k):
            calls.append(1)
            return None if len(calls) == 1 else data
        s, mf = self.empty_setup(flaky)
        with mock.patch.object(download, 'fetch_small', flaky), mock.patch.object(manifest, 'RETRY_S', 0):
            self.assertEqual(s.state()['manifest']['packs'], [])
            self.assertEqual([p['id'] for p in s.state()['manifest']['packs']], ['small', 'all'])

    def test_a_bundled_manifest_never_waits(self):
        calls = []
        mf = self.manifest()
        mf.remote = 'https://127.0.0.1/manifest-v1.json'

        def slow(*a, **k):
            calls.append(1)
            time.sleep(2)
        s = self.setup(manifest=mf)
        with mock.patch.object(download, 'fetch_small', slow):
            t0 = time.time()
            s.state()
        self.assertLess(time.time() - t0, 1.0)


def fast_backoff():
    return mock.patch.object(download, 'BACKOFF', (0.05,) * 6)


if __name__ == '__main__':
    unittest.main()
