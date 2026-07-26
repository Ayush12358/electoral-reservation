"""
SC/ST Reservation and Capability Analysis
Tests whether seat reservation for SC/ST candidates affects:
1. Capability distribution across SC/ST vs General candidates
2. Gender gaps within reserved seats
3. Whether reservation is associated with different candidate quality
"""

import pandas as pd
import numpy as np
import statsmodels.api as sm
from pathlib import Path

DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("experiments/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. LOAD AND PREPARE (same pipeline as main analysis)
# ============================================================

print("Loading data...")
df = pd.read_csv(OUTPUT_DIR / "analysis_with_controls.csv", low_memory=False)
print(f"  Loaded: {len(df)} observations")

# ============================================================
# 2. CATEGORY DISTRIBUTION
# ============================================================

print("\n" + "="*60)
print("CATEGORY DISTRIBUTION")
print("="*60)

df["CATEGORY_CLEAN"] = df["CATEGORY"].str.strip().str.upper().fillna("UNKNOWN")
cat_counts = df["CATEGORY_CLEAN"].value_counts()
print(f"\nCategory counts:")
for cat, cnt in cat_counts.items():
    female_cnt = df[(df["CATEGORY_CLEAN"] == cat) & (df["FEMALE"] == 1)].shape[0]
    print(f"  {cat}: {cnt} total, {female_cnt} female ({female_cnt/cnt*100:.1f}%)")

# ============================================================
# 3. CAPABILITY BY CATEGORY
# ============================================================

print("\n" + "="*60)
print("CAPABILITY BY CATEGORY")
print("="*60)

for cat in ["GEN", "SC", "ST"]:
    subset = df[df["CATEGORY_CLEAN"] == cat]
    cap_mean = subset["CAPABILITY"].mean()
    cap_median = subset["CAPABILITY"].median()
    cap_sd = subset["CAPABILITY"].std()
    n = len(subset)
    f_mean = subset[subset["FEMALE"] == 1]["CAPABILITY"].mean() if subset["FEMALE"].sum() > 0 else None
    m_mean = subset[subset["FEMALE"] == 0]["CAPABILITY"].mean() if (subset["FEMALE"] == 0).sum() > 0 else None
    print(f"\n  {cat} (n={n}):")
    print(f"    Capability: mean={cap_mean:.4f}, median={cap_median:.4f}, SD={cap_sd:.4f}")
    if f_mean is not None and m_mean is not None:
        gap = f_mean - m_mean
        print(f"    Female mean={f_mean:.4f}, Male mean={m_mean:.4f}, Gap={gap:.4f}")

# ============================================================
# 4. REGRESSION: CAPABILITY ~ SC/ST + GENDER INTERACTIONS
# ============================================================

print("\n" + "="*60)
print("REGRESSION: Capability ~ SC/ST Category + Gender")
print("="*60)

y = df["CAPABILITY"].values

# Model 1: Category effects (SC, ST vs GEN baseline)
X1 = df[["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]].copy()
X1["IS_SC"] = (df["CATEGORY_CLEAN"] == "SC").astype(int)
X1["IS_ST"] = (df["CATEGORY_CLEAN"] == "ST").astype(int)
X1["EDU_NUM"] = X1["EDU_NUM"].fillna(0)
X1 = sm.add_constant(X1)

model1 = sm.OLS(y, X1).fit(cov_type="HC3")
print(f"\nModel 1: Category main effects")
print(f"{'Variable':<20} {'Coef':>8} {'SE':>8} {'p':>8} {'95% CI':>20}")
print("-" * 64)
for var in X1.columns:
    ci = model1.conf_int().loc[var]
    print(f"{var:<20} {model1.params[var]:>8.4f} {model1.bse[var]:>8.4f} {model1.pvalues[var]:>8.4f}  [{ci[0]:>7.4f}, {ci[1]:>7.4f}]")

# Model 2: Category × Gender interactions
X2 = X1.copy()
X2["FEMALE_SC"] = df["FEMALE"] * (df["CATEGORY_CLEAN"] == "SC").astype(int)
X2["FEMALE_ST"] = df["FEMALE"] * (df["CATEGORY_CLEAN"] == "ST").astype(int)
model2 = sm.OLS(y, X2).fit(cov_type="HC3")
print(f"\nModel 2: Category × Gender interactions")
print(f"{'Variable':<20} {'Coef':>8} {'SE':>8} {'p':>8} {'95% CI':>20}")
print("-" * 64)
for var in X2.columns:
    ci = model2.conf_int().loc[var]
    print(f"{var:<20} {model2.params[var]:>8.4f} {model2.bse[var]:>8.4f} {model2.pvalues[var]:>8.4f}  [{ci[0]:>7.4f}, {ci[1]:>7.4f}]")

# Model 3: Within-category gender gaps
print(f"\nModel 3: Within-category gender gaps")
for cat in ["GEN", "SC", "ST"]:
    subset = df[df["CATEGORY_CLEAN"] == cat]
    if len(subset) < 50 or subset["FEMALE"].sum() < 5:
        print(f"  {cat}: too few observations (n={len(subset)}, female={subset['FEMALE'].sum()})")
        continue
    y_sub = subset["CAPABILITY"].values
    X_sub = subset[["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]].copy()
    X_sub["EDU_NUM"] = X_sub["EDU_NUM"].fillna(0)
    X_sub = sm.add_constant(X_sub)
    m = sm.OLS(y_sub, X_sub).fit(cov_type="HC3")
    ci = m.conf_int().loc["FEMALE"]
    print(f"  {cat} (n={len(subset)}): Female={m.params['FEMALE']:.4f} (SE={m.bse['FEMALE']:.4f}, p={m.pvalues['FEMALE']:.4f})")
    print(f"    95% CI: [{ci[0]:.4f}, {ci[1]:.4f}], female n={subset['FEMALE'].sum()}")

# ============================================================
# 5. DESCRIPTIVE: Candidate characteristics by category
# ============================================================

print("\n" + "="*60)
print("CANDIDATE CHARACTERISTICS BY CATEGORY")
print("="*60)

for cat in ["GEN", "SC", "ST"]:
    subset = df[df["CATEGORY_CLEAN"] == cat]
    print(f"\n  {cat}:")
    for col in ["CAPABILITY", "VOTE_SHARE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]:
        f_mean = subset[subset["FEMALE"] == 1][col].mean() if subset["FEMALE"].sum() > 0 else None
        m_mean = subset[subset["FEMALE"] == 0][col].mean()
        if f_mean is not None:
            print(f"    {col:<15}: Female={f_mean:.4f}, Male={m_mean:.4f}, Gap={f_mean-m_mean:.4f}")
        else:
            print(f"    {col:<15}: Male={m_mean:.4f}")

# ============================================================
# 6. SAVE RESULTS
# ============================================================

results = []
for var in X2.columns:
    ci = model2.conf_int().loc[var]
    results.append({
        "Model": "Category × Gender",
        "Variable": var,
        "Coef": round(model2.params[var], 4),
        "SE": round(model2.bse[var], 4),
        "p_value": round(model2.pvalues[var], 4),
        "CI_lower": round(ci[0], 4),
        "CI_upper": round(ci[1], 4),
    })
pd.DataFrame(results).to_csv(OUTPUT_DIR / "sc_st_analysis.csv", index=False)
print(f"\nSaved: {OUTPUT_DIR / 'sc_st_analysis.csv'}")
