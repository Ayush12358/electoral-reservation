"""Predictive validation: does 2004 capability predict 2009 renomination?

Uses the corrected shared pipeline. Vote shares/residuals are computed on full
parliament results before MyNeta matching, and the validation sample is restricted
to exact one-row matched 2004 candidates with controls.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss, classification_report
from sklearn.model_selection import StratifiedKFold

from electoral_pipeline import OUTPUT_DIR, add_expected_vote_share, build_analysis_dataset, load_parliament

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SEED = 42

print("Building validation sample...")
df, _ = build_analysis_dataset()
full = add_expected_vote_share(load_parliament())
candidates_2009 = set(full.loc[full["YEAR"] == 2009, "NAME_CLEAN"])

d = df[df["YEAR"] == 2004].copy()
d["RENOMINATED_2009"] = d["NAME_CLEAN"].isin(candidates_2009).astype(int)
d["EDU_NUM"] = d["EDU_NUM"].fillna(0)

print(f"  2004 matched candidates: {len(d)}")
print(f"  Female: {d['FEMALE'].sum()} ({d['FEMALE'].mean()*100:.1f}%)")
print(f"  Renominated: {d['RENOMINATED_2009'].sum()} ({d['RENOMINATED_2009'].mean()*100:.1f}%)")

# Logit models
models = {}
y = d["RENOMINATED_2009"].astype(int)
for name, cols in {
    "bivariate_capability": ["CAPABILITY"],
    "capability_plus_gender": ["CAPABILITY", "FEMALE"],
    "full_controls": ["CAPABILITY", "FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"],
}.items():
    X = sm.add_constant(d[cols].astype(float), has_constant="add")
    models[name] = sm.Logit(y, X).fit(disp=0)

m = models["full_controls"]
print(m.summary().tables[1])

# In-sample and CV predictive metrics
cols = ["CAPABILITY", "FEMALE", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]
X_all = d[cols].astype(float).fillna(0)
d["PRED_PROB"] = m.predict(sm.add_constant(X_all, has_constant="add"))
auc = roc_auc_score(y, d["PRED_PROB"])
brier = brier_score_loss(y, d["PRED_PROB"])

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
cv_aucs, cv_briers = [], []
for fold, (tr, te) in enumerate(skf.split(X_all, y), start=1):
    lr = LogisticRegression(max_iter=1000, solver="lbfgs")
    lr.fit(X_all.iloc[tr], y.iloc[tr])
    p = lr.predict_proba(X_all.iloc[te])[:, 1]
    fold_auc = roc_auc_score(y.iloc[te], p)
    cv_aucs.append(fold_auc)
    cv_briers.append(brier_score_loss(y.iloc[te], p))
    print(f"  Fold {fold}: AUC={fold_auc:.4f}, Brier={cv_briers[-1]:.4f}")

median_cap = d["CAPABILITY"].median()
high = d[d["CAPABILITY"] >= median_cap]
low = d[d["CAPABILITY"] < median_cap]

results = {
    "n_2004_candidates": len(d),
    "n_renominated": int(y.sum()),
    "renomination_rate": round(y.mean() * 100, 1),
    "renomination_rate_female": round(d.loc[d["FEMALE"] == 1, "RENOMINATED_2009"].mean() * 100, 1),
    "renomination_rate_male": round(d.loc[d["FEMALE"] == 0, "RENOMINATED_2009"].mean() * 100, 1),
    "capability_coef": round(m.params["CAPABILITY"], 4),
    "capability_se": round(m.bse["CAPABILITY"], 4),
    "capability_p": round(m.pvalues["CAPABILITY"], 4),
    "capability_or": round(np.exp(m.params["CAPABILITY"]), 4),
    "gender_coef": round(m.params["FEMALE"], 4),
    "gender_p": round(m.pvalues["FEMALE"], 4),
    "auc": round(auc, 4),
    "brier": round(brier, 4),
    "cv_auc_mean": round(float(np.mean(cv_aucs)), 4),
    "cv_auc_se": round(float(np.std(cv_aucs, ddof=1) / np.sqrt(len(cv_aucs))), 4),
    "cv_brier_mean": round(float(np.mean(cv_briers)), 4),
    "cv_brier_se": round(float(np.std(cv_briers, ddof=1) / np.sqrt(len(cv_briers))), 4),
    "cv_auc_folds": str({i + 1: round(v, 4) for i, v in enumerate(cv_aucs)}),
    "high_cap_renomination": round(high["RENOMINATED_2009"].mean() * 100, 1),
    "low_cap_renomination": round(low["RENOMINATED_2009"].mean() * 100, 1),
    "female_high_cap_renomination": round(high.loc[high["FEMALE"] == 1, "RENOMINATED_2009"].mean() * 100, 1),
    "female_low_cap_renomination": round(low.loc[low["FEMALE"] == 1, "RENOMINATED_2009"].mean() * 100, 1),
}

pd.Series(results).to_csv(OUTPUT_DIR / "validation_renomination.csv")
d.to_csv(OUTPUT_DIR / "validation_dataset.csv", index=False)
print(pd.Series(results).to_string())
print(f"Saved: {OUTPUT_DIR / 'validation_renomination.csv'}")
