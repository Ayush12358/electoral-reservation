## Updated review

### Verdict

**Ready to publish as version 0.1 working paper or preprint.**
**Not yet ready for submission to a strong peer-reviewed journal.**

The repository now contains the compressed TCPD inputs, corrected core
specification, refreshed results, manuscript consistency audit, deterministic
release archive, and prepared arXiv and Zenodo submission packages.

## Resolved issues

### Data availability and provenance

* The GE, AE, and GA TCPD inputs are tracked as compressed archives.
* Extended-analysis paths read the `.csv.gz` files directly.
* Provenance, byte sizes, and SHA-256 checksums are recorded.
* `scripts/validate_checksums.py` validates all recorded inputs.

### Vote-share denominator

Constituency totals are calculated from every valid candidate vote record before
the analysis is restricted to candidates with usable gender information.

### 2004 baseline leakage

The contemporaneous 2004 party-state expectation is now leave-one-out. Candidates
in singleton party-state groups are excluded because no within-group
leave-one-out expectation exists.

### Education missingness

Missing education is no longer coded as illiteracy. The primary controlled
specification uses median imputation and an `EDU_MISSING` indicator.

### Manuscript framing and factual accuracy

* The paper describes a candidacy representation gap and evidence consistent
  with party gatekeeping rather than claiming to identify nomination
  discrimination among unobserved aspirants.
* The historical table reports 59 women winners (10.9%) in 2009 and 62 (11.4%)
  in 2014.
* Unsourced party-specific winner ranges were removed.
* Repository links in `CITATION.cff` point to
  `https://github.com/Ayush12358/electoral-reservation`.

### Publication packages

* The repository has an MIT code license.
* `arxiv/` and `release/electoral_reservation_arxiv_v0.1.zip` provide a
  self-contained PDFLaTeX submission package.
* `zenodo/` and `release/zenodo_submission_v0.1.0.zip` provide a working-paper
  PDF, source, raw-data-free replication archive, metadata, and checksums.
* The manuscript consistency audit verifies eight registered quantitative
  claims.
* The frozen replication archive has been rebuilt and verified.

## Verification policy

GitHub Actions is intentionally not used. The workflow was removed because the
current release has already been validated and the repository owner does not
want recurring CI runs.

Verification remains reproducible through committed local commands:

```text
python scripts/validate_checksums.py
python experiments/analysis_with_controls.py
python experiments/manuscript_consistency_audit.py
python scripts/build_release.py
python experiments/verify_release.py
python scripts/build_arxiv_package.py
python scripts/build_zenodo_package.py
```

The arXiv ZIP was compiled twice with PDFLaTeX from a clean temporary extraction.
The Zenodo payload checksums and bundle membership were also independently
validated locally. This is credible release evidence, but it is not continuous
clean-clone verification.

## Remaining work

### Before public release

* Confirm that redistribution of the tracked TCPD archives is consistent with
  the provider's current terms.
* Publish the Zenodo record and add its assigned DOI to the paper, README, and
  citation metadata.
* If arXiv endorsement is obtained, publish the arXiv version and add its
  identifier to the repository and Zenodo record.

### Before journal submission

* Add dependence-robust uncertainty appropriate to repeated party,
  constituency, election, and state structure.
* Re-run the full robustness and extended-analysis suite from the corrected
  specification, not only the refreshed core outputs.
* Complete human adjudication of unresolved fuzzy entity links.
* Strengthen convergent validation using outcomes such as appointments,
  leadership roles, or expert assessments.
* Check the target journal's preprint and repository-license policies.

## Revised scorecard

| Area | Assessment |
|---|---|
| Conceptual contribution | Strong |
| Transparency about limitations | Strong |
| Repository organization | Strong |
| Data availability | Strong, subject to redistribution confirmation |
| Reproducibility design | Good; locally verified, no recurring CI |
| Measurement validity | Preliminary |
| Causal identification | Not claimed and not established |
| Statistical specification | Core issues corrected; journal extensions remain |
| Manuscript factual accuracy | Mandatory corrections completed |
| Working-paper readiness | **Yes** |
| Journal readiness | **No, further validation and uncertainty work required** |

## Recommended publication decision

**Publish as version 0.1 working paper** after confirming TCPD redistribution
terms and completing the chosen repository deposit. Treat arXiv endorsement as
optional: Zenodo can provide the immediate public record and DOI without
endorsement.
