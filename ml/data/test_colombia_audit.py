import unittest

import pandas as pd

from ml.data.audit_colombia import WATER, constant_runs, fraction_noninteger


class ColombiaAuditTests(unittest.TestCase):
    def test_constant_water_runs_ignore_changing_derived_columns(self):
        frame = pd.DataFrame({c: [1, 1, 2, 2, 1] for c in WATER})
        frame["source_row"] = [2, 3, 4, 5, 6]
        frame["Datetime"] = pd.date_range("2024-01-01", periods=5, freq="h")
        frame["derived"] = range(5)
        runs = constant_runs(frame)
        self.assertEqual(runs.rows.tolist(), [2, 2, 1])
        self.assertEqual(runs.first_source_row.tolist(), [2, 4, 6])

    def test_fractional_count_check_handles_missing_and_rounding(self):
        self.assertEqual(fraction_noninteger(pd.Series([1, 2, 1.5, None, 1.00000000001])), 1)


if __name__ == "__main__":
    unittest.main()
