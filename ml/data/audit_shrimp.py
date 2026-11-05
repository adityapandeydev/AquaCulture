"""Read-only channel/session audit of the supplied shrimp-buoy workbook.

No formulas are evaluated, no units are inferred and no cleaned values are changed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


def ph_representation(values):
    numeric = pd.to_numeric(values, errors="coerce")
    result = pd.Series("numeric_0_to_14_unverified", index=values.index)
    result.loc[numeric > 14] = "above_14_unverified"
    result.loc[numeric < 0] = "negative"
    result.loc[numeric.notna() & ~np.isfinite(numeric)] = "nonfinite"
    result.loc[values.notna() & numeric.isna()] = "nonnumeric"
    result.loc[values.isna()] = "missing"
    return result


def candidate_sessions(frame):
    result = frame[frame.timestamp.notna()].sort_values(["timestamp", "source_row"]).copy()
    delta = result.timestamp.diff().dt.total_seconds()
    result["session_candidate"] = (delta.isna() | delta.gt(3600)).cumsum()
    return result


def numeric_summary(values):
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[numeric.notna() & np.isfinite(numeric)]
    return {"rows": len(values), "missing": int(values.isna().sum()),
            "nonnumeric": int((values.notna() & numeric.isna()).sum()),
            "nonfinite": int((numeric.notna() & ~np.isfinite(numeric)).sum()),
            "negative": int(finite.lt(0).sum()), "zero": int(finite.eq(0).sum()),
            "unique_finite": int(finite.nunique()),
            "quantiles": {str(q): float(finite.quantile(q)) for q in [0, .01, .5, .99, 1]} if len(finite) else {}}


def run(workbook_path, output):
    if output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    digest = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        data_rows = list(book["Data"].values)
        width = max(map(len, data_rows))
        header = list(data_rows[0]) + [None] * (width - len(data_rows[0]))
        header = [str(value).strip() if value is not None else f"unnamed_{i}" for i, value in enumerate(header)]
        frame = pd.DataFrame(data_rows[1:]).reindex(columns=range(width))
        frame.columns = header
        frame["source_row"] = np.arange(2, len(frame) + 2)
        reference_rows = list(book["Sheet2"].values)
    finally:
        book.close()
    date = frame.Date.astype(str).str.replace(r" 00:00:00$", "", regex=True)
    frame["timestamp"] = pd.to_datetime(date + " " + frame.Time.astype(str), format="mixed", errors="coerce")
    frame["ph_representation"] = ph_representation(frame["pH"])
    channels = ["pH", "Calculated Ph", "DO", "Turbidity", "TDS", "Humidity", "Room Temperature", "Water Temperature"]
    summaries = {name: numeric_summary(frame[name]) for name in channels}
    mapped = candidate_sessions(frame[["source_row", "timestamp", "ph_representation"]])
    sessions = []
    for number, group in mapped.groupby("session_candidate"):
        sessions.append({"candidate": int(number), "rows": len(group),
                         "start_local": str(group.timestamp.min()), "end_local": str(group.timestamp.max()),
                         "duration_hours": (group.timestamp.max() - group.timestamp.min()).total_seconds() / 3600,
                         "first_source_row": int(group.source_row.min()), "last_source_row": int(group.source_row.max()),
                         "ph_representations": group.ph_representation.value_counts().to_dict()})
    # Retain contiguous source-order representation blocks for investigation.
    blocks = frame.ph_representation.ne(frame.ph_representation.shift()).cumsum()
    runs = frame.groupby(blocks).agg(first_source_row=("source_row", "min"), last_source_row=("source_row", "max"),
                                    rows=("source_row", "count"), representation=("ph_representation", "first"))
    refs = {}
    for label, column, lower, upper in [("PH7", 2, 2, 54), ("PH9", 6, 2, 54), ("PH4", 2, 55, len(reference_rows))]:
        values = pd.Series([r[column] if len(r) > column else None for r in reference_rows[lower:upper]], dtype=object)
        refs[label] = numeric_summary(values)
    formulas, errors = [], {}
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    try:
        for row in book["Data"].iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    value = cell.value
                    formulas.append({"cell": cell.coordinate, "formula": value if isinstance(value, str) else value.text,
                                     "range": None if isinstance(value, str) else value.ref})
                elif cell.data_type == "e":
                    key = cell.column_letter + ":" + str(cell.value)
                    errors[key] = errors.get(key, 0) + 1
    finally:
        book.close()
    valid = frame.timestamp.notna()
    source_delta = frame.loc[valid, "timestamp"].diff().dt.total_seconds()
    result = {"workbook_sha256": digest, "data_rows": len(frame), "valid_timestamp_rows": int(valid.sum()),
              "invalid_timestamp_rows": int((~valid).sum()), "source_order_backward_steps": int(source_delta.lt(0).sum()),
              "source_order_forward_steps": int(source_delta.gt(0).sum()),
              "duplicate_timestamp_rows": int(frame.loc[valid].duplicated("timestamp", keep=False).sum()),
              "ph_representations": frame.ph_representation.value_counts().to_dict(),
              "numeric_channel_summaries": summaries, "reference_readings": refs,
              "formulas": formulas, "stored_errors_by_column": errors,
              "session_candidate_count": len(sessions),
              "session_method": "Sorted naive local timestamps; split at gaps greater than 1h. Candidates are continuity groups, not verified ponds, field deployments or calibration events.",
              "session_candidates": sessions, "training_approved": False,
              "conversion_approved": False}
    if hashlib.sha256(workbook_path.read_bytes()).hexdigest() != digest:
        raise ValueError("Workbook changed during inspection")
    output.mkdir(parents=True)
    mapped.to_csv(output / "candidate_session_rows.csv.gz", index=False)
    runs.to_csv(output / "ph_representation_runs.csv", index=False)
    (output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["data_rows", "valid_timestamp_rows", "source_order_backward_steps",
                                            "session_candidate_count", "ph_representations", "stored_errors_by_column"]}, indent=2))
    print("Saved", output, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=Path("Datasets/external/shrimp_buoy/TestData_DBT6.xlsx"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/shrimp-channel-review-2026-11-05"))
    args = parser.parse_args()
    run(args.workbook, args.output)
