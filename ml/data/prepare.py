"""Conservative dataset audit/cleaning. No model fitting, interpolation or unit guessing.

Run from the repository root: python -m ml.data.prepare
Raw files are read only; outputs live under the ignored Datasets/processed directory.
"""
import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


METRICS = {
    "do": {"do", "dissolvedoxygen", "disolvedoxygen", "domgl", "doppm"},
    "temperature": {"temp", "temperature", "tempc", "temperaturec", "watertemperature"},
    "ph": {"ph"},
    "turbidity": {"turbidity", "turbidityntu"},
    "ammonia": {"ammonia", "ammoniamgl"},
    "nitrate": {"nitrate", "nitrateppm"},
    "salinity": {"salinity", "salinityppt"},
    "nitrite": {"nitrite"},
}
# Screening bounds, NOT species safety thresholds. Suspicious extremes outside
# these broad bounds become missing, with their source row retained for review.
BOUNDS = {"temperature": (-3, 60), "ph": (0, 14)}


def token(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def metric_name(column):
    key = token(column)
    if "nitrate" in key and "nitrite" in key:
        return None  # Combined nitrogen measurements are not nitrate alone.
    for name, aliases in METRICS.items():
        if key in aliases:
            return name
    for prefix, name in [("dissolvedoxygen", "do"), ("disolvedoxygen", "do"),
                         ("ammonia", "ammonia"), ("nitrate", "nitrate"), ("nitrite", "nitrite")]:
        if key.startswith(prefix) and not any(x in key for x in ["min", "max", "mean", "alert"]):
            return name
    return None


def parse_times(values, dayfirst=False):
    text = values.fillna("").astype(str).str.strip()
    cet = text.str.contains(r"\sCET$", regex=True)
    utc = text.str.contains(r"(?:Z|\sUTC|[+-]\d{2}:?\d{2})$", regex=True)
    wall = text.str.replace(r"\s(?:CET|UTC)$", "", regex=True)
    wall = wall.str.replace(r"(?:Z|[+-]\d{2}:?\d{2})$", "", regex=True)
    local = pd.to_datetime(wall, format="mixed", dayfirst=dayfirst, errors="coerce")
    absolute = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    absolute.loc[utc] = pd.to_datetime(text.loc[utc].str.replace(r"\sUTC$", "+00:00", regex=True),
                                      format="mixed", errors="coerce", utc=True)
    status = pd.Series("unspecified", index=values.index)
    status.loc[cet] = "unverified_CET"
    status.loc[utc] = "explicit_offset"
    return pd.DataFrame({"timestamp_original": text, "timestamp_local": local,
                         "timestamp_utc": absolute, "timezone_status": status})


def clean_frame(frame, dataset_id, row_start=2):
    frame = frame.reset_index(drop=True).copy()
    # Keep exact source row references before filtering, sorting or deduplication.
    out = pd.DataFrame({"source_row": np.arange(row_start, row_start + len(frame))})
    selected = {}
    for column in frame.columns:
        metric = metric_name(column)
        if metric and metric not in selected:
            selected[metric] = column
    lookup = {token(c): c for c in frame.columns}
    pond_col = next((lookup[k] for k in ["station", "pondid", "nodeid"] if k in lookup), None)
    pond = frame[pond_col].fillna("").astype(str).str.strip().str.lower() if pond_col else pd.Series("unidentified", index=frame.index)
    out["pond_id"] = dataset_id + ":" + pond
    time_col = next((lookup[k] for k in ["timestamp", "datetime", "createdat"] if k in lookup), None)
    if not time_col and "unnamed0" in lookup:
        candidate = frame[lookup["unnamed0"]].astype(str)
        if candidate.str.match(r"\d{4}-\d{2}-\d{2}T").mean() > .5:
            time_col = lookup["unnamed0"]
    dayfirst = False
    if time_col:
        values = frame[time_col]
    elif "date" in lookup:
        values = frame[lookup["date"]].astype(str)
        dayfirst = True
        if "time" in lookup:
            values = values.str.replace(r" 00:00:00$", "", regex=True) + " " + frame[lookup["time"]].astype(str)
    else:
        values = pd.Series("", index=frame.index)
    out = pd.concat([out, parse_times(values, dayfirst)], axis=1)
    flags = pd.Series("", index=frame.index)
    stats = {}
    for metric, column in selected.items():
        raw = frame[column]
        numeric = pd.to_numeric(raw, errors="coerce").astype(float)
        invalid = numeric.notna() & ~np.isfinite(numeric)
        nonnumeric = raw.notna() & numeric.isna()
        lower, upper = BOUNDS.get(metric, (0, np.inf))
        outside = numeric.notna() & ((numeric < lower) | (numeric > upper))
        for mask, reason in [(nonnumeric, "nonnumeric"), (invalid, "nonfinite"), (outside, "screening_range")]:
            flags.loc[mask] += metric + ":" + reason + ";"
        numeric = numeric.mask(invalid | outside)
        if metric in {"do", "ammonia", "nitrate", "nitrite"}:
            # Review flags retain values; upper limits depend on units, calibration
            # and chemistry and must not be used to manufacture benign readings.
            threshold = {"do": 30, "ammonia": 100, "nitrate": 1000, "nitrite": 100}[metric]
            suspect = numeric > threshold
            flags.loc[suspect] += metric + ":extreme_review;"
        out[metric] = numeric
        stats[metric] = {"source_column": str(column), "missing_after_screening": int(numeric.isna().sum()),
                         "invalid_numeric": int((invalid | outside | nonnumeric).sum()),
                         "min": float(numeric.min()) if numeric.notna().any() else None,
                         "max": float(numeric.max()) if numeric.notna().any() else None,
                         "unique_values": int(numeric.nunique()),
                         "source_unit_review_required": True}
    out["quality_flags"] = flags.str.rstrip(";")
    out["dataset_id"] = dataset_id
    has_time = bool(time_col or "date" in lookup)
    invalid_time = out.timestamp_local.isna() if has_time else pd.Series(False, index=out.index)
    out["rejection_reason"] = ""
    if selected:
        out.loc[out[list(selected)].isna().all(axis=1), "rejection_reason"] = "no_valid_measurements"
    out.loc[invalid_time, "rejection_reason"] = "invalid_timestamp"
    missing_pond = pond.eq("")
    out.loc[missing_pond, "rejection_reason"] += ";missing_pond"
    # Compare ORIGINAL measurements, before screening could collapse distinct bad values.
    signature = pd.util.hash_pandas_object(frame[list(selected.values())].astype(str), index=False)
    time_key = out.timestamp_local.astype(str)
    explicit = out.timestamp_utc.notna()
    time_key.loc[explicit] = out.loc[explicit, "timestamp_utc"].astype(str)
    key = [out.pond_id, time_key]
    counts = signature.groupby(key, dropna=False).transform("nunique")
    conflicting = out.timestamp_local.notna() & (counts > 1)
    out.loc[conflicting, "rejection_reason"] += ";conflicting_timestamp"
    rejected = out[out.rejection_reason.ne("")].copy()
    accepted = out[out.rejection_reason.eq("")].copy()
    duplicate = accepted.timestamp_local.notna() & pd.DataFrame(
        {"pond": accepted.pond_id, "time": time_key.loc[accepted.index]}).duplicated()
    duplicates = accepted[duplicate].copy()
    duplicates["rejection_reason"] = "exact_measurement_duplicate"
    rejected = pd.concat([rejected, duplicates], ignore_index=True)
    accepted = accepted[~duplicate].sort_values(["pond_id", "timestamp_local", "source_row"])
    cadence = {}
    for pond_id, group in accepted[accepted.timestamp_local.notna()].groupby("pond_id"):
        delta = group.timestamp_local.diff().dt.total_seconds().dropna()
        cadence[pond_id] = {"rows": len(group), "median_interval_seconds": float(delta.median()) if len(delta) else None,
                           "gaps_over_hour": int((delta > 3600).sum()),
                           "start": str(group.timestamp_local.min()), "end": str(group.timestamp_local.max())}
        cols = list(selected)
        cadence[pond_id]["unchanged_successive_fraction"] = float(
            group[cols].eq(group[cols].shift()).all(axis=1).mean()) if cols else None
    report = {"dataset_id": dataset_id, "input_rows": len(frame), "accepted_rows": len(accepted),
              "quarantined_rows": len(rejected), "invalid_timestamps": int(invalid_time.sum()),
              "conflicting_timestamp_rows": int(conflicting.sum()), "exact_duplicates": int(duplicate.sum()),
              "has_time_column": has_time, "has_pond_column": pond_col is not None,
              "timezone_counts": out.timezone_status.value_counts().to_dict(), "metrics": stats,
              "other_columns_excluded": [str(c) for c in frame.columns if c not in selected.values()],
              "series": cadence, "training_approved": False}
    assert len(accepted) + len(rejected) == len(frame)
    return accepted, rejected, report


def hourly_observations(clean):
    metrics = [c for c in METRICS if c in clean]
    pieces = []
    for pond, group in clean[clean.timestamp_local.notna()].groupby("pond_id"):
        explicit = group.timestamp_utc.notna().all()
        if explicit:
            group = group.copy()
            group["timestamp_local"] = group.timestamp_utc.dt.tz_localize(None)
        group = group.set_index("timestamp_local").sort_index()
        if len(group) >= 2 and group.index.to_series().diff().median() > pd.Timedelta(hours=1):
            continue
        # [00:00, 01:00) is available at 01:00, never at 00:00.
        bins = group[metrics].resample("1h", closed="left", label="right")
        result = bins.mean()
        result["observation_count"] = group.source_row.resample("1h", closed="left", label="right").count()
        for metric in metrics:
            result[metric + "_count"] = bins[metric].count()
        result["pond_id"] = pond
        result["timezone_status"] = "UTC" if explicit else "source_wall_clock_no_utc_conversion"
        pieces.append(result.reset_index())
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def time_splits(frame):
    result = frame.copy()
    result["split"] = "insufficient_history"
    if "observation_count" in result:
        result.loc[result.observation_count.eq(0), "split"] = "gap"
    for _, group in result.groupby("pond_id"):
        group = group[group.split.ne("gap")]
        unique = np.sort(group.timestamp_local.dropna().unique())
        if len(unique) < 3:
            continue
        a = min(max(1, int(len(unique) * .7)), len(unique) - 2)
        b = min(max(a + 1, int(len(unique) * .85)), len(unique) - 1)
        for name, times in [("train", unique[:a]), ("validation", unique[a:b]), ("test", unique[b:])]:
            result.loc[group.index[group.timestamp_local.isin(times)], "split"] = name
    return result


def spreadsheet_tables(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook:
            # Compilation: split on actual header rows, not workbook dimensions.
            if "Shrimp water sensor" in path.name:
                header, rows, start, number = None, [], 0, 0
                for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                    vals = list(values)
                    is_marker = vals and isinstance(vals[0], str) and vals[0].startswith("Dataset-")
                    is_header = sum(metric_name(v) is not None for v in vals if v is not None) >= 2
                    if is_marker or is_header:
                        if header is not None and rows:
                            yield f"section_{number}", pd.DataFrame(rows, columns=header), start
                        rows, header = [], None
                        if is_header:
                            number += 1
                            width = max(i + 1 for i, v in enumerate(vals) if v is not None)
                            header = [str(v) if v is not None else f"unnamed_{i}" for i, v in enumerate(vals[:width])]
                            start = row_number + 1
                    elif header is not None:
                        # Retain blanks so spreadsheet source_row stays exact.
                        rows.append((vals + [None] * len(header))[:len(header)])
                if header is not None and rows:
                    yield f"section_{number}", pd.DataFrame(rows, columns=header), start
            elif "cure4aqua" in path.as_posix():
                rows = list(sheet.iter_rows(values_only=True))
                metric, long = None, []
                for i, row in enumerate(rows, 1):
                    first = row[0] if row else None
                    if isinstance(first, str) and "(" in first:
                        metric = first
                    if isinstance(first, datetime) and metric:
                        for tank, value in zip(["G01", "G02", "G03", "G04"], row[1:5]):
                            long.append({"source_row": i, "tank_id": tank, "date": first,
                                         "parameter_and_unit": metric, "value": value})
                yield "long_measurements", pd.DataFrame(long), 1
            else:
                rows = sheet.values
                header = list(next(rows))
                frame = pd.DataFrame(rows)
                width = max(len(header), len(frame.columns))
                frame = frame.reindex(columns=range(width))
                header.extend([None] * (width - len(header)))
                frame.columns = [str(value) if value is not None else f"unnamed_{i}"
                                 for i, value in enumerate(header)]
                yield token(sheet.title), frame, 2
    finally:
        workbook.close()


def run(root, output):
    if output.exists():
        raise FileExistsError(f"Use a new --output directory; refusing to overwrite {output}")
    output.mkdir(parents=True)
    files, reports = [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".xlsx", ".zip"}:
            continue
        if "processed" in path.relative_to(root).parts or output.resolve() in path.resolve().parents:
            continue
        relative = path.relative_to(root).as_posix()
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
        print("Processing", relative, flush=True)
        dataset = re.sub(r"[^a-zA-Z0-9]+", "_", str(path.relative_to(root).with_suffix("")))
        if path.suffix == ".csv":
            tables = [("data", pd.read_csv(path, low_memory=False), 2)]
        elif path.suffix == ".xlsx":
            tables = spreadsheet_tables(path)
        else:
            with zipfile.ZipFile(path) as archive:
                tables = [(token(n), pd.read_csv(archive.open(n), low_memory=False), 2)
                          for n in archive.namelist() if n.endswith(".csv")]
        for name, frame, row_start in tables:
            folder = output / dataset / name
            folder.mkdir(parents=True)
            if name == "long_measurements":
                numeric = pd.to_numeric(frame["value"], errors="coerce")
                frame["quality_flag"] = np.where(frame["value"].notna() & numeric.isna(), "nonnumeric", "")
                frame["value_numeric"] = numeric.mask(~np.isfinite(numeric))
                frame.to_csv(folder / "measurements_long.csv.gz", index=False)
                reports.append({"dataset_id": dataset + "/" + name, "input_rows": len(frame),
                                "classification": "long_measurements_heterogeneous_units",
                                "parameters": frame.parameter_and_unit.value_counts().to_dict(),
                                "missing_numeric_values": int(frame.value_numeric.isna().sum()),
                                "zero_values_require_review": int(frame.value_numeric.eq(0).sum()),
                                "training_approved": False})
                continue
            if not any(metric_name(c) for c in frame.columns):
                frame.to_csv(folder / "reference_table.csv.gz", index=False)
                reports.append({"dataset_id": dataset + "/" + name, "input_rows": len(frame),
                                "classification": "reference_or_events_not_forecast_series", "training_approved": False})
                continue
            clean, quarantine, report = clean_frame(frame, dataset, row_start)
            report["table"] = name
            report["source_sha256"] = digest
            report["source_file"] = relative
            clean.to_csv(folder / "cleaned.csv.gz", index=False)
            quarantine.to_csv(folder / "quarantine.csv.gz", index=False)
            hourly = hourly_observations(clean)
            if not hourly.empty:
                time_splits(hourly).to_csv(folder / "hourly_candidate.csv.gz", index=False)
            report["hourly_candidate_rows"] = len(hourly)
            report["hourly_populated_bins"] = int(hourly.observation_count.gt(0).sum()) if not hourly.empty else 0
            (folder / "quality.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
            reports.append(report)
    summary = {"policy_version": 1, "raw_files": files, "tables": reports,
               "notes": ["No interpolation, scaling, synthetic samples or automatic unit conversion.",
                         "Hourly means are labeled at bin END; counts expose sparse/empty bins.",
                         "Chronological split suggestions are not feature windows: all future labels must stay within their split.",
                         "Unseen-pond evaluation and provenance approval remain separate prerequisites."]}
    (output / "manifest.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print("Saved", output / "manifest.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/audit-v1"))
    args = parser.parse_args()
    run(args.root, args.output)
