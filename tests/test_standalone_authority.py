"""Owned standalone authority regression; all model/user observations are fixtures."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
import test_review_driver
from workflow_lib.document_units import digest
from workflow_lib.review_sessions import read_session
from workflow_lib.session_evidence import prepare,package_current

class StandaloneAuthorityTests(unittest.TestCase):
    def fixture(self):
        case=test_review_driver.ReviewDriverTests();self.addCleanup(case.doCleanups)
        base,repo,path,request=case.owned_session()
        subject=read_session(path)['subject'];package=prepare(path,'original-authority')
        return subject,package
    def test_artifact_contains_actual_original_user_contract(self):
        subject,package=self.fixture()
        self.assertEqual(package.get('review_contract'),subject['review_contract'])
        self.assertEqual(package.get('review_contract_hash'),subject['review_contract_hash'])
    def test_forged_original_authority_body_cannot_be_current(self):
        subject,package=self.fixture()
        package['review_contract']=copy.deepcopy(subject['review_contract'])
        package['review_contract_hash']=subject['review_contract_hash']
        package['review_contract']['request']['intent']='Return sixty days; forged controller intent.'
        package['package_hash']=digest({k:v for k,v in package.items() if k!='package_hash'})
        self.assertFalse(package_current(subject,package))

if __name__=='__main__':unittest.main(defaultTest='StandaloneAuthorityTests',verbosity=2)
