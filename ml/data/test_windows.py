import copy
import unittest

import numpy as np
import pandas as pd

from ml.data.windows import build_windows, input_matrix, paired_issues, validate_window


class WindowTests(unittest.TestCase):
    def contract(self):
        return {'version': 'test-v1', 'history_hours': 6, 'horizons_hours': [1, 3],
                'input_configurations': {'do_only': ['do_mgL'], 'do_temperature_ph': ['do_mgL', 'temperature_c', 'ph']}}

    def observations(self, n=10):
        return pd.DataFrame({'observation_id': [f'row-{i}' for i in range(n)], 'session_id': 'a', 'partition': 'train',
                             'available_at': pd.date_range('2026-01-01 01:00', periods=n, freq='h', tz='UTC'),
                             'do_mgL': np.arange(n, dtype=float), 'temperature_c': 28., 'ph': 7.,
                             'do_mgL_eligible': True, 'temperature_c_eligible': True, 'ph_eligible': True})

    def test_counts_alignment_shapes_and_feature_order(self):
        obs = self.observations()
        windows = build_windows(obs, self.contract())
        self.assertEqual(len(windows), 12)  # (4 one-hour + 2 three-hour) x 2 configs
        single = next(w for w in windows if w['configuration'] == 'do_only' and w['horizon_hours'] == 1)
        self.assertEqual(single['input_observation_ids'], [f'row-{i}' for i in range(6)])
        self.assertEqual(single['target_observation_id'], 'row-6')
        matrix = input_matrix(obs, single, self.contract())
        self.assertEqual(matrix.shape, (6, 1))
        np.testing.assert_array_equal(matrix[:, 0], np.arange(6))
        multi = next(w for w in windows if w['configuration'] == 'do_temperature_ph')
        np.testing.assert_array_equal(input_matrix(obs, multi, self.contract())[0], [0., 28., 7.])

    def test_partition_and_session_boundaries_are_not_bridged(self):
        obs = self.observations(12)
        obs.loc[6:, 'partition'] = 'test'
        self.assertEqual(build_windows(obs, self.contract()), [])
        obs['partition'] = 'train'
        obs.loc[6:, 'session_id'] = 'b'
        self.assertEqual(build_windows(obs, self.contract()), [])

    def test_missing_optional_input_does_not_remove_do_only_window(self):
        obs = self.observations()
        obs.loc[0, 'ph_eligible'] = False
        windows = build_windows(obs, self.contract())
        counts = {name: sum(w['configuration'] == name for w in windows) for name in self.contract()['input_configurations']}
        self.assertEqual(counts, {'do_only': 6, 'do_temperature_ph': 4})

    def test_future_optional_sensors_do_not_gate_labels(self):
        obs = self.observations()
        obs.loc[6:, 'ph_eligible'] = False
        windows = build_windows(obs, self.contract())
        self.assertTrue(any(w['configuration'] == 'do_temperature_ph' and w['horizon_hours'] == 3 for w in windows))

    def test_missing_intermediate_future_do_rejects_long_horizon(self):
        obs = self.observations()
        obs.loc[7, 'do_mgL_eligible'] = False
        windows = build_windows(obs, self.contract())
        self.assertFalse(any(w['horizon_hours'] == 3 for w in windows))

    def test_future_values_and_diagnostic_columns_cannot_enter_input_matrix(self):
        obs = self.observations()
        window = build_windows(obs, self.contract())[0]
        before = input_matrix(obs, window, self.contract())
        obs.loc[6:, ['do_mgL', 'temperature_c', 'ph']] = 999.
        obs['exact_plateau_review_rows'] = 999
        obs['disease_risk'] = 999
        np.testing.assert_array_equal(input_matrix(obs, window, self.contract()), before)

    def test_forged_future_input_or_cross_partition_label_is_rejected(self):
        obs = self.observations()
        window = build_windows(obs, self.contract())[0]
        forged = copy.deepcopy(window)
        forged['input_observation_ids'][-1] = forged['target_observation_id']
        with self.assertRaises(ValueError):
            validate_window(obs, forged, self.contract())
        obs.loc[6, 'partition'] = 'test'
        with self.assertRaises(ValueError):
            validate_window(obs, window, self.contract())

    def test_pairing_keeps_only_common_issues_and_ids_are_stable(self):
        obs = self.observations()
        first = build_windows(obs, self.contract())
        second = build_windows(obs.iloc[::-1], self.contract())
        self.assertEqual(first, second)
        pairs = paired_issues(first, self.contract())
        self.assertEqual(len(pairs), 4)  # 2 common issues for each configuration
        self.assertTrue(all(set(pair['window_ids_by_horizon']) == {'1', '3'} for pair in pairs))

    def test_duplicate_observations_and_time_gaps_fail_or_remove_windows(self):
        obs = self.observations()
        with self.assertRaises(ValueError):
            build_windows(pd.concat([obs, obs.iloc[:1]]), self.contract())
        self.assertEqual(build_windows(obs.drop(index=5), self.contract()), [])

    def test_imputed_targets_and_unapproved_covariates_are_rejected(self):
        obs = self.observations()
        obs['preparation_imputed'] = False
        obs.loc[6, 'preparation_imputed'] = True
        self.assertEqual(build_windows(obs, self.contract()), [])
        contract = self.contract()
        contract['input_configurations']['do_only'].append('disease_risk')
        with self.assertRaises(ValueError):
            build_windows(self.observations(), contract)

    def test_forged_target_interval_or_reordered_history_is_rejected(self):
        obs = self.observations()
        window = build_windows(obs, self.contract())[0]
        window['target_interval_start'] = window['target_interval_end']
        with self.assertRaises(ValueError):
            validate_window(obs, window, self.contract())
        window = build_windows(obs, self.contract())[0]
        window['input_observation_ids'].reverse()
        with self.assertRaises(ValueError):
            validate_window(obs, window, self.contract())


if __name__ == '__main__':
    unittest.main()
