"""Inspect repeated measurements and metadata without changing source values."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


WATER = ["Temperature (°C)", "Dissolved Oxygen (mg/L)", "pH", "Turbidity (NTU)"]


def constant_runs(frame):
    changed = frame[WATER].ne(frame[WATER].shift()).any(axis=1)
    groups = changed.cumsum()
    return frame.groupby(groups).agg(first_source_row=("source_row", "min"),
        last_source_row=("source_row", "max"), rows=("source_row", "size"),
        start=("Datetime", "min"), end=("Datetime", "max"))


def fraction_noninteger(values):
    values = pd.to_numeric(values, errors="coerce")
    return int((values.notna() & ~np.isclose(values, values.round(), atol=1e-9, rtol=0)).sum())


def run(path, output):
    if output.exists():
        raise FileExistsError(output)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = pd.read_excel(path)
    frame["source_row"] = np.arange(2, len(frame) + 2)
    frame["Datetime"] = pd.to_datetime(frame.Datetime, errors="coerce")
    runs = constant_runs(frame)
    checks = {}
    for field, expected in [("hour", frame.Datetime.dt.hour), ("day", frame.Datetime.dt.day),
                            ("Month_Num", frame.Datetime.dt.month), ("month_x", frame.Datetime.dt.month),
                            ("month_y", frame.Datetime.dt.month)]:
        actual = pd.to_numeric(frame[field], errors="coerce")
        checks[field] = {"noninteger_rows": fraction_noninteger(actual),
                         "mismatch_with_timestamp": int((~np.isclose(actual, expected, atol=1e-9, rtol=0)).sum())}
    disease = frame["Disease Occurrence (Cases)"]
    status = frame["Health Status"].astype(str)
    thermal = frame["Thermal Risk Index"].astype(str)
    do = pd.to_numeric(frame["Dissolved Oxygen (mg/L)"], errors="coerce")
    result = {"sha256": digest, "rows": len(frame), "invalid_timestamps": int(frame.Datetime.isna().sum()),
        "duplicate_timestamps": int(frame.Datetime.duplicated().sum()),
        "start_local": str(frame.Datetime.min()), "end_local": str(frame.Datetime.max()),
        "hourly_successive_differences": int(frame.Datetime.diff().eq(pd.Timedelta(hours=1)).sum()),
        "core_water_unique_vectors": int(len(frame[WATER].drop_duplicates())),
        "constant_run_length_counts": {str(k): int(v) for k, v in runs.rows.value_counts().sort_index().items()},
        "unchanged_successive_rows": int(frame[WATER].eq(frame[WATER].shift()).all(axis=1).sum()),
        "calendar_field_checks": checks, "fractional_disease_case_rows": fraction_noninteger(disease),
        "do_min": float(do.min()), "do_max": float(do.max()), "observed_do_below_5": int(do.lt(5).sum()),
        "label_counts": {name: frame[name].value_counts(dropna=False).to_dict()
                         for name in ["Low Oxygen Alert", "Health Status", "Thermal Risk Index"]},
        "health_thermal_mapping_mismatches": int((status.ne(np.where(thermal.eq("High"), "At Risk", "Stable"))).sum()),
        "training_approved": False,
        "interpretation": "Repeated values and fractional calendar/count fields are construction/interpolation warnings. Original measurement cadence and exact generation process are not established by this audit."}
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Raw workbook changed during inspection")
    output.mkdir(parents=True)
    runs.to_csv(output / "constant_water_runs.csv", index=False)
    (output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/colombia-review-2026-11-05"))
    args = parser.parse_args()
    paths = list(Path("Datasets/O1D3").rglob("*.xlsx")) if args.workbook is None else [args.workbook]
    if len(paths) != 1:
        raise ValueError("Specify exactly one --workbook")
    run(paths[0], args.output)
