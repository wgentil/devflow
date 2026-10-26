"""Immutable storage must preserve identity and fail closed without creating authority."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from control_store_fixtures import owned_control, legacy_root


class StorageObjectTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(owned_control())

    def module(self, name='storage_objects'):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.' + name),
                             'The real versioned storage component is required for this contract')
        return importlib.import_module('workflow_lib.' + name)

    def test_object_roundtrip_preserves_bytes_and_kind(self):
        store = self.module()
        value = b'raw\x00\xff\r\n' + 'é東京'.encode()
        for encoding in ('identity', 'gzip'):
            with self.subTest(encoding=encoding):
                ref = store.put_object(self.root, 'test-' + encoding, value, encoding=encoding)
                self.assertEqual(store.read_object(self.root, ref, max_bytes=len(value)), value)
                self.assertEqual(ref['kind'], 'test-' + encoding)
                self.assertEqual(ref['size_bytes'], len(value))
                self.assertEqual(store.put_object(self.root, 'test-' + encoding, value), ref)
                with self.assertRaises(WorkflowError):
                    store.read_object(self.root, {**ref, 'kind': 'different'}, max_bytes=100)
        self.assertNotEqual(store.put_object(self.root, 'kind-a', value)['object_id'],
                            store.put_object(self.root, 'kind-b', value)['object_id'])

    def test_chunked_object_stream_is_bounded(self):
        store = self.module()
        value = b'x' * (4 * 1024 * 1024) + b'y' * (4 * 1024 * 1024) + b'z'
        ref = store.put_object(self.root, 'large-test', value)
        chunks = list(store.stream_object(self.root, ref))
        self.assertEqual(b''.join(chunks), value)
        self.assertTrue(chunks)
        self.assertLessEqual(max(map(len, chunks)), 4 * 1024 * 1024)
        self.assertFalse((self.root / 'state.json').exists())
        self.assertFalse((self.root / 'format.json').exists())

    def test_corrupt_or_oversized_object_fails_closed(self):
        store = self.module()
        value = b'payload' * 100
        ref = store.put_object(self.root, 'test', value)
        with self.assertRaises(WorkflowError) as caught:
            store.read_object(self.root, ref, max_bytes=len(value) - 1)
        self.assertEqual(caught.exception.code, 'STORAGE_OBJECT_LIMIT')
        for change in ({'schema_version': 999}, {'object_id': '../escape'}, {'size_bytes': -1}):
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                store.read_object(self.root, {**ref, **change}, max_bytes=10000)
        path = next((self.root / 'objects' / 'manifests').rglob('*.json'))
        path.write_bytes(b'{"corrupt":true}')
        with self.assertRaises(WorkflowError):
            store.read_object(self.root, ref, max_bytes=10000)
        with self.assertRaises(WorkflowError):
            store.put_object(self.root, 'test', value)

    def test_layout_detection_never_creates_empty_authority(self):
        formats = self.module('storage_format')
        self.assertEqual(formats.detect_layout(self.root)['layout'], 'uninitialized')
        self.assertFalse(self.root.exists())
        legacy_root(self.root)
        self.assertEqual(formats.detect_layout(self.root)['storage_format'], 1)
        (self.root / 'maintenance').mkdir()
        (self.root / 'maintenance/intent.json').write_text('{}', encoding='utf-8')
        self.assertEqual(formats.detect_layout(self.root)['layout'], 'incomplete')
        (self.root / 'maintenance/intent.json').unlink()
        (self.root / 'format.json').write_text('{"storage_format":999}', encoding='utf-8')
        with self.assertRaises(WorkflowError) as caught:
            formats.detect_layout(self.root)
        self.assertEqual(caught.exception.code, 'UNSUPPORTED_STORAGE_FORMAT')

    def test_symlink_escape_never_publishes_outside_root(self):
        store = self.module()
        self.root.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as outside:
            try:
                (self.root / 'objects').symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest('symlink creation unavailable: ' + str(exc))
            with self.assertRaises(WorkflowError):
                store.put_object(self.root, 'test', b'forbidden')
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_failed_publication_is_retryable_without_partial_reference(self):
        store = self.module()
        value = b'published only when complete'
        original = store._publish
        for after in (False, True):
            root = self.root / str(after)
            def fail_manifest(path, raw):
                if 'manifests' in path.parts:
                    if after:
                        original(path, raw)
                    raise OSError('injected publication interruption')
                return original(path, raw)
            with patch.object(store, '_publish', side_effect=fail_manifest):
                with self.assertRaises((OSError, WorkflowError)):
                    store.put_object(root, 'test', value)
            ref = store.put_object(root, 'test', value)
            self.assertEqual(store.read_object(root, ref, max_bytes=100), value)
            self.assertFalse(list(root.rglob('*.tmp')))

    def test_concurrent_publishers_return_one_complete_identity(self):
        self._assert_concurrent_publishers(self.root)

    @unittest.skipUnless(os.name=='nt','native Windows fresh-root canonicalization race')
    def test_repeated_concurrent_fresh_windows_roots_preserve_confinement(self):
        for index in range(5):
            with self.subTest(index=index):self._assert_concurrent_publishers(self.root/('fresh-'+str(index)))

    def _assert_concurrent_publishers(self,root):
        store = self.module()
        code = "import json,sys;from pathlib import Path;from workflow_lib.storage_objects import put_object;print(json.dumps(put_object(Path(sys.argv[1]),'race',b'concurrent'*1000)))"
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'skills/workflow/scripts')}
        processes = [subprocess.Popen([sys.executable, '-B', '-c', code, str(root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for _ in range(4)]
        for process in processes:
            self.addCleanup(lambda p=process: p.kill() if p.poll() is None else None)
        refs = []
        for process in processes:
            out, err = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, err.decode('utf-8', errors='replace'))
            refs.append(json.loads(out))
        self.assertEqual(refs, [refs[0]] * 4)
        self.assertEqual(store.read_object(root, refs[0], max_bytes=10000), b'concurrent' * 1000)
        self.assertFalse(list(root.rglob('*.tmp')))

    def test_missing_component_resolution_cannot_reject_safe_publication(self):
        store=self.module();self.root.mkdir(parents=True)
        outside=self.root.parent/'outside-fallback';outside.mkdir()
        original=Path.resolve
        def resolve(path,strict=False):
            # A non-strict OS fallback can have a different spelling while
            # another publisher creates ancestors. It is not an existing link.
            if not strict and path!=self.root and path.is_relative_to(self.root) and not path.exists():
                return outside/path.name
            return original(path,strict=strict)
        with patch.object(Path,'resolve',resolve):
            reference=store.put_object(self.root,'safe-publication',b'complete bytes')
        self.assertEqual(store.read_object(self.root,reference,max_bytes=100),b'complete bytes')
        self.assertEqual(list(outside.iterdir()),[])

    def test_existing_open_manifest_is_reused_without_replacement(self):
        store = self.module()
        ref = store.put_object(self.root, 'open', b'unchanged')
        path = next((self.root / 'objects/manifests').rglob('*.json'))
        code = "import sys;f=open(sys.argv[1],'rb');print('ready',flush=True);sys.stdin.readline();f.close()"
        process = subprocess.Popen([sys.executable, '-B', '-c', code, str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            self.assertEqual(store.put_object(self.root, 'open', b'unchanged'), ref)
        finally:
            process.communicate('done\n', timeout=10)
        self.assertEqual(process.returncode, 0)

    @unittest.skipUnless(os.name == 'nt', 'native NTFS junction containment')
    def test_junction_escape_never_publishes_outside_root(self):
        store = self.module()
        self.root.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as outside:
            for target in (Path(outside),Path(outside)/'missing-target'):
                with self.subTest(target_exists=target.exists()):
                    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root / 'objects'), str(target)],
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0,result.stderr)
                    try:
                        with self.assertRaises(WorkflowError):
                            store.put_object(self.root, 'test', b'forbidden')
                        self.assertEqual(list(Path(outside).iterdir()), [])
                    finally:
                        os.rmdir(self.root / 'objects')
