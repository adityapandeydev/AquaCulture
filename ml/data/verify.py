"""Verify a preparation run and report overlapping source measurement vectors."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd

from .prepare import metric_name


def verify(root, output):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["raw_files"]:
        digest = hashlib.sha256()
        with (root / item["path"]).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError("Raw input changed: " + item["path"])
    checked = 0
    for report in manifest["tables"]:
        if "accepted_rows" not in report:
            continue
        if report["input_rows"] != report["accepted_rows"] + report["quarantined_rows"]:
            raise ValueError("Row accounting mismatch: " + report["dataset_id"])
        folder = output / report["dataset_id"] / report["table"]
        for name, key in [("cleaned.csv.gz", "accepted_rows"), ("quarantine.csv.gz", "quarantined_rows")]:
            if len(pd.read_csv(folder / name, low_memory=False)) != report[key]:
                raise ValueError("Saved row count differs: " + str(folder / name))
        hourly_path = folder / "hourly_candidate.csv.gz"
        if not hourly_path.exists():
            continue
        frame = pd.read_csv(hourly_path)
        if frame.duplicated(["pond_id", "timestamp_local"]).any():
            raise ValueError("Duplicate hourly timestamps: " + str(hourly_path))
        if not frame.loc[frame.observation_count.eq(0), "split"].eq("gap").all():
            raise ValueError("Empty bins included in temporal split")
        for _, group in frame[frame.observation_count.gt(0)].groupby("pond_id"):
            ranges = group.groupby("split").timestamp_local.agg(["min", "max"])
            if all(name in ranges.index for name in ["train", "validation", "test"]):
                if not (ranges.loc["train", "max"] < ranges.loc["validation", "min"]
                        and ranges.loc["validation", "max"] < ranges.loc["test", "min"]):
                    raise ValueError("Overlapping chronological splits")
        checked += 1
    metrics = ["temperature", "ph", "do", "turbidity"]
    vectors = {}
    for path in sorted((root / "O1D2").glob("*.csv")):
        frame = pd.read_csv(path, low_memory=False)
        mapping = {column: metric_name(column) for column in frame if metric_name(column) in metrics}
        values = frame[list(mapping)].rename(columns=mapping)[metrics].apply(pd.to_numeric, errors="coerce").round(6)
        vectors[path.name] = set(pd.util.hash_pandas_object(values, index=False))
    overlaps = []
    for left, right in itertools.combinations(vectors, 2):
        shared = len(vectors[left] & vectors[right])
        smaller = min(len(vectors[left]), len(vectors[right]))
        fraction = shared / smaller if smaller else 0
        if fraction > .01:
            overlaps.append({"left": left, "right": right, "shared_unique_water_vectors": shared,
                             "fraction_of_smaller_unique_set": round(fraction, 6)})
    result = {"raw_hashes_verified": len(manifest["raw_files"]), "hourly_tables_verified": checked,
              "row_accounting_verified": True,
              "overlap_method": "Unique unordered temperature/ph/do/turbidity vectors rounded to six decimals. This tests shared values, not shared complete sequences.",
              "aquaponics_pairs_over_one_percent_overlap": overlaps}
    (output / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("Datasets"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/2026-11-05"))
    args = parser.parse_args()
    verify(args.root, args.output)
