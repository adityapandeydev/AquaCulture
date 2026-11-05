"""Audit local pond CSVs in source units; no repairs, conversions or model fitting."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .prepare import metric_name, parse_times


def channel_summary(values, metric):
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[numeric.notna() & np.isfinite(numeric)]
    result = {"missing": int(values.isna().sum()), "nonnumeric": int((values.notna() & numeric.isna()).sum()),
              "nonfinite": int((numeric.notna() & ~np.isfinite(numeric)).sum()),
              "negative": int(finite.lt(0).sum()), "zero": int(finite.eq(0).sum()),
              "minus_127": int(finite.eq(-127).sum()), "minus_one": int(finite.eq(-1).sum()),
              "unique_finite": int(finite.nunique()),
              "min": float(finite.min()) if len(finite) else None,
              "max": float(finite.max()) if len(finite) else None}
    if metric == "ph":
        result["outside_0_14"] = int((finite.lt(0) | finite.gt(14)).sum())
    if metric in {"ammonia", "nitrate"}:
        result["above_one_million_source_units"] = int(finite.gt(1e6).sum())
    return result


def consecutive_match_runs(matches):
    ordered = matches.sort_values(["left_row", "right_row"]).copy()
    new = ordered.left_row.diff().ne(1) | ordered.right_row.diff().ne(1)
    return ordered.groupby(new.cumsum()).agg(left_start=("left_row", "min"), left_end=("left_row", "max"),
        right_start=("right_row", "min"), right_end=("right_row", "max"), rows=("left_row", "size"))


def run(root, output):
    if output.exists():
        raise FileExistsError(output)
    reports, normalized = {}, {}
    for path in sorted(root.glob("*.csv")):
        raw = pd.read_csv(path, low_memory=False)
        mapping = {c: metric_name(c) for c in raw if metric_name(c)}
        values = raw[list(mapping)].rename(columns=mapping).apply(pd.to_numeric, errors="coerce")
        time_column = "created_at" if "created_at" in raw else "Unnamed: 0"
        parsed = parse_times(raw[time_column])
        # Unknown CET timezone is preserved; these matches use recorded wall time,
        # never claim cross-site absolute-time equivalence.
        values["timestamp_recorded"] = parsed.timestamp_original
        values["source_row"] = np.arange(2, len(raw) + 2)
        normalized[path.name] = values
        local = parsed.timestamp_local
        delta = local.diff().dt.total_seconds()
        signatures = pd.util.hash_pandas_object(raw[list(mapping)].astype(str), index=False)
        distinct_at_time = signatures.groupby(local, dropna=False).transform("nunique")
        reports[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(raw),
            "source_headers": {metric: column for column, metric in mapping.items()},
            "channels": {metric: channel_summary(raw[column], metric) for column, metric in mapping.items()},
            "timestamp_column": time_column, "timezone_status": parsed.timezone_status.value_counts().to_dict(),
            "invalid_timestamp_rows": int(local.isna().sum()),
            "source_order_backwards": int(delta.lt(0).sum()),
            "duplicate_wall_time_rows": int((local.notna() & local.duplicated(keep=False)).sum()),
            "conflicting_wall_time_rows": int((local.notna() & distinct_at_time.gt(1)).sum()),
            "median_positive_source_interval_seconds": float(delta[delta.gt(0)].median()),
            "training_approved": False}
        print("Audited", path.name, flush=True)
    left, right = normalized["IoTpond1.csv"], normalized["IoTPond2.csv"]
    water = ["temperature", "ph", "do", "turbidity"]
    keys = ["timestamp_recorded"] + water
    # Rounding matches the previous unordered overlap audit; source units remain unchanged.
    left = left.copy(); right = right.copy()
    left[water] = left[water].round(6); right[water] = right[water].round(6)
    valid_left, valid_right = left.dropna(subset=keys), right.dropna(subset=keys)
    # Guard against ambiguous many-to-many matching from duplicated source keys.
    unique_left = valid_left.drop_duplicates(keys, keep=False)
    unique_right = valid_right.drop_duplicates(keys, keep=False)
    matches = unique_left[keys + ["source_row"]].merge(unique_right[keys + ["source_row"]], on=keys,
                                                     suffixes=("_left", "_right"), validate="one_to_one")
    matches = matches.rename(columns={"source_row_left": "left_row", "source_row_right": "right_row"})
    runs = consecutive_match_runs(matches)
    result = {"files": reports, "pond1_pond2_shared_recorded_timestamp_water_rows": len(matches),
              "matching_basis": "Exact recorded timestamp string and four water channels rounded to six decimals; nitrogen excluded. Ambiguous duplicate join keys omitted. Source-row adjacency required in both files for segment runs.",
              "longest_shared_source_order_run_rows": int(runs.rows.max()) if len(runs) else 0,
              "shared_runs_at_least_100_rows": int(runs.rows.ge(100).sum()),
              "training_approved": False}
    # Check source preservation before writing derived evidence.
    for filename, report in reports.items():
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != report["sha256"]:
            raise ValueError("Source changed during review")
    output.mkdir(parents=True)
    matches[["left_row", "right_row", "timestamp_recorded"]].to_csv(output / "pond1_pond2_shared_rows.csv.gz", index=False)
    runs.to_csv(output / "pond1_pond2_shared_runs.csv", index=False)
    (output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Shared timestamp/water rows", len(matches), "; longest source-order run", result["longest_shared_source_order_run_rows"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets/O1D2"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/aquaponics-review-2026-11-05"))
    args = parser.parse_args()
    run(args.root, args.output)
