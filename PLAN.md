# Remaining Revision Plan

This file tracks only work that is still open. Completed implementation details
are recorded in `experiments/results/plan_implementation_manifest.json`, and the
current manuscript and reproducibility package are the authoritative baseline.

## Open tasks

| Priority | Remaining revision | Status |
|---|---|---|
| **P0** | Add convergent validation beyond the subsequent-election criterion | Open: cabinet, leadership, committee, or expert-outcome data are not available locally |
| **P0** | Complete exit-test calibration and define distributional breadth | Partial: threshold/persistence sensitivity is complete; a legal or decision-theoretic derivation and a within-group breadth benchmark remain open |
| **P1** | Complete the external claim/source aggregation audit | Partial: major numerical and official-source audits are complete; broader aggregation remains open |
| **P2** | Adjudicate fuzzy matches if they materially affect conclusions | Open: 444-link review queue and consumer are ready; human decisions remain |
| **P2** | Deposit the frozen package with Zenodo and obtain a DOI | Open: local archive and deposition metadata are ready |

## 1. Convergent validation

The TCPD subsequent-election vote-share and winning analyses provide a criterion
outcome distinct from 2009 renomination, but they are selected among recontesters
and provide little incremental signal. Add at least one outcome that is related to
candidate contribution but not mechanically derived from the residual or future
nomination, preferably cabinet appointment, parliamentary leadership, committee
assignment, or an independent expert assessment.

For any added outcome:

- pre-specify the expected relationship and why it is a distinct construct;
- report missingness and selection into the validation sample;
- compare baseline and residual-inclusive specifications;
- use robustness checks appropriate to the outcome; and
- separate predictive, incremental, and convergent validity.

If no suitable outcome data can be assembled, retain the current narrowed claims
and state that validation remains preliminary.

## 2. Exit-test calibration and breadth

The threshold/persistence sensitivity artifact already tests 100 parity and
persistence combinations. The remaining work is to supply either a defensible
legal or decision-theoretic derivation of the primary values, or a pre-specified
institutional calibration that explains why the five conditions are jointly
required.

The distributional-breadth condition also needs an observable within-group
attribute and benchmark. Until that exists, report the exit test only as an
empirical diagnostic under stated design choices; do not treat an unobserved
breadth condition as passed or make a normative recommendation about removing
institutional correction.

Relevant artifacts:

- `experiments/exit_test_sensitivity.py`
- `experiments/results/exit_test_sensitivity.csv`
- `experiments/results/exit_test_sensitivity_manifest.json`

## 3. External claim/source aggregation

Extend the existing official-source audit to every remaining time-sensitive or
external substantive claim in `PAPER.md`. For each claim, record the source,
date/snapshot, denominator, and whether the statement is official, research-based,
or interpretive. In particular, keep ADR ticket and aggregation claims explicitly
scoped to their published universe, and preserve the legal distinction between the
106th Amendment being in force and its seat-reservation provisions not yet being
operative.

Artifact: `outputs/external_claims_source_audit_2026-07-17.md`.

## 4. Fuzzy-link adjudication

Review `experiments/results/entity_resolution_adjudication_template.csv`. For each
of the 444 links, enter `accept` or `reject`, an evidence reference, reviewer, UTC
timestamp, and notes. Then run:

```bash
python experiments/apply_entity_resolution_adjudication.py --require-complete
```

The exact-match sample remains the main analysis until decisions are complete.
After review, inspect `fuzzy_match_adjudicated_summary.csv`; change the main sample
only if the adjudicated links materially alter the substantive conclusion.

## 5. DOI deposition

The local archive and metadata are prepared. Before submission, run:

```bash
python scripts/build_release.py
python experiments/verify_release.py
```

Upload `release/electoral_reservation_frozen_2026-07-17.tar.gz` and the associated
metadata to Zenodo, then record the issued DOI in `CITATION.cff`, `README.md`, and
the release documentation. Verify that the DOI resolves to the same frozen archive
checksum.

## Definition of completion

The remaining revision is complete when:

- at least one convergent outcome is analyzed, or the preliminary-validation
  limitation is explicitly retained;
- the exit-test primary values and breadth condition are justified or clearly
  labeled as uncalibrated diagnostics;
- external claims have source, date, and denominator records;
- all fuzzy links have auditable human decisions, or remain explicitly excluded;
- the frozen archive is deposited and has a DOI; and
- `PAPER.md`, saved outputs, and the release manifest remain internally consistent.

Bayesian uncertainty propagation and new exploratory estimators remain optional
unless a reviewer identifies a specific validity concern that requires them.
