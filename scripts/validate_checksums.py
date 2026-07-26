"""Validate every locally present input recorded in the provenance manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "provenance_checksums.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = manifest if isinstance(manifest, list) else manifest.get("files", manifest.get("inputs", []))
    if not isinstance(records, list):
        raise ValueError("Checksum manifest must contain a 'files' or 'inputs' list")
    checked = 0
    for record in records:
        path = ROOT / record["path"]
        if not path.exists():
            if record.get("required", True):
                raise FileNotFoundError(path)
            continue
        expected = record.get("sha256") or record.get("checksum")
        if expected and sha256(path) != expected.removeprefix("sha256:"):
            raise AssertionError(f"Checksum mismatch: {record['path']}")
        checked += 1
    if not checked:
        raise AssertionError("No provenance inputs were checked")
    print(f"Validated {checked} input files")


if __name__ == "__main__":
    main()
