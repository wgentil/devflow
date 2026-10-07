import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.catalog import validate_catalog

class CatalogTests(unittest.TestCase):
    def test_catalog_closure_profiles_and_cycles(self):
        valid = {'version': 1, 'stages': [{'id':'build','prerequisites':[]}, {'id':'review','prerequisites':['build']}], 'profiles':['generic','cobol']}
        self.assertTrue(validate_catalog(valid, {'version':1,'profiles':{'generic':{},'cobol':{}}})['valid'])
        self.assertFalse(validate_catalog({**valid,'stages':[{'id':'x','prerequisites':['missing']}]}, {'profiles':{'generic':{},'cobol':{}}})['valid'])
        self.assertFalse(validate_catalog({**valid,'stages':[{'id':'x','prerequisites':['y']},{'id':'y','prerequisites':['x']}]}, {'profiles':{'generic':{},'cobol':{}}})['valid'])
