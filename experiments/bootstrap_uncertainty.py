"""Bootstrap uncertainty propagation for the corrected Lok Sabha analysis.

This is a practical sampling-uncertainty layer over the corrected 2004/2009
matched analysis. It re-samples the candidate rows within year strata and
re-estimates the female capability coefficient and the winnable-seat capability
 gap.

Note: this does not fully propagate first-stage expected-vote-share estimation
uncertainty from the raw election table; it is a conservative bootstrap over the
final analysis sample. It is still useful as an uncertainty benchmark and a
starting point for deeper pipeline bootstrapping.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from electoral_pipeline import OUTPUT_DIR, build_analysis_dataset

SEED = 42
N_BOOT = 500
rng = np.random.default_rng(SEED)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fit_female_coef(df: pd.DataFrame):
    cols = ["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]
    X = sm.add_constant(df[cols].astype(float), has_constant="add")
    y = df["CAPABILITY"].astype(float)
    m = sm.OLS(y, X).fit(cov_type="HC3")
    return float(m.params["FEMALE"]), float(m.bse["FEMALE"]), float(m.pvalues["FEMALE"])


def bootstrap_sample(df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for year, g in df.groupby("YEAR", observed=True):
        # Sample within year to preserve election composition.
        seed = int(rng.integers(0, 2**31 - 1))
        parts.append(g.sample(n=len(g), replace=True, random_state=seed))
    return pd.concat(parts, ignore_index=True)


def main():
    print("Building corrected analysis dataset...")
    df, _ = build_analysis_dataset()
    df["EDU_NUM"] = df["EDU_NUM"].fillna(0)
    df["HAS_CRIMINAL"] = df["HAS_CRIMINAL"].fillna(0)
    df["LOG_ASSETS"] = df["LOG_ASSETS"].fillna(0)

    # Observed estimates
    obs_coef, obs_se, obs_p = fit_female_coef(df)
    w = df[df["WINNABLE"] == 1]
    obs_gap = float(w.loc[w["FEMALE"] == 1, "CAPABILITY"].mean() - w.loc[w["FEMALE"] == 0, "CAPABILITY"].mean())

    rows = []
    for i in range(N_BOOT):
        boot = bootstrap_sample(df)
        coef, se, p = fit_female_coef(boot)
        wb = boot[boot["WINNABLE"] == 1]
        gap = float(wb.loc[wb["FEMALE"] == 1, "CAPABILITY"].mean() - wb.loc[wb["FEMALE"] == 0, "CAPABILITY"].mean())
        rows.append({
            "iteration": i,
            "female_coef": coef,
            "female_se": se,
            "female_p": p,
            "winnable_gap": gap,
        })
        if (i + 1) % 50 == 0:
            print(f"  bootstrap {i + 1}/{N_BOOT}")

    boot = pd.DataFrame(rows)
    boot.to_csv(OUTPUT_DIR / "bootstrap_uncertainty_draws.csv", index=False)

    summary = pd.DataFrame([
        {
            "estimand": "female_capability_coef",
            "observed": obs_coef,
            "bootstrap_mean": boot["female_coef"].mean(),
            "bootstrap_sd": boot["female_coef"].std(ddof=1),
            "ci_2_5": boot["female_coef"].quantile(0.025),
            "ci_97_5": boot["female_coef"].quantile(0.975),
            "pr_gt_0": (boot["female_coef"] > 0).mean(),
            "observed_se_hc3": obs_se,
            "observed_p_hc3": obs_p,
        },
        {
            "estimand": "winnable_capability_gap",
            "observed": obs_gap,
            "bootstrap_mean": boot["winnable_gap"].mean(),
            "bootstrap_sd": boot["winnable_gap"].std(ddof=1),
            "ci_2_5": boot["winnable_gap"].quantile(0.025),
            "ci_97_5": boot["winnable_gap"].quantile(0.975),
            "pr_gt_0": (boot["winnable_gap"] > 0).mean(),
            "observed_se_hc3": np.nan,
            "observed_p_hc3": np.nan,
        },
    ])
    summary.to_csv(OUTPUT_DIR / "bootstrap_uncertainty_summary.csv", index=False)

    manifest = {
        "seed": SEED,
        "n_boot": N_BOOT,
        "stratification": "by YEAR within the matched analysis sample",
        "scope": "sampling uncertainty only; does not re-estimate the raw-election expected-vote-share stage",
        "notes": [
            "This is a conservative first bootstrap pass for uncertainty propagation.",
            "A deeper bootstrap can resample the raw election table and re-run the full pipeline later.",
        ],
    }
    with open(OUTPUT_DIR / "bootstrap_uncertainty_manifest.json", "w", encoding="utf-8") as f:
        import json
        json.dump(manifest, f, indent=2)

    print("\n=== BOOTSTRAP SUMMARY ===")
    print(summary.round(4).to_string(index=False))
    print(f"\nObserved coef: {obs_coef:.4f} (HC3 SE={obs_se:.4f}, p={obs_p:.4f})")
    print(f"Observed winnable gap: {obs_gap:.4f}")
    print("Saved bootstrap outputs to experiments/results/.")


if __name__ == "__main__":
    main()
