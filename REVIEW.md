## Open review items

### Current verdict

**Version 0.1.0 is publicly archived, but it should not be treated as the final
manuscript version. Prepare a corrected version before arXiv or journal
submission.**

## Required for the next version

### Reconcile results and manuscript

The documented full reproduction command currently regenerates numerous result
artifacts and then fails the manuscript consistency audit. The current code
produces a subsequent-election vote-share coefficient of approximately
`-0.060312`, while the audit expects `-0.061153`.

`PAPER.md` also mixes results from two analytical vintages. For example, it
reports both:

* `N = 7,639` and a full-control female coefficient of approximately `-0.60`;
* `N = 7,812` and a coefficient of approximately `-0.54`.

Before the next release:

* choose the current code and tracked inputs as the authoritative specification;
* rerun the complete core and extended workflow;
* update every affected number in `PAPER.md`;
* regenerate the manuscript audit, LaTeX source, PDF, release archive, and
  checksums;
* verify that `bash scripts/reproduce.sh` finishes successfully from a clean
  checkout.

### Correct the Zenodo description

DOI `10.5281/zenodo.21591947` currently identifies the GitHub `v0.1.0`
**software** archive, not a separately deposited working-paper record. Repository
documentation should describe it as a software/reproducibility DOI rather than
the paper DOI.

The Zenodo record also needs its stale reference to an accompanying arXiv paper
removed. If a paper DOI is wanted, publish the prepared PDF and source as a
separate Zenodo `Publication / Working paper` record.

### Confirm third-party data rights

Confirm that redistribution of the tracked TCPD and other election-data files is
consistent with the providers' current terms. The GitHub-generated Zenodo
software archive includes the tracked repository data, while its record uses an
MIT license. Clarify that MIT covers original code only and does not relicense
third-party data; contact Zenodo support if the archived record requires a file
or licensing correction.

### Remove obsolete release artifacts

For the next version, remove the unused tracked July 15 uncompressed TCPD GE
export and the superseded July 16 frozen archive. Keep only the inputs and
release artifacts used by the documented workflow.

## Optional arXiv publication

If endorsement is obtained:

* submit the corrected manuscript version to arXiv;
* add the assigned arXiv identifier to the paper, README, citation metadata, and
  Zenodo records.

## Before journal submission

* Add dependence-robust uncertainty appropriate to repeated party,
  constituency, election, and state structure.
* Complete human adjudication of unresolved fuzzy entity links.
* Strengthen convergent validation using outcomes such as appointments,
  leadership roles, or expert assessments.
* Check the target journal's preprint, software-archive, data-redistribution, and
  licensing policies.
