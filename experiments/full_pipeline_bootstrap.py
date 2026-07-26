"""Full-pipeline bootstrap for the corrected Lok Sabha capability analysis.

This script re-samples the raw parliament election table within year strata,
recomputes vote shares, re-estimates the expected-vote baseline, re-runs the
MyNeta exact merge, and then re-fits the core capability regression.

Compared with `bootstrap_uncertainty.py`, this propagates uncertainty through the
first-stage measurement step rather than bootstrapping only the final matched
analysis sample.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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

SEED = 42
DEFAULT_N_BOOT = 200
RESULT_PREFIX = "full_pipeline_bootstrap"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fill_missing_controls(df: pd.DataFrame) -> pd.DataFrame:
    """Mirror the analysis-time missing-value handling for control variables."""
    out = df.copy()
    for col in ["HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]:
        if col not in out.columns:
            continue
        if col == "EDU_NUM":
            out[col] = out[col].fillna(0)
        else:
            fill_value = out[col].median() if out[col].notna().any() else 0
            out[col] = out[col].fillna(fill_value)
    return out


def fit_female_coef(df: pd.DataFrame):
    cols = ["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]
    X = sm.add_constant(df[cols].astype(float), has_constant="add")
    y = df["CAPABILITY"].astype(float)
    m = sm.OLS(y, X).fit(cov_type="HC3")
    return float(m.params["FEMALE"]), float(m.bse["FEMALE"]), float(m.pvalues["FEMALE"])


def fit_calibration(df: pd.DataFrame):
    X = sm.add_constant(df[["EXPECTED_VOTE_SHARE"]].astype(float), has_constant="add")
    m = sm.OLS(df["VOTE_SHARE"].astype(float), X).fit(cov_type="HC3")
    return (
        float(m.params["EXPECTED_VOTE_SHARE"]),
        float(m.params["const"]),
        float(m.rsquared),
    )


def bootstrap_parliament(parliament: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Bootstrap the parliament table by constituency blocks within year strata."""
    parts = []
    for year, g in parliament.groupby("YEAR", observed=True):
        blocks = g["PC"].drop_duplicates().to_numpy()
        sampled_blocks = rng.choice(blocks, size=len(blocks), replace=True)
        for pc in sampled_blocks:
            parts.append(g[g["PC"] == pc].copy())

    boot = pd.concat(parts, ignore_index=True)
    boot = boot.reset_index(drop=True)
    boot["PARL_ROW_ID"] = np.arange(len(boot))

    # Recompute totals and vote shares on the resampled raw table.
    boot["TOTAL_VOTES"] = boot.groupby(["YEAR", "PC"], observed=True)["VOTES"].transform("sum")
    boot["VOTE_SHARE"] = boot["VOTES"] / boot["TOTAL_VOTES"] * 100
    boot["WINNER"] = (
        boot.groupby(["YEAR", "PC"], observed=True)["VOTES"].rank(method="first", ascending=False) == 1
    ).astype(int)
    return boot


def build_full_pipeline(parliament: pd.DataFrame, myneta: pd.DataFrame):
    """Run the corrected measurement + merge pipeline on a given parliament table."""
    measured = add_expected_vote_share(parliament)
    merged = exact_merge(measured, myneta)
    matched = merged[merged["MERGED"] == 1].copy()
    matched = fill_missing_controls(matched)
    return measured, merged, matched


