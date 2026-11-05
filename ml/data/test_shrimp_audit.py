import unittest

import pandas as pd

from ml.data.audit_shrimp import candidate_sessions, ph_representation


class ShrimpAuditTests(unittest.TestCase):
    def test_ph_classification_does_not_treat_raw_count_as_calibrated_ph(self):
        values = pd.Series([8.2, 590, "0.04306121760.979591836734693", None, -1, float("inf")])
        self.assertEqual(ph_representation(values).tolist(),
                         ["numeric_0_to_14_unverified", "above_14_unverified", "nonnumeric",
                          "missing", "negative", "nonfinite"])

    def test_session_candidates_keep_source_rows_and_split_long_gaps(self):
        frame = pd.DataFrame({"source_row": [4, 3, 2],
                              "timestamp": pd.to_datetime(["2022-01-01 03:00", "2022-01-01 00:10", "2022-01-01 00:00"])})
        result = candidate_sessions(frame)
        self.assertEqual(result.source_row.tolist(), [2, 3, 4])
        self.assertEqual(result.session_candidate.tolist(), [1, 1, 2])


if __name__ == "__main__":
    unittest.main()
