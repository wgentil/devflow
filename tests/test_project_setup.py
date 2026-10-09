import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.project_setup import inspect_project_setup, initialize_project_documents
from workflow_lib.store import WorkflowError

class ProjectSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()/'project'; self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
    def test_nested_inspection_read_only(self):
        nested=self.repo/'src';nested.mkdir()
        result=inspect_project_setup(nested)
        self.assertEqual(result['project_dir'],str(self.repo))
        self.assertEqual(result['choices'],['project-only','attach-org','create-org'])
        self.assertTrue(result['ground_interview']['required'])
        self.assertFalse(result['ground_interview']['ready'])
        self.assertFalse((self.repo/'docs').exists())
        self.assertFalse((self.repo/'.devflow').exists())
    def test_idempotent_project_only(self):
        first=initialize_project_documents(self.repo,{'mode':'project-only'},'one')
        manifest=self.repo/'docs/devflow-context.json'; before=manifest.read_bytes()
        second=initialize_project_documents(self.repo,{'mode':'project-only'},'two')
        self.assertEqual(manifest.read_bytes(),before);self.assertTrue(second['unchanged'])
        self.assertIsNone(first['manifest']['org'])
    def test_invalid_url_no_manifest(self):
        with self.assertRaises(WorkflowError): initialize_project_documents(self.repo,{'mode':'attach-org','url':str(self.repo/'missing')},'one')
        self.assertFalse((self.repo/'docs/devflow-context.json').exists())
    def test_create_requires_location(self):
        with self.assertRaises(WorkflowError): initialize_project_documents(self.repo,{'mode':'create-org','name':'Team'},'one')
    def test_attach_and_local_portability(self):
        org=Path(self.temp.name)/'team'
        created=initialize_project_documents(self.repo,{'mode':'create-org','name':'Team','target_dir':str(org)},'one')
        self.assertEqual(created['portability'],'local-only')
        other=Path(self.temp.name)/'other';other.mkdir();subprocess.run(['git','init','-q',str(other)],check=True)
        attached=initialize_project_documents(other,{'mode':'attach-org','url':str(org)},'two')
        self.assertEqual(attached['manifest']['org']['id'],created['manifest']['org']['id'])
        org.rename(org.with_name('moved'))
        with self.assertRaises(WorkflowError): initialize_project_documents(other,{'mode':'attach-org','url':str(org)},'three')
    def test_adopt_existing_document(self):
        path=self.repo/'rules.md';path.write_text('## CODE-1: Existing rule\nKeep this.\n')
        result=initialize_project_documents(self.repo,{'mode':'project-only','documents':[{'category':'coding-standards','path':'rules.md','rule_ids':['CODE-1']}]},'one')
        self.assertEqual(result['manifest']['documents'][0]['path'],'rules.md')
        self.assertEqual(path.read_text(encoding='utf-8'),'## CODE-1: Existing rule\nKeep this.\n')
    def test_non_git_rejected(self):
        with self.assertRaises(WorkflowError): inspect_project_setup(Path(self.temp.name))

    def test_invalid_document_does_not_write_manifest(self):
        (self.repo/'rules.md').write_text('Unidentified policy')
        with self.assertRaises(WorkflowError):
            initialize_project_documents(self.repo,{'mode':'project-only','documents':[{'category':'coding-standards','path':'rules.md','rule_ids':['CODE-1']}]},'one')
        self.assertFalse((self.repo/'docs/devflow-context.json').exists())
    def test_missing_operation_leaves_no_files(self):
        with self.assertRaises(WorkflowError): initialize_project_documents(self.repo,{'mode':'project-only'},'')
        self.assertFalse((self.repo/'docs').exists())
    def test_cli_inspect(self):
        runner=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        result=subprocess.run([sys.executable,str(runner),'setup','inspect','--project-dir',str(self.repo)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('project-only',result.stdout)

    def test_org_update_blocks_stale_runtime_checkout(self):
        org=Path(self.temp.name)/'team'
        first=initialize_project_documents(self.repo,{'mode':'create-org','name':'Team','target_dir':str(org)},'one')
        checkout=Path(first['org_checkout'])
        before=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'])
        manifest=self.repo/'docs/devflow-context.json';original=manifest.read_bytes()
        (org/'docs/new-policy.md').write_text('## NEW-1: New sealed policy\nRequired.\n')
        import json
        org_manifest=json.loads((org/'docs/devflow-org.json').read_text(encoding='utf-8'))
        org_manifest['documents']=[{'category':'coding-standards','path':'docs/new-policy.md','rule_ids':['NEW-1'],'sealed_rule_ids':['NEW-1']}]
        (org/'docs/devflow-org.json').write_text(json.dumps(org_manifest))
        subprocess.run(['git','-C',str(org),'add','.'],check=True)
        subprocess.run(['git','-C',str(org),'-c','user.name=Test','-c','user.email=test@example.com','commit','-qm','New sealed policy'],check=True)
        with self.assertRaises(WorkflowError) as error:
            initialize_project_documents(self.repo,{'mode':'attach-org','url':str(org)},'two')
        self.assertEqual(error.exception.code,'GOVERNING_SOURCE_STALE')
        self.assertEqual(manifest.read_bytes(),original)
        self.assertEqual(subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD']),before)

    def test_inspect_and_adopt_existing_openapi_yaml_without_rewriting(self):
        path = self.repo / 'existing-api.yaml'
        raw = 'openapi: 3.1.0\ninfo: {title: Example, version: "1"}\npaths: {}\n'
        path.write_text(raw)
        self.assertIn('existing-api.yaml', inspect_project_setup(self.repo)['existing_documents'])
        result = initialize_project_documents(self.repo, {'mode': 'project-only', 'documents': [
            {'category': 'application-contracts', 'path': 'existing-api.yaml', 'rule_ids': ['API']} ]}, 'adopt-api')
        self.assertEqual(result['manifest']['documents'][0]['path'], 'existing-api.yaml')
        self.assertEqual(path.read_text(encoding='utf-8'), raw)
