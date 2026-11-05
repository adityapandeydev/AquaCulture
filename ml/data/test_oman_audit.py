import unittest

import pandas as pd

from ml.data.audit_oman import complete_windows, covered_bins


class OmanAuditTests(unittest.TestCase):
    def test_dense_burst_does_not_count_as_full_hour_coverage(self):
        frame = pd.DataFrame({"timestamp_local": pd.date_range("2026-01-01", periods=100, freq="s"),
                              "source_row": range(100)})
        bins = covered_bins(frame)
        self.assertEqual(bins.iloc[0].readings, 100)
        self.assertEqual(bins.iloc[0].occupied_five_minute_slots, 1)
        self.assertEqual(bins.index[0], pd.Timestamp("2026-01-01 01:00"))

    def test_window_count_does_not_cross_gap(self):
        self.assertEqual(complete_windows(pd.Series([True] * 10), 6, 1), 4)
        self.assertEqual(complete_windows(pd.Series([True] * 5 + [False] + [True] * 5), 6, 1), 0)


if __name__ == "__main__":
    unittest.main()
