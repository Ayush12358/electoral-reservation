"""Gender x pre-treatment moderator models on the corrected capability dataset."""

import pandas as pd
import statsmodels.api as sm
from pathlib import Path

OUTPUT_DIR = Path("experiments/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(OUTPUT_DIR / "analysis_with_controls.csv", low_memory=False)
df["EDU_NUM"] = df["EDU_NUM"].fillna(0)

interactions = [
    ("Education", "EDU_NUM", "Female x EDU_NUM"),
    ("Assets", "LOG_ASSETS", "Female x LOG_ASSETS"),
    ("Party Type", "NATIONAL_PARTY", "Female x NATIONAL_PARTY"),
    ("Seat Type", "IS_SC", "Female x IS_SC"),
    ("Seat Type", "IS_ST", "Female x IS_ST"),
    ("Winnability", "WINNABLE", "Female x WINNABLE"),
]

rows = []
for model_name, moderator, label in interactions:
    tmp = df.copy()
    inter_col = f"FEMALE_X_{moderator}"
    tmp[inter_col] = tmp["FEMALE"] * tmp[moderator]
    cols = ["FEMALE", moderator, inter_col, "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "YEAR_2009"]
    # Avoid exact duplicate columns when moderator is also a control.
    cols = list(dict.fromkeys(cols))
    X = sm.add_constant(tmp[cols].astype(float))
    y = tmp["CAPABILITY"].astype(float)
    m = sm.OLS(y, X).fit(cov_type="HC3")
    ci = m.conf_int().loc[inter_col]
    rows.append({
        "Model": model_name,
        "Term": label,
        "Coef": round(m.params[inter_col], 4),
        "SE": round(m.bse[inter_col], 4),
        "p_value": round(m.pvalues[inter_col], 4),
        "CI_lower": round(ci[0], 4),
        "CI_upper": round(ci[1], 4),
        "N": int(m.nobs),
        "R2": round(m.rsquared, 4),
        "Female_main": round(m.params["FEMALE"], 4),
    })

# Combined education/assets moderation model.
tmp = df.copy()
tmp["FEMALE_EDU"] = tmp["FEMALE"] * tmp["EDU_NUM"]
tmp["FEMALE_ASSETS"] = tmp["FEMALE"] * tmp["LOG_ASSETS"]
cols = ["FEMALE", "EDU_NUM", "LOG_ASSETS", "FEMALE_EDU", "FEMALE_ASSETS", "HAS_CRIMINAL", "YEAR_2009"]
X = sm.add_constant(tmp[cols].astype(float))
y = tmp["CAPABILITY"].astype(float)
m = sm.OLS(y, X).fit(cov_type="HC3")
for term in ["FEMALE_EDU", "FEMALE_ASSETS"]:
    ci = m.conf_int().loc[term]
    rows.append({
        "Model": "Combined",
        "Term": term,
        "Coef": round(m.params[term], 4),
        "SE": round(m.bse[term], 4),
        "p_value": round(m.pvalues[term], 4),
        "CI_lower": round(ci[0], 4),
        "CI_upper": round(ci[1], 4),
        "N": int(m.nobs),
        "R2": round(m.rsquared, 4),
        "Female_main": round(m.params["FEMALE"], 4),
    })

out = pd.DataFrame(rows)
out.to_csv(OUTPUT_DIR / "interaction_model.csv", index=False)
print(out.to_string(index=False))
print(f"Saved: {OUTPUT_DIR / 'interaction_model.csv'}")
