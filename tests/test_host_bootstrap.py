import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.bootstrap import initialize_project, discover_project, compatible_runtime
from workflow_lib.ingestion import ingest_sources
from workflow_lib.store import read_state, WorkflowError

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'project with spaces'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
    def test_repeat_nested_initialization_preserves_identity(self):
        nested = self.repo / 'src'; nested.mkdir()
        first = initialize_project(nested, None, 'init-1', None)
        second = initialize_project(self.repo, None, 'init-2', None)
        self.assertEqual(first['repo_id'], second['repo_id'])
        self.assertEqual(read_state(Path(first['control_root']))['version'], 1)
        self.assertEqual(second['resumable_runs'], [])
        self.assertEqual(second['document_setup']['default'], 'project-only')
        self.assertFalse((self.repo/'docs').exists())
        self.assertEqual(subprocess.check_output(['git','status','--porcelain'],cwd=self.repo), b'')
    def test_no_project_rejected(self):
        with self.assertRaises(WorkflowError): discover_project(Path(self.temp.name))
    def test_worktree_exclusion_preserves_entries(self):
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=f@example.test','commit','--allow-empty','-qm','initial'],cwd=self.repo,check=True)
        work = Path(self.temp.name) / 'linked worktree'
        subprocess.run(['git','worktree','add','-qb','linked',str(work)],cwd=self.repo,check=True)
        exclude = self.repo / '.git/info/exclude'; exclude.write_text('custom-entry\n')
        initialize_project(work, None, 'linked-init', None)
        self.assertIn('custom-entry', exclude.read_text())
        self.assertIn('/.devflow/', exclude.read_text())
        self.assertEqual(subprocess.check_output(['git','status','--porcelain'],cwd=work),b'')
    def test_runtime_not_ingested_even_root_scope(self):
        runtime=self.repo/'.devflow'; runtime.mkdir(); (runtime/'secret.json').write_text('{}')
        (self.repo/'source.json').write_text('{}')
        indexed=ingest_sources({'location':str(self.repo)},['.'],{'extensions':['.json']},{})
        self.assertEqual([r['path'] for r in indexed['sources']],['source.json'])
    def test_missing_runtime_diagnostic(self):
        with self.assertRaisesRegex(WorkflowError, 'Python 3.11'):
            compatible_runtime([])
    def test_operation_id_required_before_writes(self):
        with self.assertRaises(WorkflowError): initialize_project(self.repo,None,'',None)
        self.assertFalse((self.repo/'.devflow').exists())
    def test_moved_project_does_not_create_duplicate_registry_identity(self):
        first=initialize_project(self.repo,None,'first',None)
        moved=Path(self.temp.name)/'moved';self.repo.rename(moved)
        with self.assertRaisesRegex(WorkflowError,'relocat'):
            initialize_project(moved,None,'second',None)
        self.assertEqual(len(read_state(moved/'.devflow/control')['data']['repositories']),1)
