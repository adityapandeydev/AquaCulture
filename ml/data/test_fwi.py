import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.fwi import assign_roles, block_of, build_windows, hourly, linked_ponds, partition_of, residual_sharing

POLICY = json.loads(Path('docs/data/fwi-policy.json').read_text(encoding='utf-8'))
POND = 'ara2_0f143c64'


def readings(start, count, step=15, offset=0):
    time = pd.date_range(start, periods=count, freq=f'{step}min') + pd.Timedelta(seconds=offset)
    return pd.DataFrame({'time': time, 'do': np.arange(count) % 7 + 3., 'ph': 8., 'temperature': 25.,
                         'flag_time': None, 'flag_do': None, 'flag_ph': None})


def hours(pond, start, count, session=0):
    return pd.DataFrame({'pond_id': pond, 'session': session, 'hour': pd.date_range(start, periods=count, freq='h'),
                         'do_mgL': np.arange(count) + 1., 'ph': 8., 'temperature_c': 25., 'eligible': True})


class HourlyTest(unittest.TestCase):
    def test_offset_timestamps_still_form_complete_hours(self):
        table = hourly(readings('2025-12-20', 8, offset=439), POND, POLICY)
        self.assertEqual(table.readings.tolist(), [4, 4])
        self.assertTrue(table.eligible.all())

    def test_missing_readings_make_an_hour_ineligible_without_filling(self):
        frame = readings('2025-12-20', 8)
        frame.loc[[0, 1], 'do'] = np.nan
        table = hourly(frame, POND, POLICY)
        self.assertEqual(table.eligible.tolist(), [False, True])
        self.assertTrue(np.isnan(table.do_mgL[0]))

    def test_conflicting_timestamps_exclude_only_their_hour(self):
        frame = pd.concat([readings('2025-12-20', 8), readings('2025-12-20 01:15', 1).assign(do=9.)])
        self.assertEqual(hourly(frame, POND, POLICY).eligible.tolist(), [True, False])

    def test_days_with_a_second_stream_are_excluded(self):
        frame = pd.concat([readings('2025-12-20', 96), readings('2025-12-20 12:00', 11)])
        self.assertFalse(hourly(frame, POND, POLICY).eligible.any())

    def test_event_days_are_excluded_and_split_sessions(self):
        table = hourly(readings('2026-01-07', 96 * 3), POND, POLICY)
        day = table.hour.dt.strftime('%m-%d')
        self.assertFalse(table[day.eq('01-08')].eligible.any())
        self.assertEqual(table[day.ne('01-08')].groupby(day).session.first().nunique(), 2)

    def test_declared_interval_is_excluded(self):
        table = hourly(readings('2025-12-05', 8), 'ara2_29660d32', POLICY)
        self.assertFalse(table.eligible.any())


class PartitionTest(unittest.TestCase):
    def test_linked_ponds_stay_in_development(self):
        ponds = sorted(POLICY['event_days'])
        table = pd.concat([hours(p, '2026-01-24', 24 * 7) for p in ponds])
        roles = assign_roles(table, POLICY)
        self.assertTrue(all(roles[p] == 'development' for p in linked_ponds(POLICY)))
        self.assertEqual(sum(r == 'test' for r in roles.values()), 4)
        self.assertEqual(sum(r == 'calibration' for r in roles.values()), 3)

    def test_test_ponds_never_reach_fitting_or_calibration(self):
        for block in ['fit', 'validation', 'calibration', 'test']:
            self.assertTrue(partition_of('test', block).startswith('test_unseen_pond'))
        self.assertIsNone(partition_of('development', 'calibration'))
        self.assertIsNone(partition_of('test', 'outside'))

    def test_block_edges(self):
        self.assertEqual(list(block_of(['2026-01-12 23:00', '2026-01-13', '2026-01-30 23:00', '2026-01-31'], POLICY)),
                         ['fit', 'validation', 'test', 'outside'])


class WindowTest(unittest.TestCase):
    def test_windows_stay_in_one_session_and_block(self):
        table = pd.concat([hours(POND, '2026-01-12 00:00', 30), hours(POND, '2026-01-13 06:00', 10, session=1)])
        windows = build_windows(table, {POND: 'development'}, POLICY)
        self.assertTrue(windows.session.eq(0).all())
        fit = windows[windows.partition.eq('fit')]
        self.assertTrue(fit.target_hour.lt('2026-01-13').all())

    def test_window_requires_recent_history_and_target_hour(self):
        table = hours(POND, '2025-12-20', 40)
        table.loc[30, 'eligible'] = False
        windows = build_windows(table, {POND: 'development'}, POLICY)
        missing = table.hour[30]
        self.assertFalse(windows.target_hour.eq(missing).any())
        recent = windows.issue_hour.sub(missing) / pd.Timedelta(hours=1)
        self.assertFalse(recent.between(0, 2).any())
        self.assertTrue(recent.eq(3).any())

    def test_remaining_shared_records_are_detected(self):
        left, right = hours('a', '2025-12-20', 3), hours('b', '2025-12-20', 3)
        self.assertEqual(residual_sharing(pd.concat([left, right])), 3)
        right['do_mgL'] += .5
        self.assertEqual(residual_sharing(pd.concat([left, right])), 0)


if __name__ == '__main__':
    unittest.main()
