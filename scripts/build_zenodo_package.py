"""Build the files and metadata for a Zenodo working-paper deposit."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZENODO = ROOT / "zenodo"
RELEASE = ROOT / "release"
VERSION = "0.1.0"

PAPER_SOURCE = ROOT / "arxiv" / "main.pdf"
TEX_SOURCE = RELEASE / "electoral_reservation_arxiv_v0.1.zip"
REPLICATION_SOURCE = RELEASE / "electoral_reservation_frozen_2026-07-17.tar.gz"

PAPER = ZENODO / f"electoral_capability_working_paper_v{VERSION}.pdf"
TEX = ZENODO / f"electoral_capability_latex_source_v{VERSION}.zip"
REPLICATION = ZENODO / f"electoral_reservation_replication_v{VERSION}.tar.gz"
CHECKSUMS = ZENODO / "SHA256SUMS.txt"
METADATA = ZENODO / "zenodo_metadata.json"
README = ZENODO / "README.md"
BUNDLE = RELEASE / f"zenodo_submission_v{VERSION}.zip"

TITLE = "Electoral Capability, Party Gatekeeping, and the Exit Threshold for Institutional Correction"
REPOSITORY = "https://github.com/Ayush12358/electoral-reservation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    sources = [PAPER_SOURCE, TEX_SOURCE, REPLICATION_SOURCE]
    missing = [str(path.relative_to(ROOT)) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Build the arXiv and frozen releases first: {missing}")

    ZENODO.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PAPER_SOURCE, PAPER)
    shutil.copyfile(TEX_SOURCE, TEX)
    shutil.copyfile(REPLICATION_SOURCE, REPLICATION)

    upload_files = [PAPER, TEX, REPLICATION]
    CHECKSUMS.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in upload_files),
        encoding="ascii",
    )

    metadata = {
        "metadata": {
            "upload_type": "publication",
            "publication_type": "workingpaper",
            "publication_date": "2026-07-26",
            "title": TITLE,
            "creators": [{"name": "Maurya, Ayush"}],
            "description": (
                "<p>Working Paper, Version 0.1. This study develops and validates a "
                "computational measurement framework for decomposing representation "
                "shortfalls into candidacy representation, seat quality, and vote-conversion "
                "stages. It applies a party-normalized electoral-contribution residual to "
                "Indian parliamentary and state-assembly elections and documents the limits "
                "of the measure as a descriptive, non-causal proxy.</p>"
                f"<p>Code, documentation, and reproducibility materials: "
                f'<a href="{REPOSITORY}">{REPOSITORY}</a>.</p>'
            ),
            "version": VERSION,
            "language": "eng",
            # Keep the API draft conservative until the author deliberately
            # chooses an irrevocable license. Change to "open" and add a valid
            # Zenodo license identifier before publishing an open record.
            "access_right": "closed",
            "keywords": [
                "computational social science",
                "statistical measurement",
                "electoral representation",
                "party gatekeeping",
                "women's representation",
                "India",
                "reproducibility",
            ],
            "related_identifiers": [
                {
                    "identifier": REPOSITORY,
                    "relation": "isSupplementedBy",
                    "resource_type": "software",
                }
            ],
            "notes": (
                "The replication archive excludes raw data directories. Third-party election "
                "data remain subject to their providers' terms and are not relicensed by this deposit."
            ),
        }
    }
    METADATA.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    README.write_text(
        f"""# Zenodo submission package

Record type: Publication

Publication type: Working paper

Version: {VERSION}

Creator: Maurya, Ayush

Repository: {REPOSITORY}

## Upload these files individually

- `{PAPER.name}` — preservation and reader copy
- `{TEX.name}` — self-contained LaTeX source
- `{REPLICATION.name}` — code and generated reproducibility artifacts; raw data excluded
- `{CHECKSUMS.name}` — integrity checks

Use `zenodo_metadata.json` to populate the Zenodo form or legacy deposit API.
The JSON is deliberately set to closed access so it cannot silently default to
CC BY. Before publishing an open record, change access to open and select the
intended manuscript license in Zenodo.

## Decisions intentionally left to the author

- Reserve a DOI before publication if it should appear inside the PDF.
- Choose the manuscript license after checking intended journal policies.
- Add an ORCID and affiliation if applicable.
- Add the arXiv identifier later if endorsement and submission succeed.

Do not add the compressed TCPD or other raw election datasets to this deposit.
Publishing a Zenodo record is permanent; preview every field and file first.
""",
        encoding="utf-8",
    )

    bundle_files = upload_files + [CHECKSUMS, METADATA, README]
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_files:
            archive.write(path, path.name)
    print(f"Built {BUNDLE.relative_to(ROOT)} with {len(bundle_files)} files")


if __name__ == "__main__":
    main()
