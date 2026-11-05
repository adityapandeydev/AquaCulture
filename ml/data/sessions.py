"""Source-evidenced Oman timestamps and candidate continuity inventory.

This is a timestamp/row-lineage sidecar, not a recalibrated measurement release.
"""
import argparse
import hashlib
import json
from datetime import timedelta, timezone
from pathlib import Path

import pandas as pd

from .prepare import clean_frame


def documented_oman_utc(values):
    text = values.astype(str)
    explicit = text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    result = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    result.loc[explicit] = pd.to_datetime(text.loc[explicit], format="mixed", errors="coerce", utc=True)
    naive = pd.to_datetime(text.loc[~explicit], format="mixed", errors="coerce")
    result.loc[~explicit] = naive.dt.tz_localize(timezone(timedelta(hours=4))).dt.tz_convert("UTC")
    return result


def session_rows(clean, recording, source_hash, gap_seconds=3600):
    pieces = []
    for device, group in clean[clean.timestamp_local.notna()].groupby("pond_id"):
        group = group.sort_values(["timestamp_local", "source_row"]).copy()
        gaps = group.timestamp_local.diff().dt.total_seconds()
        group["continuity_number"] = (gaps.isna() | gaps.gt(gap_seconds)).cumsum()
        for _, segment in group.groupby("continuity_number"):
            segment = segment.copy()
            identity = f"{source_hash}|{recording}|{device}|{segment.timestamp_local.iloc[0].isoformat()}|gap={gap_seconds}"
            segment["session_id"] = "oman-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            segment["session_status"] = "candidate_continuity_group"
            segment["timestamp_utc"] = documented_oman_utc(segment.timestamp_local)
            segment["time_basis"] = "source_documented_offset"
            segment["timezone_evidence_id"] = "oman-pinned-data-dictionary-sections-1.1-1.2"
            segment["recording"] = recording
            segment["training_approved"] = False
            pieces.append(segment)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def run(root, output):
    if output.exists():
        raise FileExistsError(output)
    dictionary = (root / "docs/data_dictionary.md").read_text(encoding="utf-8")
    if "GMT+4" not in dictionary:
        raise ValueError("Expected source timezone evidence is absent")
    summary = {"policy_version": "oman-session-v1", "gap_threshold_seconds": 3600,
               "timezone_evidence_sha256": hashlib.sha256(dictionary.encode()).hexdigest(),
               "physical_session_identity_verified": False, "training_approved": False, "recordings": {}}
    output.mkdir(parents=True)
    all_inventory = []
    for recording, filename, start, end in [
            ("offline", "raw_readings.csv", "2026-03-26", "2026-04-02"),
            ("live", "raw_readings_new.csv", "2026-04-01", "2026-04-11")]:
        path = root / "data/raw" / recording / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        raw = pd.read_csv(path)
        clean, rejected, report = clean_frame(raw, "oman_" + recording)
        original_time = pd.to_datetime(raw.timestamp, errors="coerce")
        backwards = original_time.diff().dt.total_seconds().lt(0)
        positions = set(raw.index[backwards]) | {i - 1 for i in raw.index[backwards] if i > 0}
        review_rows = {i + 2 for i in positions}
        clock = pd.DataFrame({"source_row": range(2, len(raw) + 2), "timestamp_original": raw.timestamp,
                              "adjacent_to_backward_source_step": [i + 2 in review_rows for i in raw.index]})
        clock[clock.adjacent_to_backward_source_step].to_csv(output / f"{recording}_ordering_review.csv", index=False)
        in_period = clean.timestamp_local.ge(pd.Timestamp(start)) & clean.timestamp_local.lt(pd.Timestamp(end))
        outside = clean[~in_period].copy()
        outside["exclusion_reason"] = "outside_documented_recording_period"
        excluded = pd.concat([rejected.assign(exclusion_reason="timestamp_or_measurement_conflict"), outside], ignore_index=True)
        eligible = clean[in_period].copy()
        eligible["ordering_review"] = eligible.source_row.isin(review_rows)
        mapped = session_rows(eligible, recording, digest)
        if len(mapped):
            mapped["model_use"] = "candidate_pending_quality_and_partition_checks"
            affected = mapped.groupby("session_id").ordering_review.transform("any")
            mapped.loc[affected, "model_use"] = "excluded_pending_ordering_review"
        if len(mapped) + len(excluded) != len(raw):
            raise ValueError("Source row accounting failed")
        identity_columns = ["source_row", "pond_id", "timestamp_original", "timestamp_local", "timestamp_utc",
                            "session_id", "session_status", "time_basis", "timezone_evidence_id", "recording",
                            "ordering_review", "model_use", "training_approved"]
        mapped[identity_columns].to_csv(output / f"{recording}_timestamp_rows.csv.gz", index=False)
        excluded.to_csv(output / f"{recording}_excluded_rows.csv.gz", index=False)
        groups = []
        for session, group in mapped.groupby("session_id"):
            delta = group.timestamp_utc.sort_values().diff().dt.total_seconds().dropna()
            groups.append({"session_id": session, "session_status": "candidate_continuity_group",
                "recording": recording, "source_sha256": digest, "device_recorded": "node_001",
                "site_id": None, "pond_id": None, "species": "Nile tilapia (publisher-declared)",
                "environment": "pond (publisher-declared)" if recording == "offline" else "controlled 180 L tank (publisher-declared)",
                "rows": len(group), "start_utc": group.timestamp_utc.min().isoformat(), "end_utc": group.timestamp_utc.max().isoformat(),
                "source_row_min": int(group.source_row.min()), "source_row_max": int(group.source_row.max()),
                "median_interval_seconds": float(delta.median()) if len(delta) else None,
                "max_gap_seconds": float(delta.max()) if len(delta) else None,
                "gaps_over_60_seconds": int(delta.gt(60).sum()),
                "ordering_review_rows": int(group.ordering_review.sum()),
                "model_use": group.model_use.iloc[0],
                "lineage_group_id": "oman_single_study_unverified_site_independence",
                "training_approved": False})
        all_inventory.extend(groups)
        summary["recordings"][recording] = {"source_sha256": digest, "raw_rows": len(raw), "mapped_rows": len(mapped),
            "excluded_rows": len(excluded), "candidate_groups": len(groups),
            "mapped_ordering_review_rows": int(mapped.ordering_review.sum()),
            "source_backward_steps": int(backwards.sum()),
            "gap_sensitivity_group_counts": {str(gap): int(session_rows(eligible, recording, digest, gap).session_id.nunique())
                                             for gap in [60, 300, 3600]},
            "cleaning": report}
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Raw source changed")
    summary["session_inventory"] = all_inventory
    (output / "inventory.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary["recordings"], indent=2)[:2500])
    print("Saved", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets/external/oman_tilapia"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/oman-sessions-2026-11-05"))
    args = parser.parse_args()
    run(args.root, args.output)
