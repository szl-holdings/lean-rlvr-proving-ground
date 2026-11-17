"""Offline software/finite-oracle tests, not model evaluations."""
from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
import boundary_lab as b


class BoundaryTests(unittest.TestCase):
    def test_backward_chain(self):
        self.assertTrue(b.backward([(2, 1), (1, 0)]))
        self.assertTrue(b.acyclic([(2, 1), (1, 0)]))

    def test_two_cycle(self):
        self.assertFalse(b.backward([(0, 1), (1, 0)]))
        self.assertFalse(b.acyclic([(0, 1), (1, 0)]))

    def test_forward_edge_need_not_cycle(self):
        self.assertFalse(b.backward([(0, 1)]))
        self.assertTrue(b.acyclic([(0, 1)]))

    def test_self_loop(self):
        self.assertFalse(b.acyclic([(0, 0)]))

    def test_empty_graph(self):
        self.assertTrue(b.acyclic([]))

    def test_bool_not_nat(self):
        with self.assertRaises(ValueError): b.backward([(True, 0)])

    def test_negative_not_nat(self):
        with self.assertRaises(ValueError): b.backward([(-1, 0)])

    def test_malformed_edge(self):
        with self.assertRaises(ValueError): b.backward([(1, 0, 2)])

    def test_edge_budget(self):
        with self.assertRaises(ValueError): b.backward([(1, 0)] * 101)

    def test_fifo_control(self):
        self.assertEqual(b.fifo_trace(['send', 'deliver'], 3), [3])

    def test_retry_duplicates(self):
        self.assertEqual(b.fifo_trace(['send','deliver','retry','deliver']), [1, 1])

    def test_bad_queue_transition(self):
        with self.assertRaises(ValueError): b.fifo_trace(['deliver'])

    def test_unknown_transition(self):
        with self.assertRaises(ValueError): b.fifo_trace(['install'])

    def test_trace_budget(self):
        with self.assertRaises(ValueError): b.fifo_trace(['send'] * 21)

    def test_single_writer_monotone(self):
        self.assertTrue(b.strictly_increasing(b.sequence_trace(['emit_a'] * 4)))

    def test_restart_counterexample(self):
        self.assertEqual(b.sequence_trace(['emit_a','reset','emit_a']), [0, 0])

    def test_two_writers_counterexample(self):
        self.assertEqual(b.sequence_trace(['emit_a','emit_b']), [0, 0])

    def test_sequence_unknown(self):
        with self.assertRaises(ValueError): b.sequence_trace(['bad'])

    def test_rank_identity(self):
        self.assertEqual(b.rank_and_null([[1, 0], [0, 1]]), (2, None))

    def test_rank_deficient(self):
        rank, null = b.rank_and_null([[1, 1], [2, 2]])
        self.assertEqual(rank, 1)
        self.assertIsNotNone(null)
        self.assertEqual(sum(null) % 257, 0)

    def test_null_vector_all_small_binary_matrices(self):
        for values in product((0, 1), repeat=6):
            matrix = [list(values[:3]), list(values[3:])]
            rank, vector = b.rank_and_null(matrix)
            self.assertLess(rank, 3)
            self.assertTrue(any(vector))
            self.assertTrue(all(sum(x*y for x,y in zip(row, vector)) % 257 == 0 for row in matrix))

    def test_ragged_rejected(self):
        with self.assertRaises(ValueError): b.rank_and_null([[1, 2], [3]])

    def test_bool_matrix_rejected(self):
        with self.assertRaises(ValueError): b.rank_and_null([[True]])

    def test_vandermonde_domain(self):
        with self.assertRaises(ValueError): b.vandermonde(250)

    def test_finite_suite(self):
        r = b.finite_validation()
        self.assertEqual((r['directed_graphs_on_four_nodes'], r['backward_graphs'], r['within_domain_cycle_failures']), (4096, 64, 0))
        self.assertEqual((r['vandermonde_survivor_subsets'], r['full_rank_subsets']), (210, 210))

    def test_minimum_witness_lengths(self):
        w = b.minimum_witnesses()
        self.assertEqual(len(w['F4']['edges']), 2)
        self.assertEqual(w['F7']['trace_length'], 4)
        self.assertEqual(w['F22']['trace_length'], 3)
        self.assertEqual(w['F18']['rank'], 5)
        self.assertFalse(w['locked_theorem_refuted'])

    def test_cases_deterministic(self):
        self.assertEqual(b.canonical(b.make_cases()), b.canonical(b.make_cases()))

    def test_split_no_exact_or_family_leakage(self):
        x = b.validate_split(b.make_cases())
        self.assertEqual(x['generator_family_overlap'], 0)
        self.assertEqual(x['exact_task_overlap'], 0)
        self.assertFalse(x['independently_sealed_holdout'])

    def test_family_leakage_rejected(self):
        rows = deepcopy(b.make_cases())
        rows[-1]['generator_family'] = rows[0]['generator_family']
        with self.assertRaises(ValueError): b.validate_split(rows)

    def test_exact_leakage_rejected(self):
        rows = deepcopy(b.make_cases())
        rows[-1]['task_fingerprint'] = rows[0]['task_fingerprint']
        with self.assertRaises(ValueError): b.validate_split(rows)

    def test_duplicate_id_rejected(self):
        rows = b.make_cases();rows.append(rows[0])
        with self.assertRaises(ValueError): b.validate_split(rows)

    def test_all_output_is_synthetic_and_not_admitted(self):
        for r in b.make_cases():
            self.assertTrue(r['synthetic'])
            self.assertEqual(r['training_admission'], 'REVIEW_REQUIRED')
            self.assertFalse(r['locked_status_changed'])
            self.assertFalse(r['model_evaluation'])

    def test_f18_hypothesis_does_not_certify_codec(self):
        bad = [r for r in b.make_cases() if r['formula_id'] == 'F18' and r['label'] == 'RUNTIME_COUNTEREXAMPLE']
        self.assertTrue(bad)
        self.assertTrue(all(r['source_hypotheses_apply_to_original_encoding'] for r in bad))

    def test_strict_json_duplicates(self):
        with self.assertRaises(ValueError): b.strict_json(b'{"a":1,"a":2}')

    def test_strict_json_nonfinite(self):
        with self.assertRaises(ValueError): b.strict_json(b'{"a":NaN}')

    def test_strict_json_float_overflow(self):
        with self.assertRaises(ValueError): b.strict_json(b'{"a":1e999}')

    def test_source_changed_rejected(self):
        s=json.loads(Path(__file__).with_name('sources.json').read_text());s['formula_revision']='main'
        with self.assertRaises(ValueError): b.validate_sources(s)

    def test_training_permission_escalation_rejected(self):
        s=json.loads(Path(__file__).with_name('sources.json').read_text());s['datasets'][0]['use']='train'
        with self.assertRaises(ValueError): b.validate_sources(s)

    def test_run_readback_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'result'
            r=b.run(out,Path(__file__).with_name('sources.json'))
            for name,record in r['outputs'].items():
                self.assertEqual(b.sha256((out/name).read_bytes()).hexdigest(),record['sha256'])
            with self.assertRaises(FileExistsError): b.run(out,Path(__file__).with_name('sources.json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
