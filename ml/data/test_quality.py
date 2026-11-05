import unittest

import pandas as pd

from ml.data.quality import inspect_channel, valid_spans


class QualityTests(unittest.TestCase):
    def test_real_zero_and_abrupt_change_are_preserved_for_review(self):
        times = pd.Series(pd.date_range("2026-01-01", periods=3, freq="10s"))
        flags, report = inspect_channel(pd.Series([6., 0., 6.]), times, "do")
        self.assertEqual(report["invalid_rows"], 0)
        self.assertEqual(report["zero_rows"], 1)
        self.assertTrue(flags.loc[1, "zero_review"])
        self.assertTrue(flags.loc[1, "rapid_change_review"])

    def test_plateau_does_not_bridge_missing_time(self):
        times = pd.Series(pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 03:00"]))
        _, report = inspect_channel(pd.Series([7., 7., 7.]), times, "ph")
        self.assertEqual(report["longest_exact_plateau_seconds"], 60)

    def test_valid_spans_break_on_invalid_input_and_large_gap(self):
        times = pd.Series(pd.date_range("2026-01-01", periods=5, freq="10s"))
        spans = valid_spans(pd.Series([True, True, False, True, True]), times)
        self.assertEqual([s["rows"] for s in spans], [2, 2])


if __name__ == "__main__":
    unittest.main()
