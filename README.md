# Electoral Reservation Measurement Study

This repository contains the code and artifacts for a measurement/validation study of candidate capability and women's representation in Indian elections.

## Core idea
- Measured electoral contribution is operationalized as a party-normalized vote-share residual, treated as an imperfect proxy for latent capability.
- The main empirical question is whether nomination, seat quality, or vote conversion drives gender gaps.
- The paper is a measurement/validation contribution, not a causal identification design.

## Data layout
- `data/raw/`: core Lok Sabha analysis (2004, 2009)
- `data/TCPD_GE_All_States_2026-7-26.csv.gz`: TCPD Lok Sabha extension
- `data/TCPD_AE_All_States_2026-7-26.csv.gz`: TCPD Vidhan Sabha replication
- `data/TCPD_GA_All_States_2026-7-26.csv.gz`: TCPD general-election assembly-segment data

## Obtaining the TCPD data
The TCPD Indian Elections Dataset was downloaded from [Lok Dhaba](https://lokdhaba.ashoka.edu.in/),
the Trivedi Centre for Political Data's election-data portal at Ashoka University. The repository
contains the gzip-compressed all-states exports downloaded on July 26, 2026:

- `data/TCPD_GE_All_States_2026-7-26.csv.gz`
- `data/TCPD_AE_All_States_2026-7-26.csv.gz`
- `data/TCPD_GA_All_States_2026-7-26.csv.gz`

Pandas reads these archives directly; do not extract them. The generated
`experiments/results/vidhansabha_analysis.csv` remains excluded because its uncompressed size
exceeds GitHub's recommended limit. Expected archive sizes and SHA-256 checksums are recorded in
`data/provenance_checksums.json`.

The Lok Dhaba codebook permits no-cost, non-commercial reuse subject to its terms and attribution
requirements. Use of the data acknowledges those terms. Users must not imply TCPD endorsement;
TCPD provides no warranty and disclaims liability for errors, omissions, or misrepresentations.
Cite the dataset as:

> Agarwal, Ananay, Neelesh Agrawal, Saloni Bhogale, Sudheendra Hangal, Francesca Refsum Jensenius,
> Mohit Kumar, Chinmay Narayan, Basim U Nissa, Priyamvada Trivedi, and Gilles Verniers. 2021.
> "TCPD Indian Elections Data v2.0." Trivedi Centre for Political Data, Ashoka University.

## Dependencies
```bash
pip install -r requirements.txt
```

Or build the lightweight container:
```bash
docker build -t electoral-reservation .
docker run --rm -it -v "$PWD":/workspace electoral-reservation bash
```

## One-command reproduction
```bash
bash scripts/reproduce.sh
```

The launcher selects `python`, `py.exe`, or `python3` automatically. Set `PYTHON_BIN` to override the selection.

Optional knobs:
```bash
FULL_BOOT_N=100 RUN_EXTENDED=1 bash scripts/reproduce.sh
```

## Recommended run order
### Core analysis (2004–2009)
```bash
python experiments/analysis_with_controls.py
python experiments/step1_model_report.py
python experiments/validation_renomination.py
python experiments/heterogeneity.py
python experiments/interaction_model.py
python experiments/sc_st_analysis.py
python experiments/measurement_validation_suite.py
python experiments/fuzzy_match_sensitivity.py
python experiments/bootstrap_uncertainty.py
python experiments/full_pipeline_bootstrap.py --n-boot 100
```

### Extended analysis (TCPD Lok Sabha + Vidhan Sabha)
```bash
python experiments/tcpd_pipeline.py
python experiments/tcpd_expected_vote_sensitivity.py
python experiments/extended_loksabha_analysis.py
python experiments/tcpd_future_performance_validation.py
python experiments/exit_test_sensitivity.py
python experiments/vidhansabha_replication.py
python experiments/manuscript_consistency_audit.py
python experiments/apply_entity_resolution_adjudication.py
python scripts/build_release.py
python experiments/verify_release.py
```

## Outputs
All scripts write CSV/JSON outputs to `experiments/results/`.

### Entity-resolution review
`fuzzy_match_sensitivity.py` writes `entity_resolution_adjudication_template.csv`. Reviewers should enter `accept` or `reject` in `decision`, cite the source used to verify identity in `evidence_reference`, and record their name and UTC review time. Run `apply_entity_resolution_adjudication.py` afterward; it consumes only explicit `accept` decisions, reports pending links, and writes a separate adjudicated sensitivity result. Use `--require-complete` as a release gate once every link has been reviewed. Fuzzy links remain excluded from the main exact-match analysis until adjudicated.

## Current status
- Core manuscript numerics are audited against saved outputs.
- Sampling and full-pipeline bootstrap results are available.
- A local frozen release snapshot is available in `release/`; remaining work is tracked in `PLAN.md`.
- `scripts/build_release.py` creates the archive deterministically; `experiments/verify_release.py` checks its checksum, member count, and required artifacts.
- `CITATION.cff` and `release/zenodo.json` provide DOI deposition metadata; publication still requires an external Zenodo upload.
- Criterion validation, exit-test calibration, state-assembly portability, fuzzy-link sensitivity, and official-source claim audits are implemented.
- Human fuzzy-link adjudication and convergent validation using appointments or expert assessments remain open-data tasks.
