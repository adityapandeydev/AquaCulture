import unittest

import pandas as pd

from ml.data.release_readiness import check_history


class ReleaseReadinessTests(unittest.TestCase):
    def policy(self):
        return {'supported_context': {'session_id': 'a', 'source_sha256': 'source', 'lineage_group_id': 'study'},
                'inputs': {'do_only': ['do_mgL'], 'do_temperature_ph': ['do_mgL', 'temperature_c', 'ph']},
                'history_requirements': {'hours': 6, 'minimum_readings_per_minute': 3, 'minimum_covered_minutes': 54,
                                         'maximum_gap_seconds': 180, 'maximum_end_age_seconds': 60},
                'maximum_new_issue_delay_seconds': 60, 'maximum_latest_raw_age_at_request_seconds': 120}

    def history(self):
        frame = pd.DataFrame({'observation_id': [str(i) for i in range(6)], 'session_id': 'a',
                              'source_sha256': 'source', 'lineage_group_id': 'study', 'partition': 'test',
                              'available_at': pd.date_range('2026-01-01 01:00', periods=6, freq='h', tz='UTC'),
                              'preparation_imputed': False})
        for column, value in [('do_mgL', 7.), ('temperature_c', 28.), ('ph', 7.5)]:
            frame[column] = value
            frame[column + '_eligible'] = True
            for suffix, number in [('covered_minutes', 60), ('valid_rows', 360), ('invalid_rows', 0),
                                   ('maximum_gap_seconds', 10), ('end_age_seconds', 10)]:
                frame[column + '_' + suffix] = number
        return frame

    def check(self, frame, request='2026-01-01 06:00Z', configuration='do_only'):
        return check_history(frame, configuration, '2026-01-01 06:00Z', request, self.policy())

    def test_complete_history_is_ready_without_any_future_targets(self):
        self.assertTrue(self.check(self.history())['inputs_ready'])

    def test_delay_and_raw_freshness_limits_are_inclusive(self):
        frame = self.history()
        frame.loc[5, 'do_mgL_end_age_seconds'] = 60
        self.assertTrue(self.check(frame, '2026-01-01 06:01Z')['inputs_ready'])
        self.assertFalse(self.check(frame, '2026-01-01 06:01:01Z')['inputs_ready'])
        frame.loc[5, 'do_mgL_end_age_seconds'] = 61
        self.assertIn('sensor_stale', self.check(frame)['reasons'])

    def test_future_issue_and_incomplete_history_are_unavailable(self):
        self.assertIn('issue_not_available', self.check(self.history(), '2026-01-01 05:59Z')['reasons'])
        self.assertIn('insufficient_history', self.check(self.history().iloc[:5])['reasons'])

    def test_missing_optional_sensor_does_not_block_do_only(self):
        frame = self.history()
        frame.loc[0, 'ph'] = float('nan')
        self.assertTrue(self.check(frame)['inputs_ready'])
        self.assertFalse(self.check(frame, configuration='do_temperature_ph')['inputs_ready'])

    def test_coverage_gap_and_missing_metadata_fail_closed(self):
        frame = self.history()
        frame.loc[1, 'do_mgL_covered_minutes'] = 53
        frame.loc[2, 'do_mgL_maximum_gap_seconds'] = 181
        result = self.check(frame)
        self.assertIn('insufficient_coverage', result['reasons'])
        self.assertIn('gap_exceeded', result['reasons'])
        self.assertIn('missing_metadata', self.check(frame.drop(columns=['do_mgL_end_age_seconds']))['reasons'])

    def test_cross_partition_unknown_context_and_imputation_are_rejected(self):
        for column, value in [('partition', 'validation'), ('session_id', 'other'),
                              ('source_sha256', 'different'), ('preparation_imputed', True)]:
            frame = self.history()
            frame.loc[0, column] = value
            self.assertFalse(self.check(frame)['inputs_ready'], column)

    def test_reversed_or_duplicated_histories_are_rejected(self):
        self.assertIn('history_time_mismatch', self.check(self.history().iloc[::-1])['reasons'])
        frame = self.history()
        frame.loc[5, 'observation_id'] = frame.loc[4, 'observation_id']
        self.assertIn('duplicate_observation', self.check(frame)['reasons'])

    def test_valid_zero_is_not_treated_as_missing_or_repaired(self):
        frame = self.history()
        frame['do_mgL'] = 0.
        self.assertTrue(self.check(frame)['inputs_ready'])
        self.assertTrue(frame.do_mgL.eq(0).all())

    def test_nullable_missing_measurement_or_eligibility_fails_closed(self):
        frame = self.history()
        frame['do_mgL'] = frame.do_mgL.astype('Float64')
        frame.loc[0, 'do_mgL'] = pd.NA
        self.assertFalse(self.check(frame)['inputs_ready'])
        frame = self.history()
        frame['do_mgL_eligible'] = frame.do_mgL_eligible.astype('boolean')
        frame.loc[0, 'do_mgL_eligible'] = pd.NA
        self.assertFalse(self.check(frame)['inputs_ready'])

    def test_nullable_missing_quality_metadata_returns_unavailable(self):
        frame = self.history()
        frame['do_mgL_valid_rows'] = frame.do_mgL_valid_rows.astype('Float64')
        frame.loc[0, 'do_mgL_valid_rows'] = pd.NA
        self.assertIn('invalid_quality_metadata', self.check(frame)['reasons'])


if __name__ == '__main__':
    unittest.main()
