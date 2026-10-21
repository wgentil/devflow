import copy
import hashlib
import json
import sys
from pathlib import Path
import subprocess
import unittest
import test_item_review_recovery as review_fixtures
from workflow_lib.reviews import prepare_review,record_review
from workflow_lib.host_completion import package_current


class ReviewInputScopeTests(unittest.TestCase):
    def fixture(self):
        f=review_fixtures.ItemReviewRecoveryTests();f.setUp();self.addCleanup(f.doCleanups)
        repo=f.f.repo
        (repo/'test_scope.py').write_text('# stable test 東京\n',encoding='utf-8')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','tests\n\nWork-Item: W1'],cwd=repo,check=True)
        f.repos['repo-1']['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        f.run['verification_proofs']={'green':{'kind':'code','phase':'GREEN','item_id':'W1','token':'t1','repo_id':'repo-1',
            'passed':True,'test_hashes':{'test_scope.py':hashlib.sha256((repo/'test_scope.py').read_bytes()).hexdigest()}}}
        return f
    def package(self,f,scope=None):
        package=prepare_review(f.run,'item',f.repos,item_id='W1',input_paths=scope or {'repo-1':['src/app.py','test_scope.py']})
        f.run.setdefault('review_packages',{})[package['package_hash']]=package
        return package
    def pass_review(self,f,pkg):
        return record_review(f.run,pkg['package_hash'],f.reviewer,{'package_hash':pkg['package_hash'],'item_id':'W1','verdict':'pass','findings':[]})
    def test_unrelated_untracked_and_committed_work_is_allowed_by_both_consumers(self):
        f=self.fixture();pkg=self.package(f);repo=f.f.repo
        (repo/'W2.py').write_text('# unrelated\n',encoding='utf-8')
        self.assertEqual(self.pass_review(f,pkg)['verdict'],'pass');self.assertTrue(package_current(f.run,pkg))
        subprocess.run(['git','add','W2.py'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','W2\n\nWork-Item: W2'],cwd=repo,check=True)
        self.assertEqual(self.pass_review(f,pkg)['verdict'],'pass');self.assertTrue(package_current(f.run,pkg))
    def test_packaged_inputs_detect_content_index_deletion_rename_and_type_changes(self):
        from workflow_lib.review_inputs import compare_review_inputs
        for mode in ('edit','staged','delete','rename','symlink'):
            f=self.fixture();pkg=self.package(f);path=f.f.repo/'src/app.py'
            if mode in {'edit','staged'}:
                path.write_text('VALUE = 9\n',encoding='utf-8')
                if mode=='staged':subprocess.run(['git','add','.'],cwd=f.f.repo,check=True)
            elif mode=='delete':path.unlink()
            elif mode=='rename':path.rename(path.with_name('renamed.py'))
            else:
                path.unlink()
                try:path.symlink_to(Path(f.f.temp.name)/'outside')
                except OSError:self.skipTest('symlinks unavailable')
            with self.subTest(mode=mode):
                result=compare_review_inputs(f.f.repo,pkg['repositories']['repo-1']['input_scope'])
                self.assertFalse(result['current']);self.assertIn('src/app.py',result['changed_paths'])
                with self.assertRaises(ValueError) as error:self.pass_review(f,pkg)
                self.assertIn('src/app.py',str(error.exception));self.assertFalse(package_current(f.run,pkg))
    def test_missing_tests_or_unknown_scope_keeps_whole_tree_liveness(self):
        f=self.fixture();pkg=self.package(f,{'repo-1':['src/app.py']})
        self.assertEqual(pkg['repositories']['repo-1']['liveness_mode'],'whole')
        (f.f.repo/'W2.py').write_text('# unrelated\n',encoding='utf-8')
        with self.assertRaises(ValueError):self.pass_review(f,pkg)
        f=self.fixture();f.run['verification_proofs']={};pkg=self.package(f)
        self.assertEqual(pkg['repositories']['repo-1']['liveness_mode'],'whole')
    def test_plan_governing_artifact_and_attempt_changes_invalidate_scoped_package(self):
        for change in ('plan','governing','artifact','attempt'):
            f=self.fixture();pkg=self.package(f)
            if change=='plan':f.run['plan']['work_items'][0]['acceptance_criteria']=[{'kind':'code-test','text':'new'}]
            elif change=='governing':f.run['governing_digest']='changed'
            elif change=='artifact':f.run['artifacts']['result']={'sha256':'b'*64}
            else:f.run['items']['W1']['attempts'][-1]['token']='new'
            with self.subTest(change=change),self.assertRaises(ValueError):self.pass_review(f,pkg)
            self.assertFalse(package_current(f.run,pkg))
    def test_repository_specific_snapshots_and_bounded_diagnostics(self):
        from workflow_lib.review_inputs import capture_review_inputs,compare_review_inputs
        f=self.fixture();other=self.fixture()
        first=capture_review_inputs(f.f.repo,['src/app.py']);second=capture_review_inputs(other.f.repo,['src/app.py'])
        (other.f.repo/'src/app.py').write_text('different',encoding='utf-8')
        self.assertTrue(compare_review_inputs(f.f.repo,first)['current']);self.assertFalse(compare_review_inputs(other.f.repo,second)['current'])
        names=[f'file-{i}' for i in range(70)]
        for name in names:(f.f.repo/name).write_text('before',encoding='utf-8')
        snapshot=capture_review_inputs(f.f.repo,names)
        for name in names:(f.f.repo/name).write_text('after',encoding='utf-8')
        diff=compare_review_inputs(f.f.repo,snapshot)
        self.assertEqual(len(diff['changed_paths']),64);self.assertEqual(diff['omitted_count'],6)
        with self.assertRaises(ValueError):capture_review_inputs(f.f.repo,['../outside'])
    def test_legacy_branch_and_acceptance_packages_stay_whole_tree(self):
        for role in ('item','branch','acceptance'):
            f=self.fixture();pkg=prepare_review(f.run,role,f.repos)
            f.run.setdefault('review_packages',{})[pkg['package_hash']]=pkg
            (f.f.repo/'untracked.py').write_text('# new\n',encoding='utf-8')
            with self.subTest(role=role),self.assertRaises(ValueError) as error:
                record_review(f.run,pkg['package_hash'],{**f.reviewer,'role':role},{'package_hash':pkg['package_hash'],'item_id':'W1','verdict':'pass','findings':[]})

    def test_declared_absent_input_is_part_of_package_and_creation_invalidates_it(self):
        f=self.fixture();pkg=self.package(f,{'repo-1':['src/app.py','test_scope.py','optional-config.json']})
        self.assertIn('optional-config.json',pkg['input_paths'])
        (f.f.repo/'optional-config.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError) as error:self.pass_review(f,pkg)
        self.assertIn('optional-config.json',str(error.exception))

    def test_whole_tree_failure_names_new_untracked_path(self):
        f=self.fixture();pkg=prepare_review(f.run,'branch',f.repos)
        f.run.setdefault('review_packages',{})[pkg['package_hash']]=pkg
        (f.f.repo/'new-file.py').write_text('# new',encoding='utf-8')
        with self.assertRaises(ValueError) as error:
            record_review(f.run,pkg['package_hash'],{**f.reviewer,'role':'branch'},
                {'package_hash':pkg['package_hash'],'verdict':'pass','findings':[]})
        self.assertIn('new-file.py',str(error.exception))

    def test_scoped_cli_package_and_record_allow_unrelated_next_item(self):
        f=self.fixture();f.seed()
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        argv=[sys.executable,str(entry),'review','package','--root',str(f.root),'--run-id','run-1',
            '--role','item','--item','W1','--repositories-json',json.dumps(f.repos),
            '--input-paths-json',json.dumps({'repo-1':['src/app.py','test_scope.py']})]
        result=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        pkg=json.loads(result.stdout)['package'];self.assertEqual(pkg['repositories']['repo-1']['liveness_mode'],'scoped')
        (f.f.repo/'next-item.py').write_text('# unrelated',encoding='utf-8')
        report={'package_hash':pkg['package_hash'],'item_id':'W1','verdict':'pass','findings':[]}
        result=subprocess.run([sys.executable,str(entry),'review','record','--root',str(f.root),'--run-id','run-1',
            '--package-hash',pkg['package_hash'],'--actor-id','item-reviewer','--invocation-ref','fixture://independent',
            '--tool-available','--report-json',json.dumps(report)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_unicode_and_spaced_scoped_paths_are_literal(self):
        from workflow_lib.review_inputs import capture_review_inputs,compare_review_inputs
        f=self.fixture();name='café 東京 file.py'
        (f.f.repo/name).write_text('before',encoding='utf-8')
        snapshot=capture_review_inputs(f.f.repo,[name])
        self.assertTrue(compare_review_inputs(f.f.repo,snapshot)['current'])
        (f.f.repo/name).write_text('after',encoding='utf-8')
        self.assertEqual(compare_review_inputs(f.f.repo,snapshot)['changed_paths'],[name])

    def test_omitted_dirty_index_inputs_fall_back_and_stay_bound(self):
        for mode in ('staged-add','tracked-edit','tracked-delete','tracked-rename'):
            with self.subTest(mode=mode):
                f=self.fixture();repo=f.f.repo;dirty=repo/'dirty.py'
                if mode!='staged-add':
                    dirty.write_text('before',encoding='utf-8')
                    subprocess.run(['git','add','.'],cwd=repo,check=True)
                    subprocess.run(['git','commit','-qm','Other work\n\nWork-Item: W2'],cwd=repo,check=True)
                    f.repos['repo-1']['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
                if mode=='tracked-delete':dirty.unlink()
                elif mode=='tracked-rename':dirty.rename(repo/'renamed.py')
                else:dirty.write_text('dirty',encoding='utf-8')
                if mode!='tracked-edit':subprocess.run(['git','add','-A'],cwd=repo,check=True)
                pkg=self.package(f)
                self.assertEqual(pkg['repositories']['repo-1']['liveness_mode'],'whole')
                self.assertEqual(pkg['repositories']['repo-1']['scope_reason'],'DECLARED_INPUT_SCOPE_INCOMPLETE')
                dirty.write_text('changed after packaging',encoding='utf-8')
                subprocess.run(['git','add','-A'],cwd=repo,check=True)
                with self.assertRaises(ValueError):self.pass_review(f,pkg)
                self.assertFalse(package_current(f.run,pkg))
