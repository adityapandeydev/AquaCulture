import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.eligibility import digest
from ml.evaluation.pilot_final import SEEDS, score_case, summarize_case, verify_lock
from ml.evaluation.reporting import prediction_frame


def synthetic_lock(root):
    (root / 'docs/data').mkdir(parents=True)
    for name in ['descriptor', 'run', 'code', 'docs/data/policy.json'] + [f'm{s}' for s in SEEDS]:
        (root / name).write_text(name)
    return {'release': {'descriptor': 'descriptor', 'descriptor_sha256': digest(root / 'descriptor')},
            'policy_sha256': {'policy.json': digest(root / 'docs/data/policy.json')},
            'development_evidence': {'gru': {'run': 'run', 'sha256': digest(root / 'run')}},
            'inference_and_scoring_source_sha256': {'code': digest(root / 'code')},
            'cases': [{'replicas': [{'seed': s, 'path': f'm{s}', 'sha256': digest(root / f'm{s}')} for s in SEEDS]}]}


class PilotFinalTest(unittest.TestCase):
    def test_lock_rejects_changed_or_missing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = synthetic_lock(root)
            self.assertEqual(verify_lock(lock, root), 7)
            (root / 'm29').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'm29'):
                verify_lock(lock, root)
            (root / 'm29').unlink()
            with self.assertRaisesRegex(ValueError, 'm29'):
                verify_lock(lock, root)

    def test_lock_requires_every_registered_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = synthetic_lock(root)
            lock['cases'][0]['replicas'].pop()
            with self.assertRaisesRegex(ValueError, 'registered seed'):
                verify_lock(lock, root)

    def test_scores_and_gates_use_matched_windows(self):
        index = pd.DataFrame({'window_id': list('abcd'), 'session_id': 's', 'partition': 'test',
                              'configuration': 'do_only', 'horizon_hours': 1, 'issue_time': range(4),
                              'target_observation_id': list('wxyz'), 'observed_do_mgL': [5., 6., 7., 8.],
                              'all_horizon_specific': True, 'common_horizons': [True, True, True, False]})
        truth = index.observed_do_mgL.to_numpy()
        forecasts = {'persistence': prediction_frame(index, truth + .4, 'persistence')}
        for seed in SEEDS:
            forecasts[f'gru_seed_{seed}'] = prediction_frame(index, truth + .1, f'gru_seed_{seed}')
        rows = score_case(index, forecasts, 5.)
        lower = [r for r in rows if r['subset'] == 'training_lower_decile' and r['model'] == 'persistence']
        self.assertEqual([r['expected_windows'] for r in lower], [1, 1])
        criteria = {'minimum_mae_skill_vs_persistence': .05, 'accuracy_limits_by_horizon_hours':
                    {'1': {'maximum_mae_mgL': .5, 'maximum_rmse_mgL': .75, 'maximum_absolute_bias_mgL': .2}}}
        case = summarize_case(rows, criteria, 1)
        self.assertTrue(np.isclose(case['gru_mean']['mae_skill_vs_persistence'], .75))
        self.assertTrue(case['gates']['primary_seed_17']['passed'])


if __name__ == '__main__':
    unittest.main()
