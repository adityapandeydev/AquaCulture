import unittest

import pandas as pd

from ml.data.evaluation_plan import build_plan
from ml.data.windows import build_windows


class EvaluationPlanTests(unittest.TestCase):
    def contract(self):
        return {'version': 'test-v1', 'history_hours': 6, 'horizons_hours': [1, 3],
                'input_configurations': {'do_only': ['do_mgL']}}

    def observations(self, n=32):
        return pd.DataFrame({'observation_id': [f'row-{i}' for i in range(n)],
                             'session_id': 'a', 'partition': 'train',
                             'available_at': pd.date_range('2026-01-01 01:00', periods=n, freq='h', tz='UTC'),
                             'do_mgL': 7., 'do_mgL_eligible': True})

    def test_persistence_uses_latest_input_and_all_windows_are_kept(self):
        obs = self.observations()
        windows = build_windows(obs, self.contract())
        plan = build_plan(obs, windows, self.contract(), 24)
        self.assertEqual(len(plan), len(windows))
        self.assertTrue(all(row.persistence_reference_id == window['input_observation_ids'][-1]
                            for row, window in zip(plan.itertuples(), windows)))

    def test_seasonal_phase_tracks_target_horizon_not_issue_minus_24(self):
        obs = self.observations()
        plan = build_plan(obs, build_windows(obs, self.contract()), self.contract(), 24)
        selected = plan[plan.issue_time.eq('2026-01-02T00:00:00+00:00')]
        self.assertEqual(selected.set_index('horizon_hours').seasonal_reference_id.to_dict(), {1: 'row-0', 3: 'row-2'})
        self.assertEqual(plan.groupby('horizon_hours').seasonal_matched.sum().to_dict(), {1: 8, 3: 8})

    def test_older_reference_cannot_cross_partition_boundary(self):
        obs = self.observations(64)
        obs.loc[32:, 'partition'] = 'test'
        plan = build_plan(obs, build_windows(obs, self.contract()), self.contract(), 24)
        self.assertEqual(plan.groupby(['partition', 'horizon_hours']).seasonal_matched.sum().tolist(), [8, 8, 8, 8])

    def test_unavailable_or_imputed_seasonal_reference_is_not_eligible(self):
        obs = self.observations()
        windows = build_windows(obs, self.contract())
        obs['preparation_imputed'] = False
        obs.loc[0, 'preparation_imputed'] = True
        # row 0 is outside the six-bin inputs of this later issue, but supplies its seasonal baseline.
        later = [w for w in windows if w['issue_time'] == '2026-01-02T00:00:00+00:00' and w['horizon_hours'] == 1]
        plan = build_plan(obs, later, self.contract(), 24)
        self.assertFalse(plan.iloc[0].seasonal_matched)

    def test_joint_seasonal_cohort_requires_both_horizons(self):
        obs = self.observations()
        plan = build_plan(obs, build_windows(obs, self.contract()), self.contract(), 24)
        self.assertEqual(plan.groupby('horizon_hours').common_horizons_seasonal_matched.sum().to_dict(), {1: 6, 3: 6})

    def test_baseline_must_not_access_a_future_seasonal_reference(self):
        obs = self.observations()
        with self.assertRaises(ValueError):
            build_plan(obs, build_windows(obs, self.contract()), self.contract(), 2)


if __name__ == '__main__':
    unittest.main()
