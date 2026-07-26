"""Criterion validation using subsequent Lok Sabha performance in the TCPD panel.

Tests whether a candidate's party-normalized electoral contribution in election t
predicts performance at t+1 among candidates who recontest.  This is a criterion
validity exercise, not a causal design: recontesting is endogenous, so the script
also reports selection into the validation sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from tcpd_pipeline import OUTPUT_DIR, add_tcpd_expected_vote_share, load_tcpd_ge


SEED = 42
YEARS = (2004, 2009, 2014, 2019)
TRANSITIONS = dict(zip(YEARS[:-1], YEARS[1:]))
CONTROLS = ["Vote_Share_Percentage", "FEMALE", "INCUMBENT", "NATIONAL_PARTY", "EDU_NUM"]


def robust_ols(data: pd.DataFrame, outcome: str, predictors: list[str]):
    """Fit OLS with HC3 uncertainty and return the fitted model."""
    x = sm.add_constant(data[predictors].astype(float), has_constant="add")
    return sm.OLS(data[outcome].astype(float), x).fit(cov_type="HC3")


def grouped_cv_regression(data: pd.DataFrame, predictors: list[str]):
    """Candidate-grouped CV to prevent one person's records spanning train/test."""
    x = data[predictors].astype(float).fillna(0)
    y = data["NEXT_VOTE_SHARE"].astype(float)
    groups = data["pid"].astype(str)
    splitter = GroupKFold(n_splits=5)
    rows = []
    for fold, (train, test) in enumerate(splitter.split(x, y, groups), start=1):
        model = Ridge(alpha=1.0, random_state=SEED).fit(x.iloc[train], y.iloc[train])
        pred = model.predict(x.iloc[test])
        rows.append({
            "fold": fold,
            "n_test": len(test),
            "rmse": mean_squared_error(y.iloc[test], pred) ** 0.5,
            "r2": r2_score(y.iloc[test], pred),
        })
    return pd.DataFrame(rows)


def grouped_cv_auc(data: pd.DataFrame, predictors: list[str]):
    x = data[predictors].astype(float).fillna(0)
    y = data["NEXT_WINNER"].astype(int)
    groups = data["pid"].astype(str)
    splitter = GroupKFold(n_splits=5)
    rows = []
    for fold, (train, test) in enumerate(splitter.split(x, y, groups), start=1):
        model = LogisticRegression(max_iter=2000, solver="lbfgs", random_state=SEED)
        model.fit(x.iloc[train], y.iloc[train])
        pred = model.predict_proba(x.iloc[test])[:, 1]
        rows.append({"fold": fold, "n_test": len(test), "auc": roc_auc_score(y.iloc[test], pred)})
    return pd.DataFrame(rows)


