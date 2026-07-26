"""Bound the effect of conservative fuzzy entity links on the main regression.

The exact-match sample remains the estimand-defining main analysis. This script
recreates the review queue, then reports results under acceptance of every
candidate fuzzy link and of score-restricted subsets. It never treats those links
as adjudicated identities.
"""

from __future__ import annotations

from difflib import SequenceMatcher

import numpy as np
import pandas as pd
import statsmodels.api as sm

from electoral_pipeline import (
    OUTPUT_DIR,
    add_expected_vote_share,
    exact_merge,
    load_myneta,
    load_parliament,
)


def recover_conservative_links(full: pd.DataFrame, myneta: pd.DataFrame, exact: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the review-queue matching rule while retaining source row IDs."""
    unmatched = exact.loc[exact["MERGED"] == 0].copy()
    used = set(exact.loc[exact["MERGED"] == 1, "MYNETA_ROW_ID"].dropna().astype(int))
    pool = myneta.loc[~myneta["MYNETA_ROW_ID"].isin(used)].copy()
    links = []
    for _, row in unmatched.iterrows():
        block = pool.loc[(pool["YEAR"] == row["YEAR"]) & (pool["CONSTITUENCY_CLEAN"] == row["PC_CLEAN"])]
        if block.empty:
            continue
        same_party = block.loc[block["PARTY_CLEAN"] == row["PARTY_CLEAN"]]
        candidates = same_party if not same_party.empty else block
        scored = []
        for _, candidate in candidates.iterrows():
            name_score = SequenceMatcher(None, row["NAME_CLEAN"], candidate["CANDIDATE_CLEAN"]).ratio()
            party_score = 1.0 if row["PARTY_CLEAN"] == candidate["PARTY_CLEAN"] else SequenceMatcher(None, row["PARTY_CLEAN"], candidate["PARTY_CLEAN"]).ratio()
            scored.append((0.90 * name_score + 0.10 * party_score, name_score, party_score, candidate))
        if not scored:
            continue
        score, name_score, party_score, candidate = max(scored, key=lambda x: x[0])
        if score >= 0.94 and name_score >= 0.93:
            priority = "P1" if score >= 0.98 else "P2" if score >= 0.97 else "P3" if score >= 0.95 else "P4"
            links.append({
                "PARL_ROW_ID": row["PARL_ROW_ID"],
                "MYNETA_ROW_ID": int(candidate["MYNETA_ROW_ID"]),
                "match_score": score,
                "name_score": name_score,
                "party_score": party_score,
                "review_priority": priority,
            })
            pool = pool.loc[pool["MYNETA_ROW_ID"] != candidate["MYNETA_ROW_ID"]]
    return pd.DataFrame(links)


def prepare_controls(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["EDU_NUM"] = data["EDU_NUM"].fillna(0)
    for column in ["HAS_CRIMINAL", "LOG_ASSETS"]:
        data[column] = data[column].fillna(data[column].median())
    return data


def fit_summary(label: str, data: pd.DataFrame) -> dict:
    data = prepare_controls(data)
    columns = ["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]
    model = sm.OLS(data["CAPABILITY"].astype(float), sm.add_constant(data[columns].astype(float))).fit(cov_type="HC3")
    ci = model.conf_int().loc["FEMALE"]
    return {
        "scenario": label,
        "n": int(model.nobs),
        "n_fuzzy": int(data.get("FUZZY_ACCEPTED", pd.Series(0, index=data.index)).sum()),
        "female_coef": model.params["FEMALE"],
        "female_se_hc3": model.bse["FEMALE"],
        "female_p_value": model.pvalues["FEMALE"],
        "female_ci_lower": ci.iloc[0],
        "female_ci_upper": ci.iloc[1],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full = add_expected_vote_share(load_parliament())
    myneta = load_myneta()
    exact = exact_merge(full, myneta)
    links = recover_conservative_links(full, myneta, exact)
    links.to_csv(OUTPUT_DIR / "fuzzy_match_sensitivity_links.csv", index=False)

    controls = myneta[["MYNETA_ROW_ID", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]]
    exact_sample = exact.loc[exact["MERGED"] == 1].copy()
    exact_sample["FUZZY_ACCEPTED"] = 0
    recovered = full.merge(links, on="PARL_ROW_ID", how="inner", validate="one_to_one")
    recovered = recovered.merge(controls, on="MYNETA_ROW_ID", how="left", validate="one_to_one")
    recovered["FUZZY_ACCEPTED"] = 1

    # A blank, structured review record keeps manual identity decisions separate
    # from the model-generated candidate links and makes later acceptance auditable.
    myneta_identity = myneta[["MYNETA_ROW_ID", "Candidate", "Party"]].rename(
        columns={"Candidate": "myneta_name", "Party": "myneta_party"}
    )
    review = recovered.merge(myneta_identity, on="MYNETA_ROW_ID", how="left", validate="one_to_one")
    review = review[[
        "PARL_ROW_ID", "MYNETA_ROW_ID", "YEAR", "PC", "NAME", "PARTY",
        "myneta_name", "myneta_party", "match_score", "name_score", "party_score", "review_priority",
    ]].rename(columns={"NAME": "parliament_name", "PARTY": "parliament_party"})
    review.insert(0, "review_id", range(1, len(review) + 1))
    review["decision"] = ""
    review["evidence_reference"] = ""
    review["reviewer"] = ""
    review["reviewed_at_utc"] = ""
    review["notes"] = ""
    review.to_csv(OUTPUT_DIR / "entity_resolution_adjudication_template.csv", index=False)

    rows = [fit_summary("exact_match_main", exact_sample)]
    for threshold in [0.98, 0.97, 0.95, 0.94]:
        accepted = recovered.loc[recovered["match_score"] >= threshold]
        combined = pd.concat([exact_sample, accepted], ignore_index=True, sort=False)
        rows.append(fit_summary(f"exact_plus_fuzzy_score_ge_{threshold:.2f}", combined))
    results = pd.DataFrame(rows)
    results["coef_change_from_exact"] = results["female_coef"] - results.loc[0, "female_coef"]
    results.to_csv(OUTPUT_DIR / "fuzzy_match_sensitivity.csv", index=False)

    print(f"Recovered conservative fuzzy links: {len(links)}")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
