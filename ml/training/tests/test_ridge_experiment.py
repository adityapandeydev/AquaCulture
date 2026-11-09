import unittest
import contextlib
import io
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.evaluation.criteria import validation_error_gates
from ml.training.ridge import choose_trial, run_ridge, validate_settings


class RidgeExperimentTests(unittest.TestCase):
    def test_selection_uses_complete_validation_mae_and_registered_tie_order(self):
        trials = [
            {'trial_index': 1, 'status': 'ok', 'validation': {'complete_predictions': True, 'mae_mgL': .3}},
            {'trial_index': 2, 'status': 'ok', 'validation': {'complete_predictions': False, 'mae_mgL': .01}},
            {'trial_index': 3, 'status': 'ok', 'validation': {'complete_predictions': True, 'mae_mgL': .3}}]
        self.assertEqual(choose_trial(trials[::-1])['trial_index'], 1)
        self.assertIsNone(choose_trial([trials[1]]))

    def test_ridge_grid_is_bounded_before_fitting(self):
        import json
        from pathlib import Path
        settings = json.loads(Path('ml/training/configs/ridge_settings.json').read_text())
        validate_settings(settings, 4)
        with self.assertRaises(ValueError):
            validate_settings({**settings, 'alphas': [.1, 1, 10, 100, 1000]}, 4)
        with self.assertRaises(ValueError):
            validate_settings({**settings, 'alphas': [0.]}, 4)

    def test_error_gates_do_not_imply_model_qualification(self):
        limits = {'maximum_mae_mgL': .5, 'maximum_rmse_mgL': .75, 'maximum_absolute_bias_mgL': .2}
        metrics = {'complete_predictions': True, 'mae_mgL': .2, 'rmse_mgL': .3,
                   'mean_signed_bias_mgL': -.05, 'mae_skill_vs_persistence': .2}
        result = validation_error_gates(metrics, {'rmse_mgL': .4}, limits, .05)
        self.assertTrue(result['passed'])
        self.assertFalse(result['model_qualified'])
        failed = validation_error_gates({**metrics, 'mae_skill_vs_persistence': None}, {'rmse_mgL': .4}, limits, .05)
        self.assertFalse(failed['passed'])

    def test_complete_runner_fits_only_synthetic_training_and_saves_loadable_artifacts(self):
        import json
        from pathlib import Path
        from ml.data.eligibility import digest
        from ml.data.evaluation_plan import build_plan
        from ml.data.windows import build_windows
        from ml.modeling.ridge import RidgeForecaster
        from ml.training.data import materialize_development
        observations = pd.DataFrame({'observation_id': [str(i) for i in range(110)], 'session_id': 'fixture',
                                     'partition': ['train'] * 100 + ['validation'] * 10,
                                     'available_at': pd.date_range('2026-01-01 01:00', periods=110, freq='h', tz='UTC'),
                                     'do_mgL': 7 + np.arange(110) * .01, 'do_mgL_eligible': True, 'preparation_imputed': False})
        contract = {'version': 'fixture', 'history_hours': 6, 'horizons_hours': [1],
                    'input_configurations': {'do_only': ['do_mgL']}, 'target': {'column': 'do_mgL'}}
        windows = build_windows(observations, contract)
        index = build_plan(observations, windows, contract, 24)
        criteria = json.loads(Path('docs/data/release-criteria.json').read_text())
        evaluation = json.loads(Path('docs/data/evaluation-policy.json').read_text())
        settings_bytes = Path('ml/training/configs/ridge_settings.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = root / 'docs/data/prepared-release.json'
            descriptor.parent.mkdir(parents=True)
            descriptor.write_text('{}')
            frozen = root / 'release'
            (frozen / 'policies').mkdir(parents=True)
            (frozen / 'release_manifest.json').write_text('{}')
            for name, record in [('release-criteria.json', criteria), ('evaluation-policy.json', evaluation)]:
                (frozen / 'policies' / name).write_text(json.dumps(record))
            config = {'version': 'do-experiment-foundation-v1', 'release_descriptor': 'docs/data/prepared-release.json',
                      'configuration': 'do_only', 'horizon_hours': 1, 'seed': 17, 'neural_device': 'cuda'}
            config_path, settings_path = root / 'config.json', root / 'settings.json'
            config_path.write_text(json.dumps(config))
            settings_path.write_bytes(settings_bytes)
            fake = SimpleNamespace(root=frozen, descriptor_path=descriptor, contract=contract,
                manifest_sha256=digest(frozen / 'release_manifest.json'),
                development=lambda p, c, h, dtype: materialize_development(observations, windows, contract, p, c, h, dtype),
                baseline_context=lambda p, c, h: (observations[observations.partition.eq(p)].copy(),
                                                 index[index.partition.eq(p)].reset_index(drop=True)),
                training_observations=lambda: observations[observations.partition.eq('train')].copy())
            with patch('ml.training.ridge.PreparedRelease', return_value=fake), patch(
                    'ml.training.ridge.capture_provenance', return_value={'synthetic_fixture': True}), contextlib.redirect_stdout(io.StringIO()):
                result = run_ridge(config_path, settings_path, root / 'run', repository=root)
            self.assertTrue(result['training_performed'])
            self.assertFalse(result['model_qualified'])
            case = result['cases'][0]
            self.assertEqual(len(case['trials']), 4)
            self.assertEqual(case['features'], ['do_mgL'])
            model_path = root / 'run/do_only/horizon_1/selected_model.json'
            model = RidgeForecaster.load(model_path)
            train = materialize_development(observations, windows, contract, 'train', 'do_only', 1, np.float64)
            np.testing.assert_array_equal(model.mean, train.x.reshape(len(train.x), -1).mean(axis=0))
            for name, expected in result['outputs_sha256'].items():
                self.assertEqual(digest(root / 'run' / name), expected)
            with self.assertRaises(FileExistsError):
                run_ridge(config_path, settings_path, root / 'run', repository=root)


if __name__ == '__main__':
    unittest.main()