def summarize_observed(parliament: pd.DataFrame, myneta: pd.DataFrame):
    measured, merged, matched = build_full_pipeline(parliament, myneta)

    obs_coef, obs_se, obs_p = fit_female_coef(matched)
    w = matched[matched["WINNABLE"] == 1]
    obs_gap = float(
        w.loc[w["FEMALE"] == 1, "CAPABILITY"].mean() - w.loc[w["FEMALE"] == 0, "CAPABILITY"].mean()
    )
    slope, intercept, r2 = fit_calibration(measured)

    return {
        "observed": {
            "female_coef": obs_coef,
            "female_se": obs_se,
            "female_p": obs_p,
            "winnable_gap": obs_gap,
            "calibration_slope": slope,
            "calibration_intercept": intercept,
            "calibration_r2": r2,
            "n_matched": len(matched),
            "match_rate_overall": float(merged["MERGED"].mean()),
            "match_rate_female": float(merged.loc[merged["SEX"] == "F", "MERGED"].mean()),
            "match_rate_male": float(merged.loc[merged["SEX"] == "M", "MERGED"].mean()),
        },
        "matched": matched,
        "measured": measured,
        "merged": merged,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    print("Loading base parliament and MyNeta data...")
    parliament = load_parliament(years=(2004, 2009))
    myneta = load_myneta(years=(2004, 2009))

    print("Computing observed full-pipeline estimates...")
    observed = summarize_observed(parliament, myneta)
    obs = observed["observed"]
    print(f"  Matched N: {obs['n_matched']}")
    print(f"  Female coef: {obs['female_coef']:.4f} (SE {obs['female_se']:.4f}, p {obs['female_p']:.4f})")
    print(f"  Calibration slope: {obs['calibration_slope']:.4f}, R²: {obs['calibration_r2']:.4f}")

    rows = []
    for i in range(args.n_boot):
        boot_parl = bootstrap_parliament(parliament, rng)
        measured_b, merged_b, matched_b = build_full_pipeline(boot_parl, myneta)

        coef, se, p = fit_female_coef(matched_b)
        wb = matched_b[matched_b["WINNABLE"] == 1]
        gap = float(wb.loc[wb["FEMALE"] == 1, "CAPABILITY"].mean() - wb.loc[wb["FEMALE"] == 0, "CAPABILITY"].mean())
        slope, intercept, r2 = fit_calibration(measured_b)

        rows.append({
            "iteration": i,
            "female_coef": coef,
            "female_se": se,
            "female_p": p,
            "winnable_gap": gap,
            "calibration_slope": slope,
            "calibration_intercept": intercept,
            "calibration_r2": r2,
            "n_matched": len(matched_b),
            "match_rate_overall": float(merged_b["MERGED"].mean()),
            "match_rate_female": float(merged_b.loc[merged_b["SEX"] == "F", "MERGED"].mean()),
            "match_rate_male": float(merged_b.loc[merged_b["SEX"] == "M", "MERGED"].mean()),
        })

        if (i + 1) % max(1, args.n_boot // 10) == 0 or i == 0:
            print(f"  bootstrap {i + 1}/{args.n_boot}")

    boot = pd.DataFrame(rows)
    boot_path = OUTPUT_DIR / f"{RESULT_PREFIX}_draws.csv"
    boot.to_csv(boot_path, index=False)

    summary = pd.DataFrame([
        {
            "estimand": "female_capability_coef",
            "observed": obs["female_coef"],
            "bootstrap_mean": boot["female_coef"].mean(),
            "bootstrap_sd": boot["female_coef"].std(ddof=1),
            "ci_2_5": boot["female_coef"].quantile(0.025),
            "ci_97_5": boot["female_coef"].quantile(0.975),
            "pr_gt_0": (boot["female_coef"] > 0).mean(),
            "observed_se_hc3": obs["female_se"],
            "observed_p_hc3": obs["female_p"],
        },
        {
            "estimand": "winnable_capability_gap",
            "observed": obs["winnable_gap"],
            "bootstrap_mean": boot["winnable_gap"].mean(),
            "bootstrap_sd": boot["winnable_gap"].std(ddof=1),
            "ci_2_5": boot["winnable_gap"].quantile(0.025),
            "ci_97_5": boot["winnable_gap"].quantile(0.975),
            "pr_gt_0": (boot["winnable_gap"] > 0).mean(),
            "observed_se_hc3": np.nan,
            "observed_p_hc3": np.nan,
        },
        {
            "estimand": "calibration_slope",
            "observed": obs["calibration_slope"],
            "bootstrap_mean": boot["calibration_slope"].mean(),
            "bootstrap_sd": boot["calibration_slope"].std(ddof=1),
            "ci_2_5": boot["calibration_slope"].quantile(0.025),
            "ci_97_5": boot["calibration_slope"].quantile(0.975),
            "pr_gt_0": (boot["calibration_slope"] > 0).mean(),
            "observed_se_hc3": np.nan,
            "observed_p_hc3": np.nan,
        },
        {
            "estimand": "calibration_r2",
            "observed": obs["calibration_r2"],
            "bootstrap_mean": boot["calibration_r2"].mean(),
            "bootstrap_sd": boot["calibration_r2"].std(ddof=1),
            "ci_2_5": boot["calibration_r2"].quantile(0.025),
            "ci_97_5": boot["calibration_r2"].quantile(0.975),
            "pr_gt_0": (boot["calibration_r2"] > 0).mean(),
            "observed_se_hc3": np.nan,
            "observed_p_hc3": np.nan,
        },
    ])
    summary_path = OUTPUT_DIR / f"{RESULT_PREFIX}_summary.csv"
    summary.to_csv(summary_path, index=False)

    manifest = {
        "seed": args.seed,
        "n_boot": args.n_boot,
        "stratification": "by YEAR with constituency-block resampling before recomputing vote shares and expected shares",
        "scope": "full pipeline over the raw election table; MyNeta controls held fixed as the external linkage source",
        "notes": [
            "This propagates uncertainty through the first-stage measurement step and the exact-match linkage.",
            "Bootstrap resamples preserve constituency structure within each year, but still treat MyNeta as fixed external control data.",
        ],
        "observed": obs,
    }
    manifest_path = OUTPUT_DIR / f"{RESULT_PREFIX}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n=== FULL PIPELINE BOOTSTRAP SUMMARY ===")
    print(summary.round(4).to_string(index=False))
    print(f"\nSaved draws to: {boot_path}")
    print(f"Saved summary to: {summary_path}")
    print(f"Saved manifest to: {manifest_path}")


if __name__ == "__main__":
    main()
