"""Electoral capability analysis with MyNeta controls.

Corrected pipeline: constituency vote shares and expected vote-share baselines are
computed on the full parliament/election results before the sample is restricted
to candidates matched to MyNeta controls.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path

from electoral_pipeline import OUTPUT_DIR, build_analysis_dataset

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Building corrected analysis dataset...")
df_analysis, merged_audit = build_analysis_dataset()
print(f"  Matched analysis observations: {len(df_analysis)}")
print(f"  Full candidates with expected vote share: {len(merged_audit)}")

# Merge diagnostics
merge_rate_overall = merged_audit["MERGED"].mean()
merge_rate_female = merged_audit.loc[merged_audit["SEX"] == "F", "MERGED"].mean()
merge_rate_male = merged_audit.loc[merged_audit["SEX"] == "M", "MERGED"].mean()
print(f"  Match rate overall: {merge_rate_overall:.1%}")
print(f"  Match rate female:  {merge_rate_female:.1%}")
print(f"  Match rate male:    {merge_rate_male:.1%}")

# Descriptives
n_total = len(df_analysis)
n_female = int(df_analysis["FEMALE"].sum())
print(f"  Female candidates: {n_female}/{n_total} ({n_female/n_total*100:.1f}%)")

# Regression models
models = []
y = df_analysis["CAPABILITY"].astype(float)
model_specs = [
    ("Bivariate", ["FEMALE"]),
    ("+ Year FE", ["FEMALE", "YEAR_2009"]),
    ("+ Criminal + Assets", ["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS"]),
    ("Full controls", ["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]),
]

for name, cols in model_specs:
    X = sm.add_constant(df_analysis[cols].astype(float))
    model = sm.OLS(y, X).fit(cov_type="HC3")
    ci = model.conf_int().loc["FEMALE"]
    models.append({
        "Model": name,
        "Variable": "Female",
        "Coef": model.params["FEMALE"],
        "SE": model.bse["FEMALE"],
        "CI_lower": ci[0],
        "CI_upper": ci[1],
        "p_value": model.pvalues["FEMALE"],
        "N": int(model.nobs),
        "R2": model.rsquared,
    })
    print(f"{name}: female={model.params['FEMALE']:.4f}, SE={model.bse['FEMALE']:.4f}, p={model.pvalues['FEMALE']:.4f}")

# Exclude groups with single candidate in party-state baseline for sensitivity
if "GROUP_SIZE" in df_analysis.columns:
    df_multi = df_analysis[df_analysis["GROUP_SIZE"].fillna(2) > 1].copy()
else:
    df_multi = df_analysis.copy()
if len(df_multi) > 0:
    X = sm.add_constant(df_multi[["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]].astype(float))
    m = sm.OLS(df_multi["CAPABILITY"].astype(float), X).fit(cov_type="HC3")
    ci = m.conf_int().loc["FEMALE"]
    models.append({
        "Model": "Full (excl. single-candidate)",
        "Variable": "Female",
        "Coef": m.params["FEMALE"],
        "SE": m.bse["FEMALE"],
        "CI_lower": ci[0],
        "CI_upper": ci[1],
        "p_value": m.pvalues["FEMALE"],
        "N": int(m.nobs),
        "R2": m.rsquared,
    })

regression_table = pd.DataFrame(models)
regression_table.to_csv(OUTPUT_DIR / "regression_table.csv", index=False)

# Three-stage decomposition
winnable = df_analysis["WINNABLE"].astype(bool)
cap_gap_winnable = (
    df_analysis.loc[winnable & (df_analysis["FEMALE"] == 1), "CAPABILITY"].mean()
    - df_analysis.loc[winnable & (df_analysis["FEMALE"] == 0), "CAPABILITY"].mean()
)
winnable_female = df_analysis.loc[df_analysis["FEMALE"] == 1, "WINNABLE"].mean()
winnable_male = df_analysis.loc[df_analysis["FEMALE"] == 0, "WINNABLE"].mean()
win_rate_female = df_analysis.loc[df_analysis["FEMALE"] == 1, "WINNER"].mean()
win_rate_male = df_analysis.loc[df_analysis["FEMALE"] == 0, "WINNER"].mean()

summary = {
    "n_total": n_total,
    "n_female": n_female,
    "female_pct": round(n_female / n_total * 100, 1),
    "bivariate_female_coef": round(regression_table.loc[regression_table["Model"] == "Bivariate", "Coef"].iloc[0], 4),
    "bivariate_female_se": round(regression_table.loc[regression_table["Model"] == "Bivariate", "SE"].iloc[0], 4),
    "bivariate_female_p": round(regression_table.loc[regression_table["Model"] == "Bivariate", "p_value"].iloc[0], 4),
    "full_controls_female_coef": round(regression_table.loc[regression_table["Model"] == "Full controls", "Coef"].iloc[0], 4),
    "full_controls_female_se": round(regression_table.loc[regression_table["Model"] == "Full controls", "SE"].iloc[0], 4),
    "full_controls_female_p": round(regression_table.loc[regression_table["Model"] == "Full controls", "p_value"].iloc[0], 4),
    "capability_gap_winnable": round(cap_gap_winnable, 4),
    "winnable_share_female": round(winnable_female * 100, 1),
    "winnable_share_male": round(winnable_male * 100, 1),
    "win_rate_female": round(win_rate_female * 100, 1),
    "win_rate_male": round(win_rate_male * 100, 1),
    "merge_rate_overall": round(merge_rate_overall * 100, 1),
    "merge_rate_female": round(merge_rate_female * 100, 1),
    "merge_rate_male": round(merge_rate_male * 100, 1),
    "single_candidate_pct": round((df_analysis.get("GROUP_SIZE", pd.Series(index=df_analysis.index, data=np.nan)).fillna(2) == 1).mean() * 100, 1),
}
pd.Series(summary).to_csv(OUTPUT_DIR / "summary_with_controls.csv")

# Save full corrected analysis dataset and unmatched audit rows for reproducibility.
df_analysis.to_csv(OUTPUT_DIR / "analysis_with_controls.csv", index=False)
merged_audit.to_csv(OUTPUT_DIR / "merge_audit_exact.csv", index=False)

print(f"Saved corrected analysis outputs to {OUTPUT_DIR}")
print("Summary:")
print(pd.Series(summary).to_string())
