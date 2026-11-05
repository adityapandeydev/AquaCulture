import unittest
import tempfile
from pathlib import Path

import pandas as pd
import openpyxl

from ml.data.prepare import clean_frame, hourly_observations, metric_name, parse_times, spreadsheet_tables, time_splits


class CleaningTests(unittest.TestCase):
    def test_short_spreadsheet_header_does_not_drop_extra_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.xlsx"
            workbook = openpyxl.Workbook()
            workbook.active.append(["Time", "DO"])
            workbook.active.append(["12:00", 6, "calibration note"])
            workbook.save(path)
            workbook.close()
            _, frame, _ = list(spreadsheet_tables(path))[0]
            self.assertEqual(frame.iloc[0, 2], "calibration note")

    def test_water_temperature_is_separate_from_room_temperature(self):
        frame = pd.DataFrame({"  Date": ["2022-09-15"], "Time": ["09:59:22"],
                              "Room Temperature": [32], "Water Temperature": [28.19],
                              "pH": [590], "Calculated Ph": [7.0], "DO": [0]})
        clean, _, _ = clean_frame(frame, "shrimp_fixture")
        self.assertEqual(clean.iloc[0].temperature, 28.19)
        self.assertTrue(pd.isna(clean.iloc[0].ph))
        self.assertEqual(clean.iloc[0].do, 0)
        self.assertEqual(clean.iloc[0].timestamp_local, pd.Timestamp("2022-09-15 09:59:22"))

    def test_combined_nitrogen_and_turbidity_depth_are_not_relabelled(self):
        self.assertIsNone(metric_name("NITRATE N + NITRITE N (mg/l)"))
        self.assertIsNone(metric_name("Turbidity (cm)"))

    def test_blank_rows_remain_traceable_in_quarantine(self):
        clean, rejected, _ = clean_frame(pd.DataFrame({"DO": [None]}), "fixture", row_start=80)
        self.assertEqual(len(clean), 0)
        self.assertEqual(rejected.iloc[0].source_row, 80)
        self.assertEqual(rejected.iloc[0].rejection_reason, "no_valid_measurements")
    def test_unknown_timezone_is_not_invented(self):
        result = parse_times(pd.Series(["2021-06-19 00:00:05 CET", "2021-06-19T00:00:05+01:00", "bad"]))
        self.assertTrue(pd.isna(result.loc[0, "timestamp_utc"]))
        self.assertEqual(result.loc[1, "timestamp_utc"], pd.Timestamp("2021-06-18T23:00:05Z"))
        self.assertTrue(pd.isna(result.loc[2, "timestamp_local"]))

    def test_invalid_values_are_flagged_without_filling(self):
        frame = pd.DataFrame({"timestamp": ["2024-01-01 01:00", "2024-01-01 02:00"],
                              "TEMP": [-127, 28], "PH": [15, 8], "DO": [0, 6]})
        clean, _, _ = clean_frame(frame, "fixture")
        self.assertTrue(pd.isna(clean.iloc[0].temperature))
        self.assertTrue(pd.isna(clean.iloc[0].ph))
        self.assertEqual(clean.iloc[0].do, 0)
        self.assertIn("temperature:screening_range", clean.iloc[0].quality_flags)

    def test_conflicts_are_quarantined_not_averaged(self):
        frame = pd.DataFrame({"timestamp": ["2024-01-01"] * 3, "DO": [5, 5, 8]})
        clean, rejected, report = clean_frame(frame, "fixture")
        self.assertEqual(len(clean), 0)
        self.assertEqual(len(rejected), 3)
        self.assertEqual(report["conflicting_timestamp_rows"], 3)

    def test_identical_readings_at_different_times_are_retained(self):
        frame = pd.DataFrame({"timestamp": ["2024-01-01", "2024-01-02"], "DO": [5, 5]})
        clean, _, _ = clean_frame(frame, "fixture")
        self.assertEqual(len(clean), 2)

    def test_distinct_offsets_do_not_create_false_duplicate_conflicts(self):
        frame = pd.DataFrame({"timestamp": ["2024-01-01T01:00+01:00", "2024-01-01T01:00+00:00"], "DO": [5, 6]})
        clean, rejected, _ = clean_frame(frame, "fixture")
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(rejected), 0)

    def test_gap_bins_are_excluded_from_split_boundaries(self):
        frame = pd.DataFrame({"pond_id": ["a"] * 4,
                              "timestamp_local": pd.date_range("2024-01-01", periods=4, freq="h"),
                              "observation_count": [1, 0, 1, 1]})
        result = time_splits(frame)
        self.assertEqual(result.loc[1, "split"], "gap")
        self.assertEqual(set(result.split), {"train", "validation", "test", "gap"})

    def test_hourly_aggregation_stays_within_pond_and_marks_bin_end(self):
        frame = pd.DataFrame({"timestamp": ["2024-01-01 00:10", "2024-01-01 00:20"],
                              "Station": ["a", "b"], "DO": [2, 9]})
        clean, _, _ = clean_frame(frame, "fixture")
        hourly = hourly_observations(clean)
        self.assertEqual(len(hourly), 2)
        self.assertEqual(set(hourly.do), {2, 9})
        self.assertEqual(set(hourly.timestamp_local), {pd.Timestamp("2024-01-01 01:00")})

    def test_splits_never_divide_equal_timestamps(self):
        frame = pd.DataFrame({"pond_id": ["a"] * 10,
                              "timestamp_local": pd.to_datetime(["2024-01-01"] * 8 + ["2024-01-02", "2024-01-03"])})
        splits = time_splits(frame)
        self.assertEqual(splits.groupby("timestamp_local").split.nunique().max(), 1)
        groups = splits.groupby("split").timestamp_local.agg(["min", "max"])
        self.assertLess(groups.loc["train", "max"], groups.loc["validation", "min"])
        self.assertLess(groups.loc["validation", "max"], groups.loc["test", "min"])


if __name__ == "__main__":
    unittest.main()
