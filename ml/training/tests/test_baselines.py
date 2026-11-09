import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.evaluation.metrics import lower_do_threshold, score_predictions
from ml.modeling.baselines import predict_references
from ml.training.baselines import evaluate_case, run_baselines


class BaselineTests(unittest.TestCase):
    def observations(self):
        return pd.DataFrame({'observation_id': ['old', 'latest', 'target'], 'session_id': 'a', 'partition': 'train',
                             'available_at': pd.to_datetime(['2026-01-01 03:00Z', '2026-01-02 00:00Z', '2026-01-02 03:00Z']),
                             'do_mgL': [2., 6., 9.], 'do_mgL_eligible': True, 'preparation_imputed': False})

    def index(self):
        return pd.DataFrame({'window_id': ['w'], 'session_id': 'a', 'partition': 'train', 'horizon_hours': [3],
                             'issue_time': ['2026-01-02T00:00:00+00:00'], 'target_observation_id': ['target'],
                             'persistence_reference_id': ['latest'], 'seasonal_reference_id': ['old'],
                             'seasonal_matched': True})

    def test_persistence_and_target_aligned_seasonal_predictions(self):
        obs, index = self.observations(), self.index()
        self.assertEqual(predict_references(obs, index, 'persistence').iloc[0].point_mgL, 6.)
        self.assertEqual(predict_references(obs, index, 'daily_seasonal_persistence').iloc[0].point_mgL, 2.)
        obs.loc[2, 'do_mgL'] = 999.
        self.assertEqual(predict_references(obs, index, 'persistence').iloc[0].point_mgL, 6.)

    def test_future_or_other_partition_reference_is_rejected(self):
        obs, index = self.observations(), self.index()
        index['persistence_reference_id'] = 'target'
        with self.assertRaises(ValueError):
            predict_references(obs, index, 'persistence')
        index = self.index()
        obs.loc[0, 'partition'] = 'test'
        with self.assertRaises(ValueError):
            predict_references(obs, index, 'daily_seasonal_persistence')

    def test_unavailable_seasonal_reference_is_explicit_not_filled(self):
        index = self.index()
        index['seasonal_matched'] = False
        index['seasonal_reference_id'] = None
        result = predict_references(self.observations(), index, 'daily_seasonal_persistence')
        self.assertEqual(result.iloc[0].status, 'unavailable')
        self.assertTrue(pd.isna(result.iloc[0].point_mgL))

    def test_metrics_join_by_window_id_and_preserve_bias_sign(self):
        expected = pd.DataFrame({'window_id': ['a', 'b'], 'observed_do_mgL': [2., 4.]})
        predictions = pd.DataFrame({'window_id': ['b', 'a'], 'point_mgL': [6., 1.], 'status': 'ok'})
        result = score_predictions(expected, predictions)
        self.assertEqual(result['mae_mgL'], 1.5)
        self.assertAlmostEqual(result['rmse_mgL'], np.sqrt(2.5))
        self.assertEqual(result['mean_signed_bias_mgL'], .5)
        self.assertEqual(result['prediction_coverage'], 1.)

    def test_partial_predictions_never_rank_and_skill_is_not_fabricated(self):
        expected = pd.DataFrame({'window_id': ['a', 'b'], 'observed_do_mgL': [2., 4.]})
        predictions = pd.DataFrame({'window_id': ['a'], 'point_mgL': [2.], 'status': 'ok'})
        result = score_predictions(expected, predictions, predictions)
        self.assertEqual(result['missing_predictions'], 1)
        self.assertEqual(result['prediction_coverage'], .5)
        self.assertFalse(result['complete_predictions'])
        self.assertIsNone(result['mae_skill_vs_persistence'])

    def test_zero_reference_error_empty_cohorts_and_invalid_predictions(self):
        expected = pd.DataFrame({'window_id': ['a'], 'observed_do_mgL': [0.]})
        exact = pd.DataFrame({'window_id': ['a'], 'point_mgL': [0.], 'status': 'ok'})
        result = score_predictions(expected, exact, exact)
        self.assertEqual(result['mae_mgL'], 0.)
        self.assertIsNone(result['mae_skill_vs_persistence'])
        self.assertEqual(result['skill_status'], 'baseline_zero_error')
        for value in [np.nan, np.inf, -1.]:
            invalid = exact.assign(point_mgL=value)
            self.assertEqual(score_predictions(expected, invalid)['invalid_predictions'], 1)
        empty = score_predictions(expected.iloc[:0], exact.iloc[:0])
        self.assertIsNone(empty['mae_mgL'])
        self.assertFalse(empty['complete_predictions'])

    def test_duplicate_or_unexpected_prediction_ids_are_rejected(self):
        expected = pd.DataFrame({'window_id': ['a'], 'observed_do_mgL': [2.]})
        predictions = pd.DataFrame({'window_id': ['a'], 'point_mgL': [2.], 'status': 'ok'})
        for bad in [pd.concat([predictions, predictions]), predictions.assign(window_id='other')]:
            with self.assertRaises(ValueError):
                score_predictions(expected, bad)

    def test_lower_tail_threshold_uses_unique_training_observations_only(self):
        rows = pd.DataFrame({'observation_id': ['a', 'b', 'c', 'd'], 'partition': 'train', 'do_mgL': [0., 10., 20., 30.]})
        self.assertAlmostEqual(lower_do_threshold(rows), 3.)
        with self.assertRaises(ValueError):
            lower_do_threshold(rows.assign(partition='validation'))
        with self.assertRaises(ValueError):
            lower_do_threshold(pd.concat([rows, rows.iloc[:1]]))

    def test_nullable_status_missing_prediction_remains_a_failure_of_coverage(self):
        expected = pd.DataFrame({'window_id': ['a', 'b'], 'observed_do_mgL': [2., 4.]})
        prediction = pd.DataFrame({'window_id': ['a'], 'point_mgL': [2.], 'status': pd.Series(['ok'], dtype='string')})
        result = score_predictions(expected, prediction)
        self.assertEqual(result['prediction_coverage'], .5)
        self.assertEqual(result['missing_predictions'], 1)

    def test_case_report_pairs_cohorts_and_handles_empty_lower_tail(self):
        index = self.index().assign(configuration='do_only')
        cohorts = ['all_horizon_specific', 'common_horizons', 'seasonal_matched', 'common_horizons_seasonal_matched']
        for cohort in cohorts:
            index[cohort] = True
        policy = {'comparison_cohorts': cohorts, 'baseline_candidates': ['persistence', 'daily_seasonal_persistence']}
        predictions, metrics = evaluate_case(self.observations(), index, 2.5, policy)
        self.assertEqual(len(predictions), 2)
        self.assertEqual(len(metrics), 16)
        self.assertTrue(all(row['mae_mgL'] is None for row in metrics if row['subset'] == 'training_lower_decile'))
        seasonal = next(row for row in metrics if row['cohort'] == 'seasonal_matched'
                        and row['subset'] == 'all_targets' and row['model'] == 'daily_seasonal_persistence')
        self.assertEqual(seasonal['mae_mgL'], 7.)
        self.assertAlmostEqual(seasonal['mae_skill_vs_persistence'], 1 - 7 / 3)
        with self.assertRaises(ValueError):
            evaluate_case(self.observations(), index.assign(partition='test'), 2.5, policy)

    def test_full_runner_writes_checked_synthetic_artifacts_without_training(self):
        from ml.data.eligibility import digest
        cohorts = ['all_horizon_specific', 'common_horizons', 'seasonal_matched', 'common_horizons_seasonal_matched']
        policy = {'comparison_cohorts': cohorts, 'baseline_candidates': ['persistence', 'daily_seasonal_persistence']}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = root / 'docs/data/prepared-release.json'
            descriptor.parent.mkdir(parents=True)
            descriptor.write_text('{}', encoding='utf-8')
            release_root = root / 'release'
            (release_root / 'policies').mkdir(parents=True)
            (release_root / 'policies/evaluation-policy.json').write_text(json.dumps(policy), encoding='utf-8')
            (release_root / 'release_manifest.json').write_text('{}', encoding='utf-8')
            config = {'version': 'do-experiment-foundation-v1', 'release_descriptor': 'docs/data/prepared-release.json',
                      'configuration': 'do_only', 'horizon_hours': 3, 'seed': 17, 'neural_device': 'cuda'}
            config_path = root / 'config.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')

            def context(partition, configuration, horizon):
                obs, index = self.observations(), self.index().assign(partition=partition, configuration=configuration)
                obs['partition'] = partition
                obs['observation_id'] = partition + '-' + obs.observation_id
                for column in ['target_observation_id', 'persistence_reference_id', 'seasonal_reference_id', 'window_id']:
                    index[column] = partition + '-' + index[column]
                for cohort in cohorts:
                    index[cohort] = True
                return obs, index

            training = pd.DataFrame({'observation_id': [str(i) for i in range(100)], 'partition': 'train',
                                     'do_mgL': np.linspace(5., 10., 100)})
            fake = SimpleNamespace(root=release_root, descriptor_path=descriptor,
                                   manifest_sha256=digest(release_root / 'release_manifest.json'),
                                   baseline_context=context, training_observations=lambda: training)
            with patch('ml.training.baselines.PreparedRelease', return_value=fake), patch(
                    'ml.training.baselines.capture_provenance', return_value={'synthetic_fixture': True}), contextlib.redirect_stdout(io.StringIO()):
                report = run_baselines(config_path, root / 'run', repository=root)
            self.assertFalse(report['training_performed'])
            self.assertEqual(report['locked_partitions'], ['calibration', 'test'])
            self.assertEqual(len(pd.read_csv(root / 'run/predictions.csv')), 4)
            self.assertEqual(len(json.loads((root / 'run/metrics.json').read_text())), 32)
            for name, expected in report['outputs_sha256'].items():
                self.assertEqual(digest(root / 'run' / name), expected)
            with self.assertRaises(FileExistsError):
                run_baselines(config_path, root / 'run', repository=root)


if __name__ == '__main__':
    unittest.main()
