import sys, tempfile, unittest, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.ingestion import ingest_sources, merge_digests, digest_coverage

class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Path(self.tmp.name); (self.repo/'a.py').write_text('x=1\ny=2\n'); (self.repo/'README.md').write_text('# hi\n')
        subprocess.run(['git','init','-q'],cwd=self.repo); subprocess.run(['git','add','.'],cwd=self.repo); subprocess.run(['git','-c','user.name=x','-c','user.email=x@y','commit','-qm','fixture'],cwd=self.repo)
    def tearDown(self): self.tmp.cleanup()
    def test_formats_and_source_lines(self):
        out=ingest_sources({'location':str(self.repo)},['.'],{'extensions':['.py','.md']},{})
        self.assertEqual({x['path'] for x in out['sources']},{'a.py','README.md'}); self.assertEqual(next(x for x in out['sources'] if x['path']=='a.py')['line_end'],2)
    def test_cache_complete_key_and_transitive_invalidation(self):
        cache={}; repo={'location':str(self.repo)}; profile={'extensions':['.py']}
        a=ingest_sources(repo,['.'],profile,cache); b=ingest_sources(repo,['.'],profile,cache)
        self.assertTrue(b['cache_hit']); (self.repo/'a.py').write_text('x=3\n')
        c=ingest_sources(repo,['.'],profile,cache); self.assertFalse(c['cache_hit'])
    def test_merge_coverage_and_path_escape(self):
        a={'sources':[{'path':'a.py','hash':'a','facts':[{'id':'x','value':1}]}]}; b={'sources':[{'path':'a.py','hash':'b','facts':[{'id':'x','value':2}]}]}
        merged=merge_digests([a,b]); self.assertTrue(merged['conflicts']); self.assertEqual(digest_coverage(merged,{'paths':['a.py','b.py']})['uncovered'],['b.py'])
        with self.assertRaises(ValueError): ingest_sources({'location':str(self.repo)},['../'],{'extensions':['.py']},{})

    def test_active_history_explicit_and_required_dependency_exceptions(self):
        history = self.repo / 'docs/superpowers/specs/old.md'
        history.parent.mkdir(parents=True)
        history.write_text('Historical rule')
        repo = {'location': str(self.repo)}
        policy = {'history': ['docs/superpowers/**'], 'include_history': False, 'required_paths': []}
        out = ingest_sources(repo, ['.'], {}, {}, selection_policy=policy)
        self.assertNotIn(history.relative_to(self.repo).as_posix(), [s['path'] for s in out['sources']])
        self.assertEqual(out['selection']['excluded_count'], 1)
        explicit = ingest_sources(repo, ['.'], {}, {}, selection_policy={**policy, 'include_history': True})
        self.assertIn(history.relative_to(self.repo).as_posix(), [s['path'] for s in explicit['sources']])
        required = ingest_sources(repo, ['a.py'], {'extensions': ['.py']}, {}, selection_policy={**policy, 'required_paths': [history.relative_to(self.repo).as_posix()]})
        self.assertIn(history.relative_to(self.repo).as_posix(), [s['path'] for s in required['sources']])
        self.assertNotEqual(out['fingerprint'], explicit['fingerprint'])

    def test_projection_retains_metadata_and_inspection_restores_contents(self):
        from workflow_lib.ingestion import project_source_index
        from workflow_lib.context_artifacts import inspect_context_artifact
        value = ingest_sources({'location': str(self.repo)}, ['.'], {}, {})
        with tempfile.TemporaryDirectory() as control:
            refs = project_source_index(value, Path(control))
            self.assertNotIn('text', refs['sources'][0])
            self.assertIn('hash', refs['sources'][0])
            self.assertEqual(inspect_context_artifact(Path(control), refs['artifact_id']), value)
