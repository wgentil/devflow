"""Real Git scope checks independent of platform path spelling and filemode support."""
import os,stat,unittest
from unittest.mock import patch
import test_standalone_review
from workflow_lib import standalone_reviews
from workflow_lib.store import WorkflowError

class StandalonePathParityTests(unittest.TestCase):
    def fixture(self):
        case=test_standalone_review.StandaloneReviewTests();case.setUp();self.addCleanup(case.doCleanups)
        return case,case.fixture()
    def test_equivalent_git_root_spelling_is_accepted_but_subdirectory_is_not(self):
        case,(base,repo,first,head)=self.fixture();actual=standalone_reviews.git
        def git(directory,*args,**kwargs):
            if args==('rev-parse','--show-toplevel'):return (repo.resolve().as_posix()+'/.\n').encode()
            return actual(directory,*args,**kwargs)
        with patch.object(standalone_reviews,'git',side_effect=git):
            selected,content=standalone_reviews.select_source(repo,{'mode':'working-tree'})
        self.assertEqual(selected['head_sha'],head);self.assertEqual(selected['mode'],'working-tree')
        child=repo/'child';child.mkdir()
        with self.assertRaisesRegex(WorkflowError,'root explicitly'):
            standalone_reviews.select_source(child,{'mode':'working-tree'})
    def test_git_ignored_executable_bits_do_not_invent_working_tree_changes(self):
        case,(base,repo,first,head)=self.fixture();case.git(repo,'config','core.filemode','false')
        # Keep this mode test independent of Windows checkout line endings.
        case.git(repo,'config','core.autocrlf','false')
        case.git(repo,'add','--renormalize','.')
        case.git(repo,'commit','--allow-empty','-qm','Owned literal-byte baseline')
        path=repo/'value.py';path.chmod(path.stat().st_mode|stat.S_IXUSR)
        self.assertEqual(case.git(repo,'status','--porcelain'),'')
        # Windows reports access(X_OK) on ordinary files. Git's configured
        # filemode semantics, including a staged mode change, still govern scope.
        with patch.object(os,'access',return_value=True):
            selected,content=standalone_reviews.select_source(repo,{'mode':'working-tree'})
        self.assertEqual(selected['changed_paths'],[])
        case.git(repo,'update-index','--chmod=+x','value.py')
        with patch.object(os,'access',return_value=True):
            selected,content=standalone_reviews.select_source(repo,{'mode':'working-tree'})
        self.assertEqual(content['value.py'][1],'100755')
        self.assertEqual(selected['changed_paths'],['value.py'])
