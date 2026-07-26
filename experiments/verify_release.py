"""Verify the frozen release archive and its deposition metadata."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release" / "frozen_snapshot_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    archive = ROOT / manifest["archive"]
    observed_hash = sha256(archive)
    if observed_hash != manifest["archive_sha256"]:
        raise AssertionError(f"Archive hash mismatch: {observed_hash} != {manifest['archive_sha256']}")

    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getnames()
    if len(members) != manifest["n_members"]:
        raise AssertionError(f"Archive member count mismatch: {len(members)} != {manifest['n_members']}")

    required = manifest["included_top_level_artifacts"] + ["release/arxiv_submission.md"]
    missing = [name for name in required if name not in members]
    if missing:
        raise AssertionError(f"Required archive members missing: {missing}")

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    for marker in ("cff-version: 1.2.0", "title:", "authors:", "version:", "date-released:"):
        if marker not in citation:
            raise AssertionError(f"CITATION.cff missing marker: {marker}")
    arxiv = (ROOT / "release" / "arxiv_submission.md").read_text(encoding="utf-8")
    repository_url = "https://github.com/Ayush12358/electoral-reservation"
    if repository_url not in arxiv or repository_url not in citation:
        raise AssertionError("arXiv checklist and CITATION.cff must name the GitHub repository")
    print(f"Release verified: {archive.name} ({len(members)} members, SHA-256 {observed_hash})")


if __name__ == "__main__":
    main()
