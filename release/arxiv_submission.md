# arXiv Submission Checklist

## Publication roles

- arXiv hosts the working paper/preprint.
- GitHub hosts the public code, tracked data inputs, provenance records, and reproducibility artifacts:
  https://github.com/Ayush12358/electoral-reservation

## Repository statement for the arXiv abstract or comments field

Code, data, and replication materials are available at
https://github.com/Ayush12358/electoral-reservation.

## Before submission

- [x] Export `PAPER.md` to an arXiv-compatible PDFLaTeX source bundle.
- [x] Include `references.bib`, the rendered `main.bbl`, and the local figure.
- [x] Confirm the title and author list match `CITATION.cff`.
- [x] Include the GitHub repository URL in the paper and suggested arXiv comments.
- [x] Compile twice from a clean extraction of the upload ZIP.
- [x] Run `python scripts/validate_checksums.py`.
- [x] Run `python experiments/manuscript_consistency_audit.py`.
- [x] Run `python scripts/build_release.py` and `python experiments/verify_release.py`.
- [ ] Create or confirm the submitting author's arXiv account.
- [ ] Obtain `stat.AP` endorsement if arXiv requests it.
- [ ] Choose the manuscript license in the arXiv submission form.
- [ ] Upload the source ZIP and inspect arXiv's generated PDF.

## After submission

- Record the assigned identifier here: `arXiv: pending`.
- Add the arXiv URL and identifier to `README.md`, `PAPER.md`, and `CITATION.cff`.
- Tag the matching GitHub source state as `v0.1.0`.
