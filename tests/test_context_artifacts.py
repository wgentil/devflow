from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.context_artifacts import (store_context_artifact, inspect_context_artifact,
    resolve_cached_units, invalidate_context_artifacts)
from workflow_lib.document_units import digest
from workflow_lib.store import WorkflowError


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / 'control'
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'a.json').write_text('{"$ref":"b.json#/B"}', encoding='utf-8')
        (self.repo / 'b.json').write_text('{"B":"é"}', encoding='utf-8')
        (self.repo / 'other.md').write_text('Unrelated', encoding='utf-8')
        self.sources = {name: {'root': str(self.repo), 'path': path} for name, path in [('a','a.json'),('b','b.json'),('other','other.md')]}
        self.selection = {'sources': self.sources, 'selections': [{'source_id': 'a'}], 'policy': {}}

    def test_immutable_artifact_inspection_and_tamper_detection(self):
        ref = store_context_artifact(self.control, {'body': 'é'}, {'policy': 1})
        self.assertEqual(inspect_context_artifact(self.control, ref['artifact_id']), {'body': 'é'})
        self.assertEqual(ref, store_context_artifact(self.control, {'body': 'é'}, {'policy': 1}))
        for value in ('../x', '/tmp/a', 'z' * 64):
            with self.assertRaises(WorkflowError):
                inspect_context_artifact(self.control, value)
        Path(ref['artifact_ref']).write_text('{}', encoding='utf-8')
        with self.assertRaises(WorkflowError):
            inspect_context_artifact(self.control, ref['artifact_id'])

    def test_warm_cache_fresh_provenance_and_source_drift(self):
        cold = resolve_cached_units(self.control, self.selection)
        self.assertEqual(cold['cache_outcome'], 'miss')
        self.sources['a']['git_head'] = 'unrelated-commit'
        warm = resolve_cached_units(self.control, self.selection)
        self.assertEqual(warm['cache_outcome'], 'hit')
        self.assertEqual(cold['artifact_id'], warm['artifact_id'])
        self.assertEqual(warm['source_provenance']['a']['git_head'], 'unrelated-commit')
        (self.repo / 'other.md').write_text('Changed unrelated file', encoding='utf-8')
        self.assertEqual(resolve_cached_units(self.control, self.selection)['cache_outcome'], 'hit')
        (self.repo / 'b.json').write_text('{"B":"changed"}', encoding='utf-8')
        drift = resolve_cached_units(self.control, self.selection)
        self.assertEqual(drift['cache_outcome'], 'miss')
        self.assertNotEqual(cold['artifact_id'], drift['artifact_id'])

    def test_missing_corrupt_cache_rebuilds_and_missing_source_fails(self):
        cold = resolve_cached_units(self.control, self.selection)
        Path(cold['artifact_ref']).write_text('{}', encoding='utf-8')
        self.assertEqual(resolve_cached_units(self.control, self.selection)['cache_outcome'], 'miss')
        (self.control / 'context-artifacts/index.json').write_text('broken', encoding='utf-8')
        self.assertEqual(resolve_cached_units(self.control, self.selection)['cache_outcome'], 'miss')
        (self.repo / 'b.json').unlink()
        with self.assertRaises(WorkflowError):
            resolve_cached_units(self.control, self.selection)

    def test_transitive_invalidation_keeps_unrelated_and_never_changes_state(self):
        state = self.control / 'state.json'
        self.control.mkdir()
        state.write_text('{"proof":"old","approval":"unchanged","reassessment":true}', encoding='utf-8')
        before = state.read_bytes()
        main = resolve_cached_units(self.control, self.selection)
        other = resolve_cached_units(self.control, {**self.selection, 'selections': [{'source_id': 'other'}]})
        result = invalidate_context_artifacts(self.control, {'b': 'changed'}, digest({}))
        self.assertEqual(result['affected_ids'], [main['artifact_id']])
        self.assertNotIn(other['artifact_id'], result['affected_ids'])
        self.assertEqual(state.read_bytes(), before)
        # The content reference remains inspectable even after retrieval invalidation.
        self.assertIn('units', inspect_context_artifact(self.control, main['artifact_id']))

    def test_unknown_scope_stale_graph_policy_and_unchanged_bytes(self):
        value = resolve_cached_units(self.control, self.selection)
        unchanged = invalidate_context_artifacts(self.control, value['source_hashes'], digest({}))
        self.assertEqual(unchanged['affected_ids'], [])
        unknown = invalidate_context_artifacts(self.control, {'unknown': None}, digest({}))
        self.assertEqual(unknown['affected_ids'], [value['artifact_id']])
        resolve_cached_units(self.control, self.selection)
        policy = invalidate_context_artifacts(self.control, {}, 'new-policy')
        self.assertEqual(policy['affected_ids'], [value['artifact_id']])
        resolve_cached_units(self.control, self.selection)
        index = self.control / 'context-artifacts/index.json'
        content = json.loads(index.read_text(encoding='utf-8'))
        content['schema_version'] = 0
        index.write_text(json.dumps(content), encoding='utf-8')
        stale = invalidate_context_artifacts(self.control, {}, digest({}))
        self.assertEqual(stale['reason_code'], 'CONSERVATIVE_INVALIDATION')

    def test_direct_edits_renames_and_selection_changes(self):
        first = resolve_cached_units(self.control, self.selection)
        (self.repo / 'a.json').write_text('{"x":1}', encoding='utf-8')
        direct = resolve_cached_units(self.control, self.selection)
        self.assertNotEqual(first['artifact_id'], direct['artifact_id'])
        (self.repo / 'a.json').rename(self.repo / 'renamed.json')
        self.sources['a']['path'] = 'renamed.json'
        renamed = resolve_cached_units(self.control, self.selection)
        self.assertEqual(renamed['cache_outcome'], 'miss')
        selected = resolve_cached_units(self.control, {**self.selection, 'selections': [
            {'source_id': 'a', 'selector': {'kind': 'json-pointer', 'pointer': '/x'}}]})
        self.assertNotEqual(renamed['artifact_id'], selected['artifact_id'])

    def test_redirected_advisory_index_cannot_substitute_another_valid_scope(self):
        first = resolve_cached_units(self.control, self.selection)
        other_selection = {**self.selection, 'selections': [{'source_id': 'other'}]}
        other = resolve_cached_units(self.control, other_selection)
        path = self.control / 'context-artifacts/index.json'
        index = json.loads(path.read_text(encoding='utf-8'))
        first_key = next(k for k, v in index['entries'].items() if v['artifact_id'] == first['artifact_id'])
        other_entry = next(v for v in index['entries'].values() if v['artifact_id'] == other['artifact_id'])
        index['entries'][first_key] = other_entry
        path.write_text(json.dumps(index), encoding='utf-8')
        rebuilt = resolve_cached_units(self.control, self.selection)
        self.assertEqual(rebuilt['cache_outcome'], 'miss')
        self.assertEqual(set(rebuilt['source_hashes']), {'a', 'b'})
