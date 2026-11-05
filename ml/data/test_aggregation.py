import unittest

import numpy as np
import pandas as pd

from ml.data.aggregation import aggregate_channel


class AggregationTests(unittest.TestCase):
    def frame(self, minutes=60):
        times = pd.date_range('2026-01-01', periods=minutes * 6, freq='10s', tz='UTC')
        return pd.DataFrame({'timestamp_utc': times, 'value': 6., 'invalid': False,
                             'zero_review': False, 'rapid_change_review': False,
                             'exact_plateau_review': False})

    def test_half_open_bins_and_availability(self):
        frame = self.frame(61)
        frame.loc[360:, 'value'] = 9.
        bins = aggregate_channel(frame)
        self.assertEqual(bins.iloc[0].measured_mean, 6.)
        self.assertEqual(bins.iloc[0].available_at, pd.Timestamp('2026-01-01 01:00Z'))
        self.assertTrue(bins.iloc[0].eligible)
        self.assertFalse(bins.iloc[1].eligible)

    def test_missing_target_stays_missing_and_empty_hours_remain(self):
        frame = self.frame(180)
        frame = frame[~frame.timestamp_utc.dt.hour.eq(1)].copy()
        bins = aggregate_channel(frame)
        self.assertEqual(len(bins), 3)
        self.assertFalse(bins.iloc[1].eligible)
        self.assertTrue(np.isnan(bins.iloc[1].value))

    def test_dense_burst_cannot_replace_time_coverage(self):
        frame = self.frame(10)
        row = aggregate_channel(frame).iloc[0]
        self.assertFalse(row.eligible)
        self.assertEqual(row.covered_minutes, 10)

    def test_long_gap_and_stale_end_reject_despite_coverage(self):
        frame = self.frame()
        gap = frame[~frame.timestamp_utc.dt.minute.between(20, 23)]
        self.assertFalse(aggregate_channel(gap).iloc[0].eligible)
        stale = frame[frame.timestamp_utc.dt.minute.lt(58)]
        self.assertFalse(aggregate_channel(stale).iloc[0].eligible)

    def test_invalid_values_never_become_targets_and_zero_is_preserved(self):
        frame = self.frame()
        frame['invalid'] = True
        self.assertTrue(np.isnan(aggregate_channel(frame).iloc[0].value))
        frame['invalid'] = False
        frame['value'] = 0.
        frame['zero_review'] = True
        row = aggregate_channel(frame).iloc[0]
        self.assertTrue(row.eligible)
        self.assertEqual(row.value, 0.)
        self.assertEqual(row.zero_review_rows, 360)

    def test_equal_minute_weighting_and_review_flags(self):
        frame = self.frame()
        frame.loc[frame.timestamp_utc.dt.minute.eq(0), 'value'] = 12.
        frame.loc[0, 'rapid_change_review'] = True
        extra = frame[frame.timestamp_utc.dt.minute.eq(0)].copy()
        extra['timestamp_utc'] += pd.Timedelta(seconds=1)
        row = aggregate_channel(pd.concat([frame, extra])).iloc[0]
        self.assertAlmostEqual(row.value, 6.1)
        self.assertTrue(row.eligible)
        self.assertFalse(row.review_free_eligible)

    def test_multiple_sessions_are_rejected_at_function_boundary(self):
        frame = self.frame()
        frame['session_id'] = ['a'] * 180 + ['b'] * 180
        with self.assertRaises(ValueError):
            aggregate_channel(frame)

    def test_minute_support_and_exact_staleness_boundary(self):
        frame = self.frame()
        # Two readings per minute do not qualify as supported minutes.
        sparse = frame[frame.timestamp_utc.dt.second.lt(20)]
        self.assertEqual(aggregate_channel(sparse).iloc[0].covered_minutes, 0)
        at_limit = frame[frame.timestamp_utc.le(pd.Timestamp('2026-01-01 00:59Z'))]
        self.assertTrue(aggregate_channel(at_limit).iloc[0].eligible)
        too_old = frame[frame.timestamp_utc.lt(pd.Timestamp('2026-01-01 00:59Z'))]
        self.assertFalse(aggregate_channel(too_old).iloc[0].eligible)

    def test_future_readings_cannot_change_completed_bin(self):
        frame = self.frame(120)
        before = aggregate_channel(frame).iloc[0]
        frame.loc[frame.timestamp_utc.dt.hour.eq(1), 'value'] = 100.
        after = aggregate_channel(frame).iloc[0]
        self.assertEqual(before.value, after.value)


if __name__ == '__main__':
    unittest.main()
