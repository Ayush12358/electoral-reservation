"""Build the deterministic local replication archive and its manifest."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "release"
ARCHIVE = RELEASE_DIR / "electoral_reservation_frozen_2026-07-17.tar.gz"
MANIFEST = RELEASE_DIR / "frozen_snapshot_manifest.json"

TOP_LEVEL = [
    "PAPER.md",
    "PLAN.md",
    "README.md",
    "CITATION.cff",
    "LICENSE",
    "requirements.txt",
    "Dockerfile",
    ".dockerignore",
    ".gitignore",
    "scripts/reproduce.sh",
    "scripts/build_release.py",
    "scripts/validate_checksums.py",
    "data/provenance_checksums.json",
    "outputs/manuscript_consistency_audit.md",
    "outputs/measurement_model_concepts.svg",
    "outputs/external_claims_source_audit_2026-07-17.md",
    "release/arxiv_submission.md",
]


def archive_members() -> list[Path]:
    files = [ROOT / relative for relative in TOP_LEVEL]
    files.extend(sorted((ROOT / "experiments").glob("*.py")))
    files.extend(sorted((ROOT / "experiments" / "results").iterdir()))
    missing = [str(path.relative_to(ROOT)) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required release files missing: {missing}")
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_archive(files: list[Path]) -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as bundle:
                for path in files:
                    arcname = path.relative_to(ROOT).as_posix()
                    info = bundle.gettarinfo(str(path), arcname=arcname)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o644
                    with path.open("rb") as handle:
                        bundle.addfile(info, handle)


def main() -> None:
    files = archive_members()
    write_archive(files)
    members = len(files)
    manifest = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "archive": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
        "archive_sha256": sha256(ARCHIVE),
        "n_members": members,
        "verified_with": "python scripts/build_release.py and experiments/verify_release.py",
        "included_top_level_artifacts": TOP_LEVEL,
        "included_experiment_sources": "All Python files in experiments/ at freeze time, including validation, sensitivity, adjudication, audit, and release-verification scripts.",
        "included_results": "All CSV and JSON result artifacts in experiments/results/ at freeze time.",
        "excluded_note": "Raw data directories are excluded; see data/provenance_checksums.json. The paper is intended for arXiv, with this GitHub repository as its public replication companion.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Built {ARCHIVE.name}: {members} members, SHA-256 {manifest['archive_sha256']}")


if __name__ == "__main__":
    main()
