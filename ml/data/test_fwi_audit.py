import unittest

import pandas as pd

from ml.data.audit_fwi import inspect_pond


class FWIAuditTests(unittest.TestCase):
    def frame(self):
        timestamps = pd.date_range('2026-01-01', periods=36, freq='15min')
        return pd.DataFrame({'Date/Time (IST)': timestamps.strftime('%Y-%m-%d %H:%M:%S'),
            'DO (mg/L)': 7., 'pH': 8., 'Temperature (\u00b0C)': 27.,
            'QC_Flag_DateTime': None, 'QC_Flag_DO': None, 'QC_Flag_pH': None})

    def test_complete_hours_require_history_and_full_future_path_with_explicit_ist(self):
        summary, _, _ = inspect_pond(self.frame())
        self.assertEqual(summary['structural_complete_hour_count'], 9)
        self.assertEqual(summary['structural_six_hour_windows_by_horizon'], {'1': 3, '3': 1})
        self.assertEqual(summary['first_utc'], '2025-12-31 18:30:00+00:00')

    def test_publisher_zero_artifact_and_channel_specific_flags_break_only_do_support(self):
        frame = self.frame()
        frame.loc[16, 'DO (mg/L)'] = 0
        frame.loc[3, 'QC_Flag_pH'] = 'pH_jump_>1'
        summary, _, _ = inspect_pond(frame)
        self.assertEqual(summary['zero_counts']['DO (mg/L)'], 1)
        self.assertEqual(summary['structural_complete_hour_count'], 8)
        self.assertEqual(summary['structural_six_hour_windows_by_horizon'], {'1': 0, '3': 0})
        frame.loc[16, 'DO (mg/L)'] = 7
        frame.loc[16, 'QC_Flag_DO'] = 'DO_jump_>2'
        summary, _, _ = inspect_pond(frame)
        self.assertEqual(summary['structural_six_hour_windows_by_horizon']['1'], 0)

    def test_duplicates_and_off_grid_seconds_are_not_silently_rounded_or_deduplicated(self):
        frame = self.frame()
        frame.loc[17, 'Date/Time (IST)'] = frame.loc[16, 'Date/Time (IST)']
        summary, _, _ = inspect_pond(frame)
        self.assertEqual(summary['duplicate_timestamps'], 2)
        self.assertEqual(summary['structural_complete_hour_count'], 8)
        frame = self.frame()
        frame['Date/Time (IST)'] = (pd.to_datetime(frame['Date/Time (IST)']) + pd.Timedelta(seconds=39)).dt.strftime('%Y-%m-%d %H:%M:%S')
        summary, _, _ = inspect_pond(frame)
        self.assertEqual(summary['structural_complete_hour_count'], 0)


if __name__ == '__main__':
    unittest.main()
