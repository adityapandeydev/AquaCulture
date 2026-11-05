"""Reproduce compilation overlaps; define limited partition-claim checks.

This does not build train/test partitions or establish physical-site independence.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


CORE = ["nitrate", "ph", "ammonia", "temperature", "do", "turbidity"]


def overlap_evidence(left, right, columns):
    # Compare numeric vectors, not metadata or physical provenance. Missing
    # measurements are excluded so shared nulls cannot create false overlap.
    a = left[columns].apply(pd.to_numeric, errors="coerce").dropna().round(6)
    b = right[columns].apply(pd.to_numeric, errors="coerce").dropna().round(6)
    ca = Counter(map(tuple, a.to_numpy().tolist()))
    cb = Counter(map(tuple, b.to_numpy().tolist()))
    common = ca.keys() & cb.keys()
    return {"left_rows": len(left), "right_rows": len(right),
            "left_complete_vectors": len(a), "right_complete_vectors": len(b),
            "left_unique_vectors": len(ca), "right_unique_vectors": len(cb),
            "shared_unique_vectors": len(common),
            "shared_rows_multiset": sum(min(ca[key], cb[key]) for key in common),
            "left_complete_vector_multiset_contained": all(n <= cb[key] for key, n in ca.items()),
            "basis": "Complete numeric six-channel vectors rounded to six decimals; excludes timestamps, station IDs and labels; does not prove collection origin."}


def validate_partition_claim(development_groups, test_groups, claim):
    if claim not in {"independent_site", "chronological_within_study"}:
        raise ValueError("Unknown evaluation claim")
    if claim == "independent_site" and set(development_groups) & set(test_groups):
        raise ValueError("Shared or unverified-independent lineage cannot establish an independent-site holdout")


def run(prepared, output):
    if output.exists():
        raise FileExistsError(output)
    pairs = [("section_2", "O1D1_Fish_Ponds/data"), ("section_3", "O1D1_Ponds/data"),
             ("section_4", "O1D1_Ponds1/data")]
    result = []
    for section, other in pairs:
        left = prepared / "Copy_of_Shrimp_water_sensor_data" / section / "cleaned.csv.gz"
        right = prepared / other / "cleaned.csv.gz"
        a, b = pd.read_csv(left, low_memory=False), pd.read_csv(right, low_memory=False)
        evidence = overlap_evidence(a, b, CORE)
        evidence.update({"left_table": str(left), "right_table": str(right),
                         "left_artifact_sha256": hashlib.sha256(left.read_bytes()).hexdigest(),
                         "right_artifact_sha256": hashlib.sha256(right.read_bytes()).hexdigest()})
        result.append(evidence)
    output.mkdir(parents=True)
    (output / "compilation_overlap.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=Path("Datasets/processed/2026-11-05"))
    parser.add_argument("--output", type=Path, default=Path("Datasets/processed/lineage-review-2026-11-05"))
    args = parser.parse_args()
    run(args.prepared, args.output)
