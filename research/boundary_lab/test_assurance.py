"""Offline behavior contracts; no training or scientific efficacy assertions."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest
import assurance_demo as demo
import evaluation_contract as ec
import support_memory as sm
import verifier_search as vs


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'memory.sqlite'
        self.m=sm.SupportMemory(self.path)
        self.allow=lambda p,t,a: p=='operator' and t=='research'
    def tearDown(self):
        self.m.close();self.tmp.cleanup()
    def add(self,events,head=None):
        return self.m.apply(events,expected_head=self.m.head() if head is None else head,principal='operator',authorize=self.allow)
    def view(self,now=1000):
        return self.m.handles(tenant='research',principal='operator',now=now,authorize=self.allow)
    def states(self,now=1000):
        return {x['id']:x['support_state'] for x in self.view(now)['handles']}
    def test_empty_ledger(self):
        self.assertEqual(self.m.head(),sm.ZERO);self.assertEqual(self.states(),{})
    def test_alternative_support_survives(self):
        self.add([demo.source('A'),demo.source('B'),demo.claim('C',[['A'],['B']])])
        self.add([{'tenant':'research','op':'withdraw','id':'A','reason':'REVOKED'}])
        self.assertEqual(self.states()['C'],'SUPPORTED')
    def test_and_support_requires_all(self):
        self.add([demo.source('A'),demo.source('B'),demo.claim('C',[['A','B']])])
        self.add([{'tenant':'research','op':'withdraw','id':'A','reason':'REVOKED'}])
        self.assertEqual(self.states()['C'],'UNSUPPORTED')
    def test_transitive_withdrawal(self):
        self.add([demo.source('A'),demo.claim('C',[['A']]),demo.claim('D',[['C']])])
        self.add([{'tenant':'research','op':'withdraw','id':'A','reason':'REVOKED'}])
        self.assertEqual(self.states()['D'],'UNSUPPORTED')
    def test_new_revision_does_not_rebind_old_claim(self):
        self.add([demo.source('A'),demo.claim('C',[['A']])])
        self.add([{'tenant':'research','op':'withdraw','id':'A','reason':'SUPERSEDED'},demo.source('A-new')])
        self.assertEqual(self.states()['C'],'UNSUPPORTED')
        self.assertEqual(self.m.db.execute('SELECT count(*) FROM events').fetchone()[0],4)
    def test_expiry_checked_at_each_read(self):
        self.add([demo.source('A')]);self.assertEqual(self.states(1999)['A'],'SUPPORTED')
        self.assertEqual(self.states(2000)['A'],'EXPIRED')
    def test_rights_false_not_active(self):
        a=demo.source('A');a['read_allowed']=False;self.add([a]);self.assertEqual(self.states()['A'],'RIGHTS_UNAVAILABLE')
    def test_missing_rights_rejected(self):
        a=demo.source('A');del a['read_allowed']
        with self.assertRaises(ValueError):self.add([a])
    def test_numeric_rights_rejected(self):
        a=demo.source('A');a['read_allowed']=1
        with self.assertRaises(ValueError):self.add([a])
    def test_mutable_revision_rejected(self):
        a=demo.source('A');a['revision']='main'
        with self.assertRaises(ValueError):self.add([a])
    def test_node_ids_immutable(self):
        self.add([demo.source('A')])
        with self.assertRaises(ValueError):self.add([demo.source('A')])
    def test_forward_dependency_rejected(self):
        with self.assertRaises(ValueError):self.add([demo.claim('C',[['future']]),demo.source('future')])
    def test_self_cycle_rejected(self):
        with self.assertRaises(ValueError):self.add([demo.claim('A',[['A']])])
    def test_cross_tenant_support_rejected(self):
        self.m.apply([demo.source('B',tenant='other')],expected_head=sm.ZERO,principal='operator',authorize=lambda *x:True)
        with self.assertRaises(ValueError):self.add([demo.claim('A',[['B']])])
    def test_cross_tenant_read_hidden(self):
        self.m.apply([demo.source('B',tenant='other')],expected_head=sm.ZERO,principal='operator',authorize=lambda *x:True)
        self.assertEqual(self.states(),{})
    def test_batch_rolls_back(self):
        with self.assertRaises(ValueError):self.add([demo.source('A'),demo.claim('C',[['missing']])])
        self.assertEqual(self.m.head(),sm.ZERO)
    def test_authorizer_denial(self):
        with self.assertRaises(PermissionError):self.m.apply([demo.source('A')],expected_head=sm.ZERO,principal='operator',authorize=lambda *x:False)
        self.assertEqual(self.m.head(),sm.ZERO)
    def test_truthy_authorizer_not_enough(self):
        with self.assertRaises(PermissionError):self.m.apply([demo.source('A')],expected_head=sm.ZERO,principal='operator',authorize=lambda *x:1)
    def test_read_denial(self):
        with self.assertRaises(PermissionError):self.m.handles(tenant='research',principal='operator',now=1000,authorize=lambda *x:False)
    def test_stale_writer_rejected(self):
        old=self.m.head();self.add([demo.source('A')])
        with self.assertRaises(ValueError):self.add([demo.source('B')],old)
    def test_stale_reader_rejected(self):
        self.add([demo.source('A')])
        with self.assertRaises(ValueError):self.m.handles(tenant='research',principal='operator',now=1000,authorize=self.allow,expected_head=sm.ZERO)
    def test_two_connections_cas(self):
        other=sm.SupportMemory(self.path)
        old=other.head();self.add([demo.source('A')])
        try:
            with self.assertRaises(ValueError):other.apply([demo.source('B')],expected_head=old,principal='operator',authorize=self.allow)
        finally:other.close()
    def test_locked_database_no_overwrite(self):
        other=sm.SupportMemory(self.path)
        self.m.db.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(sqlite3.OperationalError):other.apply([demo.source('B')],expected_head=sm.ZERO,principal='operator',authorize=self.allow)
        finally:self.m.db.execute('ROLLBACK');other.close()
        self.assertEqual(self.m.head(),sm.ZERO)
    def test_restart_preserves_chain(self):
        head=self.add([demo.source('A')]);self.m.close();self.m=sm.SupportMemory(self.path);self.assertEqual(self.m.head(),head)
    def test_tampered_payload_detected(self):
        self.add([demo.source('A')]);self.m.db.execute("UPDATE events SET payload='{}' WHERE seq=1")
        with self.assertRaises(ValueError):self.view()
    def test_deletion_detected_against_retained_head(self):
        head=self.add([demo.source('A')]);self.m.db.execute('DELETE FROM events')
        with self.assertRaises(ValueError):self.m.handles(tenant='research',principal='operator',now=1000,authorize=self.allow,expected_head=head)
    def test_duplicate_support_rejected(self):
        with self.assertRaises(ValueError):self.add([demo.source('A'),demo.claim('C',[['A'],['A']])])
    def test_empty_support_rejected(self):
        with self.assertRaises(ValueError):self.add([demo.claim('C',[[]])])
    def test_no_content_or_authority_in_projection(self):
        self.add([demo.source('A')]);v=self.view();self.assertNotIn('content',v['handles'][0]);self.assertFalse(v['training_authority']);self.assertFalse(v['execution_authority'])
    def test_input_copied(self):
        a=demo.source('A');self.add([a]);a['read_allowed']=False;self.assertEqual(self.states()['A'],'SUPPORTED')
    def test_boolean_time_rejected(self):
        with self.assertRaises(ValueError):self.view(True)
    def test_all_two_source_revocation_combinations(self):
        for selected in ([],['A'],['B'],['A','B']):
            path=Path(self.tmp.name)/('scenario-'+str(len(list(Path(self.tmp.name).glob('scenario*'))))+'.db')
            m=sm.SupportMemory(path)
            try:
                h=m.apply([demo.source('A'),demo.source('B'),demo.claim('or',[['A'],['B']]),demo.claim('and',[['A','B']])],expected_head=sm.ZERO,principal='operator',authorize=self.allow)
                if selected:m.apply([{'tenant':'research','op':'withdraw','id':x,'reason':'REVOKED'} for x in selected],expected_head=h,principal='operator',authorize=self.allow)
                v=m.handles(tenant='research',principal='operator',now=1000,authorize=self.allow);s={x['id']:x['support_state'] for x in v['handles']}
                self.assertEqual(s['or']=='SUPPORTED',len(selected)<2);self.assertEqual(s['and']=='SUPPORTED',not selected)
            finally:m.close()


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases=[{'id':'s','family':'valid','expected':'SUPPORTED','task_sha256':'1'*64},{'id':'u','family':'boundary','expected':'UNSUPPORTED','task_sha256':'2'*64}]
        self.plan=ec.frozen_plan(self.cases,model_digest='a'*64,tokenizer_digest='b'*64,grader_digest='c'*64)
        self.rows=[{'arm':a,'case_id':c['id'],'seed':749,'status':'OK','decision':c['expected'],'input_tokens':100,'output_tokens':10,'model_digest':'a'*64,'task_sha256':c['task_sha256']} for a in ec.ARMS for c in self.cases]
    def score(self,rows=None,plan=None):return ec.score(self.plan if plan is None else plan,self.rows if rows is None else rows,expected_plan_sha256=ec.digest(self.plan))
    def test_oracle_control(self):
        a=self.score()['arms']['A'];self.assertEqual(a['supported_answer_accuracy'],1);self.assertEqual(a['unsupported_acceptance_rate'],0)
    def test_all_abstain_not_success(self):
        for row in self.rows:row['decision']='UNKNOWN'
        self.assertEqual(self.score()['arms']['A']['supported_answer_accuracy'],0)
    def test_all_accept_detected(self):
        for row in self.rows:row['decision']='SUPPORTED'
        self.assertEqual(self.score()['arms']['A']['unsupported_acceptance_rate'],1)
    def test_missing_results_no_rate(self):
        out=self.score(self.rows[:-1]);self.assertIsNone(out['arms']['D']['unsupported_acceptance_rate']);self.assertEqual(out['arms']['D']['missing_attempts'],1)
    def test_failed_output_kept(self):
        self.rows[-1].update(status='ERROR',decision=None,input_tokens=None,output_tokens=None)
        out=self.score();self.assertEqual(out['arms']['D']['invalid_or_failed'],1);self.assertIsNone(out['arms']['D']['supported_answer_accuracy'])
    def test_truncation_not_answer(self):
        self.rows[-1]['status']='TRUNCATED'
        with self.assertRaises(ValueError):self.score()
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):self.score(self.rows+[self.rows[0]])
    def test_extra_case_rejected(self):
        self.rows[-1]['case_id']='invented'
        with self.assertRaises(ValueError):self.score()
    def test_model_drift_rejected(self):
        self.rows[-1]['model_digest']='d'*64
        with self.assertRaises(ValueError):self.score()
    def test_task_swap_rejected(self):
        self.rows[-1]['task_sha256']='9'*64
        with self.assertRaises(ValueError):self.score()
    def test_contract_changed_rejected(self):
        p=deepcopy(self.plan);p['max_output_tokens']=128
        with self.assertRaises(ValueError):self.score(plan=p)
    def test_self_rehashed_escalation_rejected(self):
        p=deepcopy(self.plan);p['production_qualification']=True
        with self.assertRaises(ValueError):ec.score(p,self.rows,expected_plan_sha256=ec.digest(p))
    def test_budget_violation(self):
        self.rows[0]['input_tokens']=99999
        with self.assertRaises(ValueError):self.score()
    def test_bool_count_rejected(self):
        self.rows[0]['input_tokens']=True
        with self.assertRaises(ValueError):self.score()
    def test_bool_seed_rejected(self):
        self.rows[0]['seed']=True
        with self.assertRaises(ValueError):self.score()
    def test_zero_denominator_unavailable(self):
        p=ec.frozen_plan(self.cases[:1],model_digest='a'*64,tokenizer_digest='b'*64,grader_digest='c'*64)
        out=ec.score(p,[r for r in self.rows if r['case_id']=='s'],expected_plan_sha256=ec.digest(p));self.assertIsNone(out['arms']['A']['unsupported_acceptance_rate'])
    def test_missing_tokenizer_identity(self):
        with self.assertRaises(ValueError):ec.frozen_plan(self.cases,model_digest='a'*64,tokenizer_digest='unknown',grader_digest='c'*64)
    def test_duplicate_case_rejected(self):
        with self.assertRaises(ValueError):ec.frozen_plan(self.cases*2,model_digest='a'*64,tokenizer_digest='b'*64,grader_digest='c'*64)
    def test_plan_owns_its_case_copy(self):
        self.cases[0]['expected']='UNSUPPORTED';self.assertEqual(self.plan['cases'][0]['expected'],'SUPPORTED')


class SearchTests(unittest.TestCase):
    def test_finite_search_rejects_bad_candidates(self):
        result=vs.run_search();r={x['candidate']:x for x in result['candidates']}
        self.assertEqual(r['dfs_candidate']['mismatches'],0)
        self.assertGreater(r['negative_control_backward_only']['mismatches'],0)
        self.assertGreater(r['negative_control_always_true']['mismatches'],0)
        self.assertIsNone(r['negative_control_always_true']['median_full_sweep_ns'])
        self.assertFalse(result['production_promotion'])
    def test_dfs_zero_node_and_self_loop(self):
        self.assertFalse(vs.dfs_acyclic([(0,0)]));self.assertFalse(vs.dfs_acyclic([(0,1),(1,0)]));self.assertTrue(vs.dfs_acyclic([(1,0)]))
    def test_dfs_bad_domain(self):
        with self.assertRaises(ValueError):vs.dfs_acyclic([(True,0)])
    def test_demo_receipt_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'run';r=demo.run(p)
            for name,entry in r['outputs'].items():self.assertEqual(sha256((p/name).read_bytes()).hexdigest(),entry['sha256'])
            with self.assertRaises(FileExistsError):demo.run(p)


class LocalDiagnosticTests(unittest.TestCase):
    def test_decision_valid(self):
        import local_diagnostic as d
        self.assertEqual(d.parse_decision('{"decision":"SUPPORTED"}'), 'SUPPORTED')
    def test_duplicate_output_rejected(self):
        import local_diagnostic as d
        with self.assertRaises(ValueError):d.parse_decision('{"decision":"SUPPORTED","decision":"UNKNOWN"}')
    def test_extra_output_rejected(self):
        import local_diagnostic as d
        with self.assertRaises(ValueError):d.parse_decision('{"decision":"SUPPORTED","promote":true}')
    def test_unknown_label_rejected(self):
        import local_diagnostic as d
        with self.assertRaises(ValueError):d.parse_decision('{"decision":"PASS"}')
    def test_non_object_rejected(self):
        import local_diagnostic as d
        with self.assertRaises(ValueError):d.parse_decision('[]')
    def test_output_budget(self):
        import local_diagnostic as d
        with self.assertRaises(ValueError):d.parse_decision(' ' * 1025)
    def test_existing_loaded_model_stops_inference(self):
        from unittest.mock import patch
        import local_diagnostic as d
        with tempfile.TemporaryDirectory() as td, patch.object(d, 'request', return_value={'models':[{'name':'other-owner'}]}) as req:
            r=d.run(Path(td)/'run', 'test:latest', 'a'*64)
            self.assertEqual(r['requests_started'],0)
            self.assertEqual(r['status'],'HOLD')
            self.assertEqual(req.call_count,1)
    def test_tasks_have_two_positive_and_two_negative_controls(self):
        import local_diagnostic as d
        self.assertEqual(sum(t['expected']=='SUPPORTED' for t in d.tasks()),2)
        self.assertEqual(sum(t['expected']=='UNSUPPORTED' for t in d.tasks()),2)


class DiagnosticExitTests(unittest.TestCase):
    def run_result(self, result):
        from unittest.mock import patch
        import local_diagnostic as d
        with patch.object(d, 'run', return_value=result):
            return d.main(['--out', 'unused', '--model', 'test:latest', '--expected-model-digest', 'a'*64])
    def test_hold_is_nonzero(self):
        self.assertEqual(self.run_result({'status':'HOLD'}),2)
    def test_incomplete_diagnostic_is_nonzero(self):
        self.assertEqual(self.run_result({'status':'DIAGNOSTIC_RECORDED','valid_responses':15}),2)
    def test_drift_is_nonzero(self):
        self.assertEqual(self.run_result({'status':'IDENTITY_DRIFT_HOLD','valid_responses':16}),2)
    def test_complete_diagnostic_is_zero_not_qualification(self):
        self.assertEqual(self.run_result({'status':'DIAGNOSTIC_RECORDED','valid_responses':16}),0)


if __name__=='__main__':unittest.main(verbosity=2)
