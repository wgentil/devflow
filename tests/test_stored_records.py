"""Physical references never replace logical review or governing identities."""
import base64
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store, sqlite_store
from control_store_fixtures import owned_control

class StoredRecordTests(unittest.TestCase):
    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.stored_records'))
        return importlib.import_module('workflow_lib.stored_records')

    def package(self, role):
        body = {'schema_version': 2, 'run_id': 'r', 'role': role,
                'plan_hash': 'plan', 'spec_hash': 'spec', 'text': 'é東京 source' * 2000}
        return {**body, 'package_hash': sqlite_store._sha(sqlite_store._json(body).encode())}

    def test_inline_and_referenced_packages_have_identical_hashes(self):
        records = self.backend()
        with owned_control() as root:
            package = self.package('item')
            ref = records.store_package(root, package)
            self.assertEqual(records.resolve_package(root, package), package)
            self.assertEqual(records.resolve_package(root, ref), package)
            self.assertEqual(ref['summary']['package_hash'], package['package_hash'])
            self.assertNotIn('text', ref['summary'])
            bad = {**ref, 'summary': {**ref['summary'], 'role': 'pr'}}
            with self.assertRaises(store.WorkflowError): records.resolve_package(root, bad)

    def test_all_review_roles_require_verified_body(self):
        records = self.backend()
        with owned_control() as root:
            for role in ('item', 'whole', 'branch', 'acceptance', 'pr'):
                with self.subTest(role=role):
                    package = self.package(role)
                    ref = records.store_package(root, package)
                    self.assertEqual(records.resolve_package(root, ref), package)
                    broken = {**package, 'text': 'forged'}
                    with self.assertRaises(store.WorkflowError): records.store_package(root, broken)
                    with self.assertRaises(store.WorkflowError): records.resolve_package(root, broken)

    def test_missing_blob_cannot_pass_gate(self):
        records = self.backend()
        from workflow_lib.gates import gate_status
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            package = self.package('branch')
            store.transact(root, 0, 'run', {'kind': 'run.started', 'payload': {'run': {
                'id': 'r', 'status': 'active', 'review_packages': {package['package_hash']: package}}}})
            with sqlite_store.connection(root) as conn:
                row = conn.execute("SELECT codec,payload FROM entities WHERE space=? AND key='r'",
                                   (sqlite_store._space(('runs',)),)).fetchone()
            self.assertEqual(row[0], 'record')
            physical = json.loads(row[1])
            refs = list(records.object_references(physical))
            package_ref = next(ref for ref in refs if ref['kind'] == 'review-package')
            manifest = root / 'objects/manifests' / package_ref['object_id'][:2] / (package_ref['object_id'][2:] + '.json')
            manifest.unlink()
            with self.assertRaises(store.WorkflowError):
                gate_status(store.read_state(root)['data']['runs']['r'], live=False)

    def test_governing_bytes_roundtrip_without_reapproval(self):
        records = self.backend()
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            binary = base64.b64encode(bytes(range(256)) * 30).decode()
            receipt = {'effective_digest': 'original', 'files': {'app:rules.md': {
                'content_base64': binary, 'content_digest': 'unchanged', 'text': 'é東京'}}}
            proposal = {'proposal_hash': 'p', 'repo_id': 'app', 'diff_digest': 'd', 'files': {
                'rules.md': {'before_content_base64': binary, 'after_content_base64': binary,
                             'diff': '## Heading\nDescription é東京'}}}
            for op, event in enumerate([
                {'kind': 'governing.inputs.recorded', 'payload': {'receipt': receipt}},
                {'kind': 'document.proposed', 'payload': {'proposal': proposal}},
                {'kind': 'document.approved', 'payload': {'approval': {
                    'proposal_hash': 'p', 'repo_id': 'app', 'diff_digest': 'd', 'actor_id': 'owner'}}}]):
                store.transact(root, op, f'op-{op}', event)
            state = store.read_state(root)
            self.assertEqual(state['data']['governing_input_receipt'], receipt)
            self.assertEqual(state['data']['document_proposals']['p'], proposal)
            self.assertEqual(state['data']['document_approvals']['p']['actor_id'], 'owner')
            with sqlite_store.connection(root) as conn:
                payloads = [row[0] for row in conn.execute('SELECT payload FROM entities')] + [row[0] for row in conn.execute('SELECT payload FROM events')]
            self.assertFalse(any(binary in value for value in payloads))
            manifests = [json.loads(p.read_text()) for p in (root / 'objects/manifests').rglob('*.json')]
            self.assertEqual(sum(m['kind'] == 'source-field' and m['size_bytes'] == len(binary) for m in manifests), 1)
