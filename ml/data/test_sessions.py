import unittest

import pandas as pd

from ml.data.sessions import documented_oman_utc, session_rows


class SessionTests(unittest.TestCase):
    def test_documented_offset_rolls_date_without_inventing_receipt_time(self):
        utc = documented_oman_utc(pd.Series(["2026-04-01 01:00:00", "bad"]))
        self.assertEqual(utc.iloc[0], pd.Timestamp("2026-03-31T21:00:00Z"))
        self.assertTrue(pd.isna(utc.iloc[1]))

    def test_explicit_offset_is_not_localized_twice(self):
        utc = documented_oman_utc(pd.Series(["2026-04-01T01:00:00+04:00"]))
        self.assertEqual(utc.iloc[0], pd.Timestamp("2026-03-31T21:00:00Z"))

    def test_groups_separate_devices_and_long_gaps(self):
        frame = pd.DataFrame({"source_row": [2, 3, 4, 5], "pond_id": ["a", "a", "a", "b"],
                              "timestamp_local": pd.to_datetime(["2026-04-01 00:00", "2026-04-01 00:10", "2026-04-01 03:00", "2026-04-01 00:00"])})
        result = session_rows(frame, "offline", "a" * 64)
        self.assertEqual(result.session_id.nunique(), 3)
        self.assertEqual(result.loc[result.source_row.isin([2, 3]), "session_id"].nunique(), 1)
        self.assertFalse(result.training_approved.any())

    def test_ids_are_stable_after_source_order_changes(self):
        frame = pd.DataFrame({"source_row": [2, 3], "pond_id": ["a", "a"],
                              "timestamp_local": pd.to_datetime(["2026-04-01 00:00", "2026-04-01 00:10"])})
        first = session_rows(frame, "live", "b" * 64).set_index("source_row").session_id
        second = session_rows(frame.iloc[::-1], "live", "b" * 64).set_index("source_row").session_id
        pd.testing.assert_series_equal(first.sort_index(), second.sort_index())


if __name__ == "__main__":
    unittest.main()
