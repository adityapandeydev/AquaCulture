"""Non-destructive channel diagnostics for Oman candidate sessions.

Review thresholds are diagnostic heuristics, not biological limits or proof of faults.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


CHANNELS = {"do": "do_mgL", "temperature": "temp_c", "ph": "ph"}
RATE_REVIEW = {"do": 2.0, "temperature": 1.0, "ph": .5}  # source units/minute


def valid_spans(valid, times, max_gap_seconds=60):
    gap = times.diff().dt.total_seconds()
    breaks = ~valid | ~valid.shift(fill_value=False) | gap.gt(max_gap_seconds) | gap.le(0)
    groups = breaks.cumsum()
    spans = []
    for _, index in valid[valid].groupby(groups[valid]).groups.items():
        segment = times.loc[index]
        spans.append({"rows": len(index), "start_utc": segment.iloc[0].isoformat(),
                      "end_utc": segment.iloc[-1].isoformat(),
                      "duration_seconds": (segment.iloc[-1] - segment.iloc[0]).total_seconds()})
    return spans


def inspect_channel(values, times, parameter):
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric.notna() & np.isfinite(numeric)
    low, high = {"do": (0, np.inf), "temperature": (-3, 60), "ph": (0, 14)}[parameter]
    valid = finite & numeric.ge(low) & numeric.le(high)
    gap = times.diff().dt.total_seconds()
    comparable = valid & valid.shift(fill_value=False) & gap.ge(5) & gap.le(60)
    rate = numeric.diff().abs().div(gap).mul(60).where(comparable)
    equal = valid & valid.shift(fill_value=False) & numeric.eq(numeric.shift()) & gap.gt(0) & gap.le(60)
    groups = (~equal).cumsum()
    plateaus = []
    for _, index in numeric[valid].groupby(groups[valid]).groups.items():
        duration = (times.loc[index[-1]] - times.loc[index[0]]).total_seconds()
        plateaus.append((duration, index))
    plateau_review = pd.Series(False, index=values.index)
    for duration, index in plateaus:
        if duration >= 300 and len(index) >= 3:
            plateau_review.loc[index] = True
    flags = pd.DataFrame({"invalid": ~valid, "zero_review": valid & numeric.eq(0) if parameter == "do" else False,
                          "rapid_change_review": rate.gt(RATE_REVIEW[parameter]),
                          "exact_plateau_review": plateau_review})
    unique = np.sort(numeric[valid].unique())
    steps = np.diff(unique)
    report = {"rows": len(values), "invalid_rows": int((~valid).sum()),
              "zero_rows": int((finite & numeric.eq(0)).sum()),
              "rapid_change_review_rows": int(flags.rapid_change_review.sum()),
              "plateau_review_rows": int(plateau_review.sum()),
              "longest_exact_plateau_seconds": max((d for d, _ in plateaus), default=0),
              "unique_valid_values": len(unique),
              "smallest_observed_unique_increment": float(steps[steps > 0].min()) if np.any(steps > 0) else None,
              "valid_value_quantiles": {str(q): float(numeric[valid].quantile(q)) for q in [0, .01, .5, .99, 1]} if valid.any() else {},
              "absolute_rate_quantiles_per_minute": {str(q): float(rate.dropna().quantile(q)) for q in [.5, .95, .99, 1]} if rate.notna().any() else {},
              "saturation_status": "unknown_without_instrument_range_and_resolution_evidence"}
    return flags, report


def run(root, sessions, output):
    if output.exists():
        raise FileExistsError(output)
    inventory = json.loads((sessions / "inventory.json").read_text())
    result = {"policy_version": "oman-quality-diagnostics-v1", "training_approved": False,
              "rate_review_units_per_minute": RATE_REVIEW,
              "threshold_note": "Diagnostic sensitivity choices, not learned cutoffs, calibrated fault classifiers or automatic rejection rules.",
              "sessions": []}
    output.mkdir(parents=True)
    all_flags, spans_out = [], []
    for recording, filename in [("offline", "raw_readings.csv"), ("live", "raw_readings_new.csv")]:
        path = root / "data/raw" / recording / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != inventory["recordings"][recording]["source_sha256"]:
            raise ValueError("Session/source hash mismatch")
        raw = pd.read_csv(path); raw["source_row"] = np.arange(2, len(raw) + 2)
        rows = pd.read_csv(sessions / f"{recording}_timestamp_rows.csv.gz")
        rows["timestamp_utc"] = pd.to_datetime(rows.timestamp_utc, utc=True)
        rows = rows.merge(raw[["source_row"] + list(CHANNELS.values())], on="source_row", validate="one_to_one")
        for session, group in rows.groupby("session_id"):
            group = group.sort_values("timestamp_utc").reset_index(drop=True)
            summary = {"session_id": session, "recording": recording, "rows": len(group),
                       "model_use": group.model_use.iloc[0], "channels": {}, "configurations": {}}
            flags = group[["source_row", "timestamp_utc", "session_id", "model_use"]].copy()
            valid = {}
            for parameter, column in CHANNELS.items():
                channel_flags, report = inspect_channel(group[column], group.timestamp_utc, parameter)
                summary["channels"][parameter] = report
                valid[parameter] = ~channel_flags.invalid
                for reason in channel_flags:
                    flags[parameter + "_" + reason] = channel_flags[reason]
            for name, mask in [("do_only", valid["do"]),
                               ("do_temperature_ph", valid["do"] & valid["temperature"] & valid["ph"])]:
                spans = valid_spans(mask, group.timestamp_utc)
                for span in spans:
                    spans_out.append({"session_id": session, "configuration": name, **span})
                summary["configurations"][name] = {"screening_valid_rows": int(mask.sum()),
                    "fraction": float(mask.mean()), "span_count_with_max_60s_gap": len(spans),
                    "longest_span_hours": max((s["duration_seconds"] for s in spans), default=0) / 3600}
            all_flags.append(flags);result["sessions"].append(summary)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Source changed during diagnostics")
    pd.concat(all_flags, ignore_index=True).to_csv(output / "row_quality_flags.csv.gz", index=False)
    pd.DataFrame(spans_out).to_csv(output / "screening_valid_spans.csv", index=False)
    (output / "quality.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Audited", len(result["sessions"]), "sessions; saved", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets/external/oman_tilapia"))
    parser.add_argument("--sessions", type=Path, default=Path("Datasets/processed/oman-sessions-2026-11-05-v2"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/oman-quality-2026-11-05"))
    args = parser.parse_args()
    run(args.root, args.sessions, args.output)
