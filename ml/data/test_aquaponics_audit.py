import unittest

import pandas as pd

from ml.data.audit_aquaponics import consecutive_match_runs, channel_summary


class AquaponicsAuditTests(unittest.TestCase):
    def test_shared_segments_require_adjacent_rows_in_both_sources(self):
        matches = pd.DataFrame({"left_row": [10, 11, 12, 20], "right_row": [30, 31, 40, 41]})
        self.assertEqual(consecutive_match_runs(matches).rows.tolist(), [2, 1, 1])

    def test_numeric_flags_preserve_zero_and_detect_sensor_sentinel(self):
        result = channel_summary(pd.Series([-127, 0, 28, "bad", None]), "temperature")
        self.assertEqual(result["minus_127"], 1)
        self.assertEqual(result["zero"], 1)
        self.assertEqual(result["nonnumeric"], 1)
        self.assertEqual(result["missing"], 1)


if __name__ == "__main__":
    unittest.main()
