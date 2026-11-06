"""Public bounded driver routing; execution proofs live in test_review_driver."""
import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from commands import repair,review

class DriverCliTests(unittest.TestCase):
    def parser(self,module):
        parser=argparse.ArgumentParser();module.register_commands(parser.add_subparsers(dest='command'));return parser
    def test_workflow_run_requires_finite_bound_and_routes_exact_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text('{}')
            args=self.parser(repair).parse_args(['repair','run','--root',temp,'--run-id','run','--input',str(path),'--operation-id','op','--max-actions','7'])
            with patch('workflow_lib.review_driver.run_orchestration',return_value={'sentinel':True}) as execute:
                self.assertEqual(repair.dispatch(args),{'sentinel':True})
                execute.assert_called_once_with(Path(temp).resolve(),{'run_id':'run'},'op',7)
    def test_session_run_and_recovery_route_explicit_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text('{}');session=(Path(temp)/'session.json').resolve()
            for command,function,extra in [('run','run_orchestration',['--max-actions','1']),('recover','recover_orchestration',[])]:
                args=self.parser(repair).parse_args(['repair',command,'--session',str(session),'--input',str(path),'--operation-id','op',*extra])
                with patch('workflow_lib.review_driver.'+function,return_value={'ok':True}) as execute:
                    self.assertEqual(repair.dispatch(args),{'ok':True})
                    self.assertEqual(execute.call_args.args[:3],(session,{'session':True},'op'))
    def test_review_next_uses_one_driver_action_only_when_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text('{}');session=(Path(temp)/'session.json').resolve()
            args=self.parser(review).parse_args(['review','next','--session',str(session),'--input',str(path),'--operation-id','op','--execute'])
            with patch('workflow_lib.review_sessions.read_session',return_value={'subject':{'review_orchestration':{'enabled':True}}}),patch('workflow_lib.review_driver.advance_orchestration',return_value={'ok':True}) as execute:
                self.assertEqual(review.dispatch(args),{'ok':True})
                execute.assert_called_once_with(session,{'session':True},'op')

    def test_repair_scope_proposal_and_authorization_are_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text('{}');session=(Path(temp)/'session.json').resolve()
            for command,function,expected in [('repair-proposal','prepare_repair',(session,{})),('authorize-repair','authorize_repair',(session,{},'op'))]:
                args=self.parser(review).parse_args(['review',command,'--session',str(session),'--input',str(path),'--operation-id','op'])
                with patch('workflow_lib.session_repair.'+function,return_value={'ok':True}) as execute:
                    self.assertEqual(review.dispatch(args),{'ok':True});execute.assert_called_once_with(*expected)

    def test_additive_test_command_routes_actual_selected_scope(self):
        from commands import build
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text('{"input_paths":["regression.py"],"target_ids":["boundary"],"reason":"Cover boundary"}')
            args=self.parser(build).parse_args(['build','extend-tests','--root',temp,'--run-id','r','--item','W1','--input',str(path),'--operation-id','op'])
            with patch('workflow_lib.test_extensions.admit_extension',return_value={'ok':True}) as execute:
                self.assertEqual(build.dispatch(args),{'ok':True})
                self.assertEqual(execute.call_args.args[1],{'run_id':'r','item_id':'W1','input_paths':['regression.py'],'target_ids':['boundary'],'reason':'Cover boundary'})
