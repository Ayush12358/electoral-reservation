"""Apply human decisions from the fuzzy entity-resolution review queue.

The generated adjudication template is deliberately separate from the exact-match
main analysis.  This script accepts only explicit ``accept`` decisions, reports
pending/invalid records, and writes a non-main sensitivity result.  Use
``--require-complete`` when a completed review is required for a release.
"""

from __future__ import annotations

import argparse
import json

import pandas as pd
import statsmodels.api as sm

from electoral_pipeline import OUTPUT_DIR, add_expected_vote_share, exact_merge, load_myneta, load_parliament
from fuzzy_match_sensitivity import fit_summary, prepare_controls


DECISIONS = {"", "accept", "reject"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="fail unless every review row has an accept/reject decision",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template_path = OUTPUT_DIR / "entity_resolution_adjudication_template.csv"
    links_path = OUTPUT_DIR / "fuzzy_match_sensitivity_links.csv"
    template = pd.read_csv(template_path, dtype={"decision": "string"})
    links = pd.read_csv(links_path)

    required_template = {"PARL_ROW_ID", "MYNETA_ROW_ID", "decision"}
    missing = required_template.difference(template.columns)
    if missing:
        raise ValueError(f"Adjudication template missing columns: {sorted(missing)}")
    template["decision"] = template["decision"].fillna("").str.strip().str.lower()
    invalid = sorted(set(template["decision"]) - DECISIONS)
    if invalid:
        raise ValueError(f"Invalid decisions {invalid}; use accept, reject, or blank")
    if template.duplicated(["PARL_ROW_ID", "MYNETA_ROW_ID"]).any():
        raise ValueError("Adjudication template contains duplicate link keys")

    joined = links.merge(
        template[["PARL_ROW_ID", "MYNETA_ROW_ID", "decision"]],
        on=["PARL_ROW_ID", "MYNETA_ROW_ID"],
        how="left",
        validate="one_to_one",
    )
    if joined["decision"].isna().any():
        raise ValueError("Some generated fuzzy links are absent from the adjudication template")
    pending = int((joined["decision"] == "").sum())
    accepted = joined.loc[joined["decision"] == "accept"].copy()
    rejected = int((joined["decision"] == "reject").sum())
    status = {
        "template": str(template_path),
        "n_links": int(len(joined)),
        "n_accept": int(len(accepted)),
        "n_reject": rejected,
        "n_pending": pending,
        "complete": pending == 0,
        "require_complete": bool(args.require_complete),
    }
    (OUTPUT_DIR / "entity_resolution_adjudication_status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    joined.to_csv(OUTPUT_DIR / "fuzzy_match_adjudicated_links.csv", index=False)
    if args.require_complete and pending:
        raise RuntimeError(f"{pending} fuzzy links remain pending adjudication")

    full = add_expected_vote_share(load_parliament())
    myneta = load_myneta()
    exact = exact_merge(full, myneta)
    exact_sample = exact.loc[exact["MERGED"] == 1].copy()
    exact_sample["FUZZY_ACCEPTED"] = 0
    controls = myneta[["MYNETA_ROW_ID", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]]
    recovered = full.merge(accepted, on="PARL_ROW_ID", how="inner", validate="one_to_one")
    recovered = recovered.merge(controls, on="MYNETA_ROW_ID", how="left", validate="one_to_one")
    recovered["FUZZY_ACCEPTED"] = 1
    combined = pd.concat([exact_sample, recovered], ignore_index=True, sort=False)
    rows = [fit_summary("exact_match_main", exact_sample)]
    if not recovered.empty:
        rows.append(fit_summary("adjudicated_accepts_only", recovered))
        rows.append(fit_summary("exact_plus_adjudicated_accepts", combined))
    summary = pd.DataFrame(rows)
    summary["coef_change_from_exact"] = summary["female_coef"] - summary.loc[0, "female_coef"]
    summary.to_csv(OUTPUT_DIR / "fuzzy_match_adjudicated_summary.csv", index=False)
    print(json.dumps(status, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
