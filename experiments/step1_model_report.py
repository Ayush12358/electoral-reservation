"""Step-1 expected vote-share model fit report.

Uses full parliament data to evaluate calibration of the expected vote-share
baseline used for candidate capability residuals.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path

from electoral_pipeline import OUTPUT_DIR, add_expected_vote_share, load_parliament

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading and computing expected vote shares...")
df = add_expected_vote_share(load_parliament())
df = df.dropna(subset=["EXPECTED_VOTE_SHARE", "VOTE_SHARE"]).copy()
df["RESIDUAL"] = df["VOTE_SHARE"] - df["EXPECTED_VOTE_SHARE"]

print("\n" + "=" * 60)
print("STEP 1 MODEL: EXPECTED VOTE SHARE")
print("=" * 60)

def r2(y, pred):
    return 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)

results = {
    "overall_r2": r2(df["VOTE_SHARE"], df["EXPECTED_VOTE_SHARE"]),
    "n_total": len(df),
    "mean_residual": df["RESIDUAL"].mean(),
    "sd_residual": df["RESIDUAL"].std(),
    "median_residual": df["RESIDUAL"].median(),
    "iqr_low": df["RESIDUAL"].quantile(0.25),
    "iqr_high": df["RESIDUAL"].quantile(0.75),
}
print(f"Overall R²: {results['overall_r2']:.4f}; N={len(df)}")
for year, yr in df.groupby("YEAR"):
    val = r2(yr["VOTE_SHARE"], yr["EXPECTED_VOTE_SHARE"])
    results[f"r2_{int(year)}"] = val
    results[f"n_{int(year)}"] = len(yr)
    print(f"  {int(year)} R²: {val:.4f} (N={len(yr)})")

print("\n  --- 2009 by source ---")
for source, src in df[df["YEAR"] == 2009].groupby("EXPECTED_SOURCE"):
    val = r2(src["VOTE_SHARE"], src["EXPECTED_VOTE_SHARE"])
    results[f"r2_2009_{source.replace(' ', '_').replace('-', '_')}"] = val
    results[f"n_2009_{source.replace(' ', '_').replace('-', '_')}"] = len(src)
    print(f"    {source}: R²={val:.4f}, N={len(src)}")

print("\n--- Residual distribution ---")
for k in ["mean_residual", "sd_residual", "median_residual", "iqr_low", "iqr_high"]:
    print(f"  {k}: {results[k]:.4f}")

X = sm.add_constant(df[["EXPECTED_VOTE_SHARE"]])
model = sm.OLS(df["VOTE_SHARE"], X).fit(cov_type="HC3")
results.update({
    "regression_beta": model.params["EXPECTED_VOTE_SHARE"],
    "regression_beta_se": model.bse["EXPECTED_VOTE_SHARE"],
    "regression_intercept": model.params["const"],
    "regression_intercept_se": model.bse["const"],
    "regression_r2": model.rsquared,
})
print("\nRegression: Actual = a + b * Expected + e")
print(f"  b = {results['regression_beta']:.4f} (SE: {results['regression_beta_se']:.4f})")
print(f"  intercept = {results['regression_intercept']:.4f} (SE: {results['regression_intercept_se']:.4f})")
print(f"  R² = {results['regression_r2']:.4f}")

pd.Series(results).to_csv(OUTPUT_DIR / "step1_model_fit.csv")
print(f"Saved: {OUTPUT_DIR / 'step1_model_fit.csv'}")
