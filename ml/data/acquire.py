"""Download only reviewed public files from docs/data/sources.json.

Existing bytes must match expected SHA-256; changed raw data is never overwritten.
No archives are extracted and no downloaded code is executed.
"""
import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def acquire(catalog, root):
    entries = json.loads(catalog.read_text(encoding="utf-8"))["sources"]
    manifest = []
    for source in entries:
        for item in source.get("downloads", []):
            target = root / item["relative_path"]
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError("Download path escapes dataset directory")
            expected = item["sha256"]
            if target.exists():
                data = target.read_bytes()
            else:
                with urllib.request.urlopen(item["url"], timeout=60) as response:
                    data = response.read(25 * 1024 * 1024 + 1)
                if len(data) > 25 * 1024 * 1024:
                    raise ValueError("File exceeds reviewed download size limit")
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                raise ValueError(f"Checksum mismatch: {target}")
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
            manifest.append({"source_id": source["id"], "path": str(target),
                             "url": item["url"], "bytes": len(data), "sha256": actual})
            print("Verified", target, flush=True)
    result = {"verified_at_utc": datetime.now(timezone.utc).isoformat(), "files": manifest}
    root.mkdir(parents=True, exist_ok=True)
    (root / "verified_downloads.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("docs/data/sources.json"))
    parser.add_argument("--root", type=Path, default=Path("Datasets/external"))
    args = parser.parse_args()
    acquire(args.catalog, args.root)