def build_transition_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Attach next-cycle outcomes using TCPD's stable candidate identifier."""
    panels = []
    for source_year, next_year in TRANSITIONS.items():
        source = df.loc[df["Year"] == source_year].copy()
        target = df.loc[df["Year"] == next_year, ["pid", "Vote_Share_Percentage", "WINNER"]].copy()
        target = target.drop_duplicates("pid").rename(columns={
            "Vote_Share_Percentage": "NEXT_VOTE_SHARE", "WINNER": "NEXT_WINNER"
        })
        # A handful of candidates contest multiple constituencies in one election,
        # so source records are many-to-one with their next-cycle candidate record.
        panel = source.merge(target, on="pid", how="left", validate="many_to_one")
        panel["NEXT_YEAR"] = next_year
        panel["RECONTESTED_NEXT"] = panel["NEXT_VOTE_SHARE"].notna().astype(int)
        panels.append(panel)
    return pd.concat(panels, ignore_index=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading TCPD Lok Sabha panel (2004–2019)...")
    df = add_tcpd_expected_vote_share(load_tcpd_ge(years=YEARS))
    df["EDU_NUM"] = df["EDU_NUM"].fillna(0)
    panel = build_transition_panel(df)

    # Selection into the criterion-validation sample is substantively meaningful.
    selection_predictors = ["CAPABILITY", "Vote_Share_Percentage", "FEMALE", "INCUMBENT", "NATIONAL_PARTY", "EDU_NUM"]
    selection = sm.Logit(
        panel["RECONTESTED_NEXT"],
        sm.add_constant(panel[selection_predictors].astype(float), has_constant="add"),
    ).fit(disp=0)
    selection_rows = []
    for source_year, next_year in TRANSITIONS.items():
        sub = panel[panel["Year"] == source_year]
        selection_rows.append({
            "source_year": source_year,
            "next_year": next_year,
            "eligible_candidates": len(sub),
            "recontested_candidates": int(sub["RECONTESTED_NEXT"].sum()),
            "recontest_rate_pct": 100 * sub["RECONTESTED_NEXT"].mean(),
            "female_eligible": int(sub["FEMALE"].sum()),
            "female_recontest_rate_pct": 100 * sub.loc[sub["FEMALE"] == 1, "RECONTESTED_NEXT"].mean(),
            "male_recontest_rate_pct": 100 * sub.loc[sub["FEMALE"] == 0, "RECONTESTED_NEXT"].mean(),
        })
    selection_rows.append({
        "source_year": "pooled",
        "next_year": "next scheduled election",
        "eligible_candidates": len(panel),
        "recontested_candidates": int(panel["RECONTESTED_NEXT"].sum()),
        "recontest_rate_pct": 100 * panel["RECONTESTED_NEXT"].mean(),
        "female_eligible": int(panel["FEMALE"].sum()),
        "female_recontest_rate_pct": 100 * panel.loc[panel["FEMALE"] == 1, "RECONTESTED_NEXT"].mean(),
        "male_recontest_rate_pct": 100 * panel.loc[panel["FEMALE"] == 0, "RECONTESTED_NEXT"].mean(),
    })
    selection_out = pd.DataFrame(selection_rows)
    selection_out.to_csv(OUTPUT_DIR / "tcpd_future_validation_selection.csv", index=False)

    selection_coefficients = pd.DataFrame({
        "term": selection.params.index,
        "coefficient": selection.params.values,
        "odds_ratio": np.exp(selection.params.values),
        "robust_se": selection.bse.values,
        "p_value": selection.pvalues.values,
    })
    selection_coefficients.to_csv(OUTPUT_DIR / "tcpd_future_validation_selection_model.csv", index=False)

    validation = panel.loc[panel["RECONTESTED_NEXT"] == 1].copy()
    print(f"  Eligible candidate-election records: {len(panel)}")
    print(f"  Recontesting records: {len(validation)} ({len(validation) / len(panel) * 100:.1f}%)")

    # Current vote share establishes a demanding baseline.  Capability must add
    # signal above it to support persistence of candidate-specific contribution.
    baseline_predictors = CONTROLS + ["YEAR_2009", "YEAR_2014"]
    capability_predictors = ["CAPABILITY"] + baseline_predictors
    baseline = robust_ols(validation, "NEXT_VOTE_SHARE", baseline_predictors)
    capability = robust_ols(validation, "NEXT_VOTE_SHARE", capability_predictors)
    cv_baseline = grouped_cv_regression(validation, baseline_predictors)
    cv_capability = grouped_cv_regression(validation, capability_predictors)

    logit = sm.Logit(
        validation["NEXT_WINNER"].astype(int),
        sm.add_constant(validation[capability_predictors].astype(float), has_constant="add"),
    ).fit(disp=0, cov_type="HC3")
    auc_baseline = grouped_cv_auc(validation, baseline_predictors)
    auc_capability = grouped_cv_auc(validation, capability_predictors)

    results = pd.DataFrame([
        {
            "outcome": "next_election_vote_share",
            "sample": "recontesting candidates only",
            "n": len(validation),
            "capability_coefficient": capability.params["CAPABILITY"],
            "capability_robust_se": capability.bse["CAPABILITY"],
            "capability_p_value": capability.pvalues["CAPABILITY"],
            "baseline_in_sample_r2": baseline.rsquared,
            "capability_in_sample_r2": capability.rsquared,
            "baseline_grouped_cv_rmse": cv_baseline["rmse"].mean(),
            "capability_grouped_cv_rmse": cv_capability["rmse"].mean(),
            "baseline_grouped_cv_r2": cv_baseline["r2"].mean(),
            "capability_grouped_cv_r2": cv_capability["r2"].mean(),
        },
        {
            "outcome": "next_election_win",
            "sample": "recontesting candidates only",
            "n": len(validation),
            "capability_coefficient": logit.params["CAPABILITY"],
            "capability_robust_se": logit.bse["CAPABILITY"],
            "capability_p_value": logit.pvalues["CAPABILITY"],
            "capability_odds_ratio": np.exp(logit.params["CAPABILITY"]),
            "baseline_grouped_cv_auc": auc_baseline["auc"].mean(),
            "capability_grouped_cv_auc": auc_capability["auc"].mean(),
        },
    ])
    results.to_csv(OUTPUT_DIR / "tcpd_future_performance_validation.csv", index=False)
    validation[[
        "pid", "Year", "NEXT_YEAR", "FEMALE", "CAPABILITY", "Vote_Share_Percentage",
        "NEXT_VOTE_SHARE", "NEXT_WINNER", "INCUMBENT", "NATIONAL_PARTY", "EDU_NUM",
    ]].to_csv(OUTPUT_DIR / "tcpd_future_performance_validation_dataset.csv", index=False)
    pd.concat([
        cv_baseline.assign(model="baseline"),
        cv_capability.assign(model="baseline_plus_capability"),
    ]).to_csv(OUTPUT_DIR / "tcpd_future_vote_share_validation_folds.csv", index=False)
    pd.concat([
        auc_baseline.assign(model="baseline"),
        auc_capability.assign(model="baseline_plus_capability"),
    ]).to_csv(OUTPUT_DIR / "tcpd_future_win_validation_folds.csv", index=False)

    print(results.to_string(index=False))
    print("Saved TCPD future-performance validation outputs.")


if __name__ == "__main__":
    main()
