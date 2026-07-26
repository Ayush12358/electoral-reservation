"""Heterogeneity analysis for the corrected capability dataset."""

import pandas as pd
import statsmodels.api as sm
from pathlib import Path

OUTPUT_DIR = Path("experiments/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

path = OUTPUT_DIR / "analysis_with_controls.csv"
if not path.exists():
    raise FileNotFoundError("Run experiments/analysis_with_controls.py first")

df = pd.read_csv(path, low_memory=False)
df["EDU_NUM"] = df["EDU_NUM"].fillna(0)


def run_subset(label, subset, dimension):
    if len(subset) < 50 or subset["FEMALE"].sum() < 5:
        return None
    y = subset["CAPABILITY"].astype(float)
    X = subset[["FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]].astype(float)
    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit(cov_type="HC3")
    ci = model.conf_int().loc["FEMALE"]
    return {
        "Subset": label,
        "N": int(model.nobs),
        "N_female": int(subset["FEMALE"].sum()),
        "Female_Coef": round(model.params["FEMALE"], 4),
        "SE": round(model.bse["FEMALE"], 4),
        "P_value": round(model.pvalues["FEMALE"], 4),
        "CI_lower": round(ci[0], 4),
        "CI_upper": round(ci[1], 4),
        "Dimension": dimension,
    }

rows = []
for year in sorted(df["YEAR"].dropna().unique()):
    rows.append(run_subset(str(int(year)), df[df["YEAR"] == year], "Year"))
rows.append(run_subset("Party: National", df[df["NATIONAL_PARTY"] == 1], "Party Type"))
rows.append(run_subset("Party: Regional/Other", df[df["NATIONAL_PARTY"] == 0], "Party Type"))
for seat_type in ["General", "SC Reserved", "ST Reserved"]:
    rows.append(run_subset(f"Seat: {seat_type}", df[df["SEAT_TYPE"] == seat_type], "Seat Type"))
rows.append(run_subset("Seat: Winnable", df[df["WINNABLE"] == 1], "Winnable"))
rows.append(run_subset("Seat: Non-Winnable", df[df["WINNABLE"] == 0], "Winnable"))
median_cap = df["CAPABILITY"].median()
rows.append(run_subset("Capability: High Capability", df[df["CAPABILITY"] >= median_cap], "Capability Level"))
rows.append(run_subset("Capability: Low Capability", df[df["CAPABILITY"] < median_cap], "Capability Level"))
rows.append(run_subset("Full Sample", df, "Full"))

out = pd.DataFrame([r for r in rows if r is not None])
out.to_csv(OUTPUT_DIR / "heterogeneity.csv", index=False)
print(out.to_string(index=False))
print(f"Saved: {OUTPUT_DIR / 'heterogeneity.csv'}")
