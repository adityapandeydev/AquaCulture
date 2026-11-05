"""Audit Oman source coverage without changing measurements or fitting models."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .prepare import clean_frame


def covered_bins(frame, frequency="1h"):
    """Report occupied five-minute subslots; counts alone can hide burst sampling."""
    indexed = frame.set_index("timestamp_local").sort_index()
    groups = indexed.resample(frequency, closed="left", label="right")
    result = groups.source_row.count().to_frame("readings")
    slots = pd.Series(indexed.index.floor("5min"), index=indexed.index)
    result["occupied_five_minute_slots"] = slots.resample(frequency, closed="left", label="right").nunique()
    return result


def complete_windows(mask, history, horizon):
    """Require every hourly bin from history through target, with no bridged gaps."""
    width = history + horizon
    return int(mask.astype(int).rolling(width).sum().eq(width).sum())


def run(root, output):
    if output.exists():
        raise FileExistsError(output)
    reports, clean_sets = {}, {}
    output.mkdir(parents=True)
    for name, filename, end in [("offline", "raw_readings.csv", "2026-04-02"),
                                ("live", "raw_readings_new.csv", "2026-04-11")]:
        path = root / "data/raw" / name / filename
        raw = pd.read_csv(path)
        timestamp = pd.to_datetime(raw.timestamp, errors="coerce")
        start = pd.Timestamp("2026-03-26" if name == "offline" else "2026-04-01")
        in_period = timestamp.ge(start) & timestamp.lt(pd.Timestamp(end))
        # This filter establishes stated-period membership, not verified pond identity.
        clean, rejected, quality = clean_frame(raw, "oman_" + name)
        clean_sets[name] = clean
        daily = timestamp.dt.strftime("%Y-%m-%d").value_counts().sort_index().to_dict()
        periods = []
        for label, data in [("all", clean), ("stated_period", clean[clean.timestamp_local.ge(start) & clean.timestamp_local.lt(pd.Timestamp(end))])]:
            for pond, group in data.groupby("pond_id"):
                bins = covered_bins(group)
                bins["occupied_slot_fraction"] = bins.occupied_five_minute_slots / 12
                # Sensitivity thresholds, not final scientific acceptance rules.
                sensitivity = {}
                for slots in [9, 11, 12]:
                    mask = bins.occupied_five_minute_slots.ge(slots)
                    sensitivity[str(slots)] = {"eligible_bins": int(mask.sum()),
                        "candidate_examples": {f"history_{h}_horizon_{k}": complete_windows(mask, h, k)
                                               for h in [6, 12, 24] for k in [1, 3, 6]}}
                bins.to_csv(output / f"{name}_{label}_hourly_coverage.csv")
                periods.append({"period": label, "series": pond, "accepted_rows": len(group),
                                "calendar_bins": len(bins), "populated_bins": int(bins.readings.gt(0).sum()),
                                "coverage_sensitivity": sensitivity})
        metrics = {}
        for column in ["temp_c", "ph", "do_mgL"]:
            values = pd.to_numeric(raw[column], errors="coerce")
            metrics[column] = {"missing_or_nonfinite": int((values.isna() | ~np.isfinite(values)).sum()),
                               "zero": int(values.eq(0).sum()), "negative": int(values.lt(0).sum()),
                               "min": float(values.min()), "median": float(values.median()), "max": float(values.max())}
        reports[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "raw_rows": len(raw),
                         "timestamp_min": str(timestamp.min()), "timestamp_max": str(timestamp.max()),
                         "stated_period_rows": int(in_period.sum()), "outside_stated_period_rows": int((~in_period).sum()),
                         "source_order_backward_steps": int(timestamp.diff().dt.total_seconds().lt(0).sum()),
                         "daily_raw_counts": daily, "metrics": metrics, "cleaning": quality, "periods": periods,
                         "training_approved": False}
    left, right = clean_sets["offline"], clean_sets["live"]
    columns = ["timestamp_local", "temperature", "ph", "do"]
    overlap = left[columns].merge(right[columns], on=columns)
    calibration = {p.name: json.loads(p.read_text()) for p in (root / "data/calibration").glob("*.json")}
    ph = calibration["calibration_ph.json"]
    checks = {key: ph["slope_m"] * point["voltage_v_avg"] + ph["offset_b"]
              for key, point in ph["points"].items()}
    result = {"sources": reports, "exact_cross_file_timestamp_water_matches": len(overlap),
              "calibration_files": calibration, "ph_equation_at_recorded_buffers": checks,
              "timezone_evidence": "Pinned docs/data_dictionary.md explicitly declares local Oman time GMT+4 for both raw files. Raw timestamps contain no offsets; existing cleaned outputs are not relocalized by this audit.",
              "coverage_policy": "Hourly candidates, 12 possible five-minute subslots; 9/11/12 occupied slots are sensitivity checks, not final acceptance. Presence does not establish valid calibrated coverage.",
              "window_policy": "Every bin through the horizon must satisfy occupancy. Counts are before train/validation/test/calibration partitions and quality approval, not final sample sizes."}
    (output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({name: {k: r[k] for k in ["raw_rows", "stated_period_rows", "outside_stated_period_rows"]}
                      for name, r in reports.items()}, indent=2))
    print("Exact cross-file timestamp/water matches:", len(overlap))
    print("Saved", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets/external/oman_tilapia"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/oman-review-2026-11-05"))
    args = parser.parse_args()
    run(args.root, args.output)
