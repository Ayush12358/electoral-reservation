"""Extended Lok Sabha analysis: 2004-2019 using TCPD data.

Extends the original 2004-2009 analysis to include 2014 and 2019 elections.
Uses TCPD's pre-computed vote shares and richer covariates (education,
profession, incumbent status).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path

from tcpd_pipeline import (
    OUTPUT_DIR, load_tcpd_ge, add_tcpd_expected_vote_share, fit_ols_female
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. LOAD AND PREPARE
# ============================================================
print("Loading TCPD Lok Sabha data (2004-2019)...")
ge = load_tcpd_ge(years=(2004, 2009, 2014, 2019))
print(f"  Candidates (M/F): {len(ge)}")
for y in sorted(ge["Year"].unique()):
    sub = ge[ge["Year"] == y]
    nf = sub["FEMALE"].sum()
    print(f"    {y}: {len(sub)} candidates, {nf} female ({nf/len(sub)*100:.1f}%)")

print("\nAdding expected vote share and capability residuals...")
df = add_tcpd_expected_vote_share(ge)
print(f"  Analysis sample: {len(df)}")

# ============================================================
# 2. MEASUREMENT MODEL AUDIT
# ============================================================
print("\n" + "=" * 60)
print("MEASUREMENT MODEL AUDIT")
print("=" * 60)

for y in sorted(df["Year"].unique()):
    yr = df[df["Year"] == y]
    ss_res = np.sum((yr["Vote_Share_Percentage"] - yr["EXPECTED_VOTE_SHARE"]) ** 2)
    ss_tot = np.sum((yr["Vote_Share_Percentage"] - yr["Vote_Share_Percentage"].mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    print(f"  {y}: R² = {r2:.4f}, N = {len(yr)}, mean residual = {(yr['Vote_Share_Percentage'] - yr['EXPECTED_VOTE_SHARE']).mean():.2f}")

# Overall calibration
X_cal = sm.add_constant(df[["EXPECTED_VOTE_SHARE"]].astype(float))
cal = sm.OLS(df["Vote_Share_Percentage"].astype(float), X_cal).fit(cov_type="HC3")
print(f"\n  Calibration: slope = {cal.params['EXPECTED_VOTE_SHARE']:.4f} (SE: {cal.bse['EXPECTED_VOTE_SHARE']:.4f}), "
      f"intercept = {cal.params['const']:.4f}, R² = {cal.rsquared:.4f}")

# ============================================================
# 3. DESCRIPTIVE STATISTICS BY GENDER AND YEAR
# ============================================================
print("\n" + "=" * 60)
print("DESCRIPTIVE STATISTICS BY GENDER AND YEAR")
print("=" * 60)

desc_rows = []
for y in sorted(df["Year"].unique()):
    yr = df[df["Year"] == y]
    for g, label in [(1, "Female"), (0, "Male")]:
        sub = yr[yr["FEMALE"] == g]
        desc_rows.append({
            "Year": y, "Gender": label, "N": len(sub),
            "Vote_Share_Mean": sub["Vote_Share_Percentage"].mean(),
            "Capability_Mean": sub["CAPABILITY"].mean(),
            "Capability_SD": sub["CAPABILITY"].std(),
            "Winnable_Pct": sub["WINNABLE"].mean() * 100,
            "Winner_Pct": sub["WINNER"].mean() * 100,
            "Incumbent_Pct": sub["INCUMBENT"].mean() * 100,
        })

desc = pd.DataFrame(desc_rows)
print(desc.to_string(index=False))
desc.to_csv(OUTPUT_DIR / "extended_descriptives.csv", index=False)

# ============================================================
# 4. MAIN REGRESSIONS (POOLED 2004-2019)
# ============================================================
print("\n" + "=" * 60)
print("REGRESSIONS: POOLED 2004-2019")
print("=" * 60)

# Year fixed effects (2004 as base)
df["YEAR_2009"] = (df["Year"] == 2009).astype(int)
df["YEAR_2014"] = (df["Year"] == 2014).astype(int)
df["YEAR_2019"] = (df["Year"] == 2019).astype(int)
df["EDU_NUM"] = df["EDU_NUM"].fillna(0)

specs = [
    ("Bivariate", ["FEMALE"]),
    ("+ Year FE", ["FEMALE", "YEAR_2009", "YEAR_2014", "YEAR_2019"]),
    ("+ Incumbent + Party Type", ["FEMALE", "INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT"]),
    ("+ Education", ["FEMALE", "INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM"]),
    ("Full controls", ["FEMALE", "INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM",
                        "IS_PROFESSIONAL", "IS_BUSINESS", "IS_AGRICULTURE",
                        "YEAR_2009", "YEAR_2014", "YEAR_2019"]),
]

reg_rows = []
for name, controls in specs:
    coef, se, p, lo, hi, r2, n = fit_ols_female(df, controls)
    reg_rows.append({
        "Model": name, "Female_Coef": round(coef, 4), "SE": round(se, 4),
        "p_value": round(p, 4), "CI_lower": round(lo, 4), "CI_upper": round(hi, 4),
        "R2": round(r2, 4), "N": n,
    })
    print(f"  {name}: coef={coef:.4f}, SE={se:.4f}, p={p:.4f}, N={n}")

reg = pd.DataFrame(reg_rows)
reg.to_csv(OUTPUT_DIR / "extended_regression_table.csv", index=False)

# ============================================================
# 5. BY-YEAR REGRESSIONS
# ============================================================
print("\n" + "=" * 60)
print("BY-YEAR REGRESSIONS")
print("=" * 60)

year_rows = []
controls = ["INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM"]
for y in sorted(df["Year"].unique()):
    yr = df[df["Year"] == y]
    coef, se, p, lo, hi, r2, n = fit_ols_female(yr, controls)
    year_rows.append({
        "Year": y, "Female_Coef": round(coef, 4), "SE": round(se, 4),
        "p_value": round(p, 4), "CI_lower": round(lo, 4), "CI_upper": round(hi, 4),
        "N": n, "N_female": int(yr["FEMALE"].sum()),
    })
    print(f"  {y}: coef={coef:.4f}, SE={se:.4f}, p={p:.4f}, N={n}, N_f={yr['FEMALE'].sum()}")

year_reg = pd.DataFrame(year_rows)
year_reg.to_csv(OUTPUT_DIR / "extended_by_year.csv", index=False)

# ============================================================
# 6. THREE-STAGE DECOMPOSITION BY YEAR
# ============================================================
print("\n" + "=" * 60)
print("THREE-STAGE DECOMPOSITION BY YEAR")
print("=" * 60)

decomp_rows = []
for y in sorted(df["Year"].unique()):
    yr = df[df["Year"] == y]
    f_rate = yr["FEMALE"].mean()
    w_f = yr.loc[yr["FEMALE"] == 1, "WINNABLE"].mean()
    w_m = yr.loc[yr["FEMALE"] == 0, "WINNABLE"].mean()
    cap_f = yr.loc[(yr["FEMALE"] == 1) & (yr["WINNABLE"] == 1), "CAPABILITY"].mean()
    cap_m = yr.loc[(yr["FEMALE"] == 0) & (yr["WINNABLE"] == 1), "CAPABILITY"].mean()
    cap_gap = cap_f - cap_m if not (np.isnan(cap_f) or np.isnan(cap_m)) else np.nan
    win_f = yr.loc[yr["FEMALE"] == 1, "WINNER"].mean()
    win_m = yr.loc[yr["FEMALE"] == 0, "WINNER"].mean()
    decomp_rows.append({
        "Year": y,
        "Female_Candidate_Share": round(f_rate * 100, 1),
        "Winnable_Female": round(w_f * 100, 1),
        "Winnable_Male": round(w_m * 100, 1),
        "Capability_Gap_Winnable": round(cap_gap, 4) if not np.isnan(cap_gap) else None,
        "Win_Rate_Female": round(win_f * 100, 1),
        "Win_Rate_Male": round(win_m * 100, 1),
    })
    print(f"  {y}: candidate_share={f_rate*100:.1f}%, winnable_F={w_f*100:.1f}% vs M={w_m*100:.1f}%, "
          f"cap_gap={cap_gap:.4f}, win_F={win_f*100:.1f}% vs M={win_m*100:.1f}%")

decomp = pd.DataFrame(decomp_rows)
decomp.to_csv(OUTPUT_DIR / "extended_decomposition.csv", index=False)

# ============================================================
# 7. HETEROGENEITY BY SEAT TYPE AND PARTY TYPE
# ============================================================
print("\n" + "=" * 60)
print("HETEROGENEITY")
print("=" * 60)

het_rows = []
for label, sub in [
    ("All seats", df),
    ("General seats", df[df["SEAT_TYPE"] == "General"]),
    ("SC Reserved", df[df["SEAT_TYPE"] == "SC Reserved"]),
    ("ST Reserved", df[df["SEAT_TYPE"] == "ST Reserved"]),
    ("National parties", df[df["NATIONAL_PARTY"] == 1]),
    ("Non-national", df[df["NATIONAL_PARTY"] == 0]),
    ("Winnable seats", df[df["WINNABLE"] == 1]),
    ("Non-winnable", df[df["WINNABLE"] == 0]),
]:
    if len(sub) < 100 or sub["FEMALE"].sum() < 10:
        continue
    controls = ["INCUMBENT", "EDU_NUM", "YEAR_2009", "YEAR_2014", "YEAR_2019"]
    coef, se, p, lo, hi, r2, n = fit_ols_female(sub, controls)
    het_rows.append({
        "Subset": label, "Female_Coef": round(coef, 4), "SE": round(se, 4),
        "p_value": round(p, 4), "N": n, "N_female": int(sub["FEMALE"].sum()),
    })
    print(f"  {label}: coef={coef:.4f}, SE={se:.4f}, p={p:.4f}, N={n}")

het = pd.DataFrame(het_rows)
het.to_csv(OUTPUT_DIR / "extended_heterogeneity.csv", index=False)

# ============================================================
# 8. SPECIFICATION CURVE
# ============================================================
print("\n" + "=" * 60)
print("SPECIFICATION CURVE")
print("=" * 60)

spec_rows = []
spec_id = 0
year_filters = ["all", 2004, 2009, 2014, 2019]
party_filters = ["all", "national", "regional", "independent"]
seat_filters = ["all", "general", "sc", "st"]
winnable_thresholds = [25, 30, 35, 40]
control_sets = {
    "minimal": ["EDU_NUM"],
    "year": ["EDU_NUM", "YEAR_2009", "YEAR_2014", "YEAR_2019"],
    "full": ["INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM",
             "IS_PROFESSIONAL", "IS_BUSINESS", "IS_AGRICULTURE",
             "YEAR_2009", "YEAR_2014", "YEAR_2019"],
}

for ctrl_name, controls in control_sets.items():
    for wt in winnable_thresholds:
        tmp = df.copy()
        tmp["WINNABLE_SPEC"] = (tmp["EXPECTED_VOTE_SHARE"] > wt).astype(int)
        for yf in year_filters:
            sub = tmp if yf == "all" else tmp[tmp["Year"] == yf]
            for pf in party_filters:
                sub2 = sub
                if pf == "national":
                    sub2 = sub2[sub2["NATIONAL_PARTY"] == 1]
                elif pf == "regional":
                    sub2 = sub2[sub2["NATIONAL_PARTY"] == 0]
                elif pf == "independent":
                    sub2 = sub2[sub2["IS_INDEPENDENT"] == 1]
                for sf in seat_filters:
                    sub3 = sub2
                    if sf == "general":
                        sub3 = sub3[sub3["SEAT_TYPE"] == "General"]
                    elif sf == "sc":
                        sub3 = sub3[sub3["SEAT_TYPE"] == "SC Reserved"]
                    elif sf == "st":
                        sub3 = sub3[sub3["SEAT_TYPE"] == "ST Reserved"]
                    if len(sub3) < 100 or sub3["FEMALE"].sum() < 10:
                        continue
                    try:
                        c = controls + ["WINNABLE_SPEC"]
                        c = list(dict.fromkeys(c))
                        coef, se, p, lo, hi, r2, n = fit_ols_female(sub3, c)
                    except Exception:
                        continue
                    spec_id += 1
                    spec_rows.append({
                        "spec_id": spec_id,
                        "controls": ctrl_name,
                        "year_filter": yf,
                        "party_filter": pf,
                        "seat_filter": sf,
                        "winnable_threshold": wt,
                        "female_coef": coef,
                        "female_se": se,
                        "female_p": p,
                        "ci_lower": lo,
                        "ci_upper": hi,
                        "n": n,
                    })

curve = pd.DataFrame(spec_rows)
curve.to_csv(OUTPUT_DIR / "extended_spec_curve.csv", index=False)

summary = pd.DataFrame([{
    "n_specifications": len(curve),
    "median_female_coef": curve["female_coef"].median(),
    "mean_female_coef": curve["female_coef"].mean(),
    "share_p_lt_0_05": (curve["female_p"] < 0.05).mean(),
    "share_ci_includes_zero": ((curve["ci_lower"] <= 0) & (curve["ci_upper"] >= 0)).mean(),
    "coef_5th_pct": curve["female_coef"].quantile(0.05),
    "coef_95th_pct": curve["female_coef"].quantile(0.95),
}])
summary.to_csv(OUTPUT_DIR / "extended_spec_curve_summary.csv", index=False)
print(f"  {len(curve)} specifications")
print(f"  Median coef: {summary['median_female_coef'].iloc[0]:.4f}")
print(f"  Significant at 0.05: {summary['share_p_lt_0_05'].iloc[0]*100:.1f}%")
print(f"  CI includes zero: {summary['share_ci_includes_zero'].iloc[0]*100:.1f}%")

# ============================================================
# 9. PLACEBO TESTS
# ============================================================
print("\n" + "=" * 60)
print("PLACEBO TESTS")
print("=" * 60)

rng = np.random.default_rng(42)
controls_full = ["INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM",
                  "IS_PROFESSIONAL", "IS_BUSINESS", "IS_AGRICULTURE",
                  "YEAR_2009", "YEAR_2014", "YEAR_2019"]
obs_coef, obs_se, obs_p, _, _, _, _ = fit_ols_female(df, controls_full)

perm_rows = []
n_perm = 200
for i in range(n_perm):
    tmp = df.copy()
    tmp["FEMALE"] = rng.permutation(tmp["FEMALE"].values)
    coef, se, p, _, _, _, _ = fit_ols_female(tmp, controls_full)
    perm_rows.append({"iteration": i, "female_coef": coef, "p_value": p})

perm = pd.DataFrame(perm_rows)
perm_p = (np.abs(perm["female_coef"]) >= abs(obs_coef)).mean()
print(f"  Observed coef: {obs_coef:.4f} (p={obs_p:.4f})")
print(f"  Permutation p (2-sided): {perm_p:.3f}")

placebo = pd.DataFrame([{
    "test": "gender_permutation_2004_2019",
    "observed_coef": round(obs_coef, 4),
    "observed_p": round(obs_p, 4),
    "permutation_p": round(perm_p, 4),
    "n_perm": n_perm,
}])
placebo.to_csv(OUTPUT_DIR / "extended_placebo_tests.csv", index=False)

# ============================================================
# 10. SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

summary_data = {
    "n_total": len(df),
    "n_female": int(df["FEMALE"].sum()),
    "female_pct": round(df["FEMALE"].mean() * 100, 1),
    "years_covered": str(sorted(df["Year"].unique().tolist())),
    "female_pct_by_year": str({int(y): round(df.loc[df["Year"]==y, "FEMALE"].mean()*100, 1) for y in sorted(df["Year"].unique())}),
}
pd.Series(summary_data).to_csv(OUTPUT_DIR / "extended_summary.csv")
print(pd.Series(summary_data).to_string())
print("\nDone. Extended analysis outputs saved to experiments/results/.")
