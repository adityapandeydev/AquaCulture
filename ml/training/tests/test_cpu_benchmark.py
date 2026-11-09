import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ml.evaluation.cpu_benchmark import assess_resources, verify_run
from ml.modeling.cpu import CPUForecast, assemble_history


class CPUBenchmarkTests(unittest.TestCase):
    def history(self):
        return [{'available_at': f'2026-01-01T{hour:02d}:00:00+00:00', 'do_mgL': 7 + hour / 10} for hour in range(1, 7)]

    def test_hourly_assembly_preserves_feature_order_and_rejects_gaps_or_bad_values(self):
        rows = self.history()
        actual = assemble_history(rows, ('do_mgL',))
        self.assertEqual(actual.shape, (1, 6, 1))
        self.assertAlmostEqual(CPUForecast('persistence', None, ['do_mgL']).from_history(rows)[0], 7.6)
        with self.assertRaises(ValueError):
            assemble_history(rows[::-1], ('do_mgL',))
        with self.assertRaises(ValueError):
            assemble_history(rows, ('ph', 'do_mgL'))
        with self.assertRaises(ValueError):
            assemble_history([{**r, 'do_mgL': float('nan')} for r in rows], ('do_mgL',))

    def test_resource_gate_checks_worst_cold_trial_peak_memory_and_never_qualifies_model(self):
        limits = json.loads(Path('docs/data/release-criteria.json').read_text())['cpu_resource_limits']
        warm = {'timings': {'model_only': {'p95_ms': 1}, 'hourly_history_preprocessing_plus_model': {'p95_ms': 2}},
                'memory': {'peak_rss_bytes': 100 * 1024**2}, 'parameter_count': 100, 'batch32_windows_per_second': 1000}
        cold = [{'process_start_to_exit_seconds': n, 'memory': {'peak_rss_bytes': 100 * 1024**2}} for n in [1, 2, 16]]
        result = assess_resources(warm, cold, 1024, limits)
        self.assertFalse(result['passed'])
        self.assertIn('cold_start', result['failed_checks'])
        self.assertFalse(result['model_qualified'])
        self.assertTrue(assess_resources(warm, cold[:2], 1024, limits)['passed'])
        cold[0]['memory']['peak_rss_bytes'] = 2 * 1024**3
        self.assertIn('peak_rss_mib', assess_resources(warm, cold[:2], 1024, limits)['failed_checks'])

    def test_run_integrity_and_no_partition_or_path_escape(self):
        from ml.data.eligibility import digest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'model.json').write_text('{}')
            record = {'status': 'development_ridge_completed', 'outputs_sha256': {'model.json': digest(root / 'model.json')},
                      'source_sha256': {}, 'descriptor_sha256': 'descriptor', 'release_manifest_sha256': 'manifest',
                      'locked_partitions': ['calibration', 'test']}
            (root / 'run.json').write_text(json.dumps(record))
            verify_run(root, 'development_ridge_completed', root, 'descriptor', 'manifest')
            (root / 'model.json').write_text('changed')
            with self.assertRaises(ValueError):
                verify_run(root, 'development_ridge_completed', root, 'descriptor', 'manifest')
            record['outputs_sha256'] = {'../escape': 'bad'}
            (root / 'run.json').write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                verify_run(root, 'development_ridge_completed', root, 'descriptor', 'manifest')

    def test_real_fresh_worker_measures_cpu_persistence_and_checks_prediction_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'payload.json'
            path.write_text(json.dumps({'family': 'persistence', 'artifact': None, 'features': ['do_mgL'],
                                        'histories': [self.history()], 'expected_predictions': [7.6]}))
            import os
            env = {**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'CUDA_VISIBLE_DEVICES': ''}
            process = subprocess.run([sys.executable, '-B', '-m', 'ml.evaluation.cpu_worker', '--payload', str(path), '--phase', 'warm'],
                                     capture_output=True, text=True, check=True, env=env)
            result = json.loads(process.stdout)
            self.assertEqual(result['prediction_parity'], 'passed')
            self.assertEqual(len(result['timings']['model_only']['samples_ms']), 100)
            self.assertGreater(result['memory']['peak_rss_bytes'], 0)
            self.assertGreater(result['batch32_windows_per_second'], 0)
            self.assertTrue(result['cpu_name'])

    def test_cpu_ridge_adapter_matches_bound_predictions_and_rejects_feature_mismatch(self):
        from ml.modeling.ridge import fit_ridge
        histories = np.stack([assemble_history([{**r, 'do_mgL': r['do_mgL'] + offset} for r in self.history()], ('do_mgL',))[0]
                              for offset in [0, 1, 2]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ridge.json'
            model = fit_ridge(histories, np.array([8., 9., 10.]), 1.)
            model.save(path)
            adapter = CPUForecast('ridge', path, ['do_mgL'])
            np.testing.assert_array_equal(adapter.predict(adapter.prepare(histories)), model.predict(histories))
            with self.assertRaises(ValueError):
                CPUForecast('ridge', path, ['do_mgL', 'temperature_c', 'ph'])


if __name__ == '__main__':
    unittest.main()
