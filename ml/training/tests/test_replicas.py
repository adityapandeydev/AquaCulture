import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ml.evaluation.replicas import choose_setting, summarize_replicas
from ml.training.gru import validate_settings
from ml.training.gru_fit import prepare_randomness


class ReplicaTests(unittest.TestCase):
    def test_missing_neural_runtime_has_actionable_error(self):
        with patch('ml.training.gru_fit.importlib.import_module', side_effect=ImportError('absent')):
            with self.assertRaisesRegex(RuntimeError, 'separate model environment'):
                prepare_randomness(17, 'cuda:0')

    def replicas(self, errors=(.2, .4, .6)):
        return [{'seed': seed, 'status': 'ok', 'validation': {'complete_predictions': True, 'mae_mgL': error,
                 'rmse_mgL': error, 'mean_signed_bias_mgL': bias, 'mae_skill_vs_persistence': .1}}
                for seed, error, bias in zip([17, 29, 43], errors, [-.2, .2, -.2])]

    def test_mean_seed_selection_does_not_choose_lucky_seed_and_bias_cannot_cancel(self):
        a, b = summarize_replicas(self.replicas()), summarize_replicas(self.replicas((.01, .9, .9)))
        self.assertAlmostEqual(a['mean']['mean_signed_bias_mgL'], .2)
        trials = [{'trial_index': n, 'parameter_count': 100, 'summary': s} for n, s in enumerate([a, b], 1)]
        self.assertEqual(choose_setting(trials)['trial_index'], 1)
        trials[0]['summary']['complete'] = False
        self.assertEqual(choose_setting(trials)['trial_index'], 2)
        trials[1]['summary']['complete'] = False
        self.assertIsNone(choose_setting(trials))

    def test_all_seeds_required_and_failure_is_ineligible(self):
        rows = self.replicas()
        with self.assertRaises(ValueError):
            summarize_replicas(rows[:2])
        rows[1] = {'seed': 29, 'status': 'failed', 'error': 'timeout'}
        result = summarize_replicas(rows)
        self.assertFalse(result['complete'])
        self.assertIsNone(result['mean']['mae_mgL'])

    def test_setting_and_epoch_budget_are_fixed(self):
        settings = json.loads(Path('ml/training/configs/gru_settings.json').read_text())
        criteria = json.loads(Path('docs/data/release-criteria.json').read_text())
        policy = json.loads(Path('docs/data/evaluation-policy.json').read_text())
        validate_settings(settings, criteria, policy)
        altered = copy.deepcopy(settings)
        altered['settings'][0]['hidden_size'] = 32
        with self.assertRaises(ValueError):
            validate_settings(altered, criteria, policy)
        with self.assertRaises(ValueError):
            validate_settings({**settings, 'maximum_epochs': 101}, criteria, policy)


if __name__ == '__main__':
    unittest.main()
