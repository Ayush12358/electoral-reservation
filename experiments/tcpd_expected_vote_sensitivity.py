"""TCPD Lok Sabha expected-vote-share sensitivity analysis.

This script benchmarks the current deterministic party-constituency/state baseline
against a linear fixed-effects surrogate, RandomForestRegressor, and a gradient-
boosting surrogate (HistGradientBoostingRegressor; xgboost is not available in the
current environment).

Design choices:
- Rolling cumulative training: for each held-out election year, train on all prior
  years available in the TCPD GE file.
- No leakage: predictors only use lagged historical aggregates and pre-election
  candidate/seat attributes; same-year vote share, winner, margin, turnout, and
  other target-like fields are excluded.
- High-cardinality constituency dummies are intentionally avoided. Historical
  constituency information enters through lagged constituency-party averages.

Outputs are written to experiments/results/.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from tcpd_pipeline import OUTPUT_DIR, fit_ols_female, load_tcpd_ge

SEED = 42
rng = np.random.default_rng(SEED)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_YEARS = [2004, 2009, 2014, 2019]
ANALYSIS_PREV_MAP = {2004: 1999, 2009: 2004, 2014: 2009, 2019: 2014}

CATEGORICAL_FEATURES = ["STATE_CLEAN", "SEAT_TYPE", "Party_Type_TCPD"]
NUMERIC_FEATURES = [
    "LAG_PC_PARTY_SHARE",
    "LAG_STATE_PARTY_SHARE",
    "LAG_PARTY_SHARE",
    "LAG_STATE_SHARE",
    "LAG_GLOBAL_MEAN",
    "LAG_PC_PARTY_N",
    "LAG_STATE_PARTY_N",
    "LAG_PARTY_N",
    "LAG_STATE_N",
    "INCUMBENT",
    "RECONTEST",
    "TURNCOAT",
    "NO_TERMS",
    "NATIONAL_PARTY",
    "IS_INDEPENDENT",
    "EDU_NUM",
    "IS_PROFESSIONAL",
    "IS_BUSINESS",
    "IS_AGRICULTURE",
    "IS_POLITICS",
    "POST_DELIMITATION",
]
LEAKY_COLUMNS = {
    "Vote_Share_Percentage",
    "Votes",
    "Valid_Votes",
    "Electors",
    "Turnout_Percentage",
    "Margin",
    "Margin_Percentage",
    "Position",
    "WINNER",
}


def make_one_hot_preprocessor() -> ColumnTransformer:
    """Dense one-hot + median-imputed numeric features."""
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="Missing")),
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                min_frequency=10,
                                sparse_output=False,
                                dtype=np.float32,
                            ),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "num",
                SimpleImputer(strategy="median"),
                NUMERIC_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def build_lag_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Add lagged historical aggregates and a deterministic baseline prediction.

    The previous election-year aggregates are computed from the immediately prior
    unique year in the TCPD file, mirroring the existing deterministic baseline.
    """
    df = df.copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year"]).copy()
    df["Year"] = df["Year"].astype(int)

    # Restrict to the Lok Sabha years up to 2019.
    df = df[df["Year"] <= 2019].copy()

    # Sanity checks: exclude obvious leakage columns from the predictor set.
    if LEAKY_COLUMNS.intersection(df.columns):
        pass  # only a guardrail; the model feature list below excludes them.

    years = sorted(df["Year"].unique())
    frames = []
    prev_year = None

    for year in years:
        cur = df[df["Year"] == year].copy()
        if prev_year is None:
            for col in [
                "LAG_PC_PARTY_SHARE",
                "LAG_STATE_PARTY_SHARE",
                "LAG_PARTY_SHARE",
                "LAG_STATE_SHARE",
                "LAG_GLOBAL_MEAN",
                "LAG_PC_PARTY_N",
                "LAG_STATE_PARTY_N",
                "LAG_PARTY_N",
                "LAG_STATE_N",
                "BASELINE_EXPECTED_SHARE",
                "BASELINE_SOURCE",
                "PREV_YEAR",
            ]:
                cur[col] = np.nan
        else:
            prev = df[df["Year"] == prev_year].copy()
            global_mean = prev["Vote_Share_Percentage"].mean()

            agg_state = prev.groupby("STATE_CLEAN", observed=True).agg(
                LAG_STATE_SHARE=("Vote_Share_Percentage", "mean"),
                LAG_STATE_N=("Vote_Share_Percentage", "size"),
            ).reset_index()
            agg_party = prev.groupby("PARTY_CLEAN", observed=True).agg(
                LAG_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
                LAG_PARTY_N=("Vote_Share_Percentage", "size"),
            ).reset_index()
            agg_state_party = prev.groupby(["STATE_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                LAG_STATE_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
                LAG_STATE_PARTY_N=("Vote_Share_Percentage", "size"),
            ).reset_index()
            agg_pc_party = prev.groupby(["PC_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                LAG_PC_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
                LAG_PC_PARTY_N=("Vote_Share_Percentage", "size"),
            ).reset_index()

            cur["PREV_YEAR"] = prev_year
            cur["LAG_GLOBAL_MEAN"] = global_mean
            cur = cur.merge(agg_state, on="STATE_CLEAN", how="left")
            cur = cur.merge(agg_party, on="PARTY_CLEAN", how="left")
            cur = cur.merge(agg_state_party, on=["STATE_CLEAN", "PARTY_CLEAN"], how="left")
            cur = cur.merge(agg_pc_party, on=["PC_CLEAN", "PARTY_CLEAN"], how="left")

            cur["BASELINE_EXPECTED_SHARE"] = (
                cur["LAG_PC_PARTY_SHARE"]
                .fillna(cur["LAG_STATE_PARTY_SHARE"])
                .fillna(cur["LAG_PARTY_SHARE"])
                .fillna(cur["LAG_STATE_SHARE"])
                .fillna(global_mean)
            )
            cur["BASELINE_SOURCE"] = np.select(
                [
                    cur["LAG_PC_PARTY_SHARE"].notna(),
                    cur["LAG_STATE_PARTY_SHARE"].notna(),
                    cur["LAG_PARTY_SHARE"].notna(),
                    cur["LAG_STATE_SHARE"].notna(),
                ],
                [
                    "party-constituency",
                    "party-state",
                    "party-national",
                    "state",
                ],
                default="global_mean",
            )

        frames.append(cur)
        prev_year = year

    out = pd.concat(frames, ignore_index=True)
    out["EDU_NUM"] = out["EDU_NUM"].fillna(0)
    out["BASELINE_AVAILABLE"] = out["BASELINE_EXPECTED_SHARE"].notna().astype(int)
    out["BASELINE_RESIDUAL"] = out["Vote_Share_Percentage"] - out["BASELINE_EXPECTED_SHARE"]
    out["WINNABLE"] = (out["BASELINE_EXPECTED_SHARE"].fillna(0) > 35).astype(int)
    return out


def build_model_pipeline(estimator):
    preprocessor = make_one_hot_preprocessor()
    return Pipeline([
        ("prep", preprocessor),
        ("model", estimator),
    ])


def add_analysis_baseline(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute the paper's baseline expected share using prior *analysis* year.

    This differs from the rolling lag panel above, which uses the immediately
    previous unique year. The baseline here uses the prior Lok Sabha election in
    the manuscript's analysis sequence: 1999 -> 2004 -> 2009 -> 2014 -> 2019.
    """
    panel = panel.copy()
    panel["ANALYSIS_BASELINE_EXPECTED_SHARE"] = np.nan
    panel["ANALYSIS_BASELINE_SOURCE"] = pd.Series([None] * len(panel), index=panel.index, dtype="object")

    for year, prev_year in ANALYSIS_PREV_MAP.items():
        if year not in panel["Year"].values or prev_year not in panel["Year"].values:
            continue
        prev = panel[panel["Year"] == prev_year].copy()
        cur = panel[panel["Year"] == year].copy()
        global_mean = prev["Vote_Share_Percentage"].mean()
        agg_state = prev.groupby("STATE_CLEAN", observed=True).agg(
            ANALYSIS_LAG_STATE_SHARE=("Vote_Share_Percentage", "mean"),
            ANALYSIS_LAG_STATE_N=("Vote_Share_Percentage", "size"),
        ).reset_index()
        agg_party = prev.groupby("PARTY_CLEAN", observed=True).agg(
            ANALYSIS_LAG_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
            ANALYSIS_LAG_PARTY_N=("Vote_Share_Percentage", "size"),
        ).reset_index()
        agg_state_party = prev.groupby(["STATE_CLEAN", "PARTY_CLEAN"], observed=True).agg(
            ANALYSIS_LAG_STATE_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
            ANALYSIS_LAG_STATE_PARTY_N=("Vote_Share_Percentage", "size"),
        ).reset_index()
        agg_pc_party = prev.groupby(["PC_CLEAN", "PARTY_CLEAN"], observed=True).agg(
            ANALYSIS_LAG_PC_PARTY_SHARE=("Vote_Share_Percentage", "mean"),
            ANALYSIS_LAG_PC_PARTY_N=("Vote_Share_Percentage", "size"),
        ).reset_index()
        cur = cur.merge(agg_state, on="STATE_CLEAN", how="left")
        cur = cur.merge(agg_party, on="PARTY_CLEAN", how="left")
        cur = cur.merge(agg_state_party, on=["STATE_CLEAN", "PARTY_CLEAN"], how="left")
        cur = cur.merge(agg_pc_party, on=["PC_CLEAN", "PARTY_CLEAN"], how="left")
        cur["ANALYSIS_BASELINE_EXPECTED_SHARE"] = (
            cur["ANALYSIS_LAG_PC_PARTY_SHARE"]
            .fillna(cur["ANALYSIS_LAG_STATE_PARTY_SHARE"])
            .fillna(cur["ANALYSIS_LAG_PARTY_SHARE"])
            .fillna(cur["ANALYSIS_LAG_STATE_SHARE"])
            .fillna(global_mean)
        )
        cur["ANALYSIS_BASELINE_SOURCE"] = np.select(
            [
                cur["ANALYSIS_LAG_PC_PARTY_SHARE"].notna(),
                cur["ANALYSIS_LAG_STATE_PARTY_SHARE"].notna(),
                cur["ANALYSIS_LAG_PARTY_SHARE"].notna(),
                cur["ANALYSIS_LAG_STATE_SHARE"].notna(),
            ],
            ["party-constituency", "party-state", "party-national", "state"],
            default="global_mean",
        )
        mask = panel["Year"] == year
        panel.loc[mask, "ANALYSIS_BASELINE_EXPECTED_SHARE"] = cur["ANALYSIS_BASELINE_EXPECTED_SHARE"].to_numpy()
        panel.loc[mask, "ANALYSIS_BASELINE_SOURCE"] = cur["ANALYSIS_BASELINE_SOURCE"].to_numpy()

    panel["ANALYSIS_BASELINE_AVAILABLE"] = panel["ANALYSIS_BASELINE_EXPECTED_SHARE"].notna().astype(int)
    panel["ANALYSIS_WINNABLE"] = (panel["ANALYSIS_BASELINE_EXPECTED_SHARE"].fillna(0) > 35).astype(int)
    panel["ANALYSIS_BASELINE_RESIDUAL"] = panel["Vote_Share_Percentage"] - panel["ANALYSIS_BASELINE_EXPECTED_SHARE"]
    return panel


def safe_corr(x, y, method="spearman"):
    try:
        if method == "spearman":
            val = spearmanr(x, y, nan_policy="omit").correlation
        else:
            val = pearsonr(x, y)[0]
        return float(val)
    except Exception:
        return np.nan


def top_decile_overlap(a, b):
    a = pd.Series(a)
    b = pd.Series(b)
    n = max(1, int(math.ceil(0.10 * len(a))))
    top_a = set(a.nlargest(n).index)
    top_b = set(b.nlargest(n).index)
    if not top_a or not top_b:
        return np.nan
    return len(top_a.intersection(top_b)) / n


def evaluate_models(panel: pd.DataFrame):
    feature_cols = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    assert not LEAKY_COLUMNS.intersection(feature_cols), "Leak-prone columns in feature set"

    model_specs = {
        "linear_fe_ridge": Ridge(alpha=1.0, random_state=None),
        "random_forest": RandomForestRegressor(
            n_estimators=250,
            max_depth=12,
            min_samples_leaf=10,
            max_features="sqrt",
            random_state=SEED,
            # Single-threaded fitting makes the frozen sensitivity artifacts
            # byte-stable across repeated runs with the fixed random seed.
            n_jobs=1,
        ),
        "hist_gbdt": HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.05,
            max_depth=6,
            min_samples_leaf=20,
            random_state=SEED,
        ),
    }

    prediction_rows = []
    metric_rows = []
    rank_rows = []
    gender_rows = []

    for test_year in TARGET_YEARS:
        test = panel[panel["Year"] == test_year].copy()
        train = panel[panel["Year"] < test_year].copy()
        if train.empty or test.empty:
            continue

        train_X = train[feature_cols]
        train_y = train["Vote_Share_Percentage"].astype(float)
        test_X = test[feature_cols]
        test_y = test["Vote_Share_Percentage"].astype(float)

        # Baseline deterministic model.
        preds = {
            "baseline_formula": test["ANALYSIS_BASELINE_EXPECTED_SHARE"].astype(float).values,
        }

        # Learned models.
        for name, estimator in model_specs.items():
            pipe = build_model_pipeline(estimator)
            pipe.fit(train_X, train_y)
            preds[name] = pipe.predict(test_X)

        # Row-level predictions.
        out = test[[
            "Year", "State_Name", "Constituency_Name", "Party", "Sex", "FEMALE",
            "Vote_Share_Percentage", "ANALYSIS_BASELINE_EXPECTED_SHARE", "ANALYSIS_BASELINE_SOURCE",
            "INCUMBENT", "RECONTEST", "TURNCOAT", "NO_TERMS", "NATIONAL_PARTY",
            "IS_INDEPENDENT", "EDU_NUM", "IS_PROFESSIONAL", "IS_BUSINESS",
            "IS_AGRICULTURE", "IS_POLITICS", "POST_DELIMITATION", "ANALYSIS_WINNABLE",
        ]].copy()
        for name, pred in preds.items():
            out[f"PRED_{name}"] = pred
            out[f"RESID_{name}"] = out["Vote_Share_Percentage"] - out[f"PRED_{name}"]
        prediction_rows.append(out)

        # Per-model metrics for this held-out year.
        for name, pred in preds.items():
            resid = test_y - pred
            metric_rows.append({
                "test_year": test_year,
                "model": name,
                "train_n": len(train),
                "test_n": len(test),
                "rmse": math.sqrt(mean_squared_error(test_y, pred)),
                "mae": mean_absolute_error(test_y, pred),
                "r2": r2_score(test_y, pred),
                "pearson_r_pred_vs_actual": safe_corr(pred, test_y, method="pearson"),
                "spearman_r_pred_vs_actual": safe_corr(pred, test_y, method="spearman"),
                "residual_mean": float(np.mean(resid)),
                "residual_sd": float(np.std(resid, ddof=1)),
            })

        # Pairwise residual rank correlations.
        model_names = list(preds.keys())
        resid_df = pd.DataFrame({name: test_y - preds[name] for name in model_names})
        for a, b in itertools.combinations(model_names, 2):
            rank_rows.append({
                "test_year": test_year,
                "model_a": a,
                "model_b": b,
                "spearman_residual_r": safe_corr(resid_df[a], resid_df[b], method="spearman"),
                "pearson_residual_r": safe_corr(resid_df[a], resid_df[b], method="pearson"),
                "top_decile_overlap": top_decile_overlap(resid_df[a], resid_df[b]),
                "n_common": len(resid_df),
            })

        # Gender regression on each model's residuals.
        reg_base = out.copy()
        reg_base["YEAR_2009"] = (reg_base["Year"] == 2009).astype(int)
        reg_base["YEAR_2014"] = (reg_base["Year"] == 2014).astype(int)
        reg_base["YEAR_2019"] = (reg_base["Year"] == 2019).astype(int)

        controls = [
            "INCUMBENT", "RECONTEST", "TURNCOAT", "NO_TERMS",
            "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM",
            "IS_PROFESSIONAL", "IS_BUSINESS", "IS_AGRICULTURE", "IS_POLITICS",
            "POST_DELIMITATION", "YEAR_2009", "YEAR_2014", "YEAR_2019",
        ]

        for name in preds.keys():
            reg_df = reg_base.copy()
            reg_df["CAPABILITY"] = reg_df[f"RESID_{name}"]
            coef, se, p, lo, hi, r2, n = fit_ols_female(reg_df, controls)
            w = reg_df[reg_df["ANALYSIS_WINNABLE"] == 1]
            gender_rows.append({
                "test_years": f"<= {test_year}",
                "test_year": test_year,
                "model": name,
                "female_coef": coef,
                "female_se": se,
                "female_p": p,
                "ci_lower": lo,
                "ci_upper": hi,
                "r2": r2,
                "n": n,
                "n_female": int(reg_df["FEMALE"].sum()),
                "winnable_female_capability": float(w.loc[w["FEMALE"] == 1, "CAPABILITY"].mean()),
                "winnable_male_capability": float(w.loc[w["FEMALE"] == 0, "CAPABILITY"].mean()),
                "winnable_gap": float(
                    w.loc[w["FEMALE"] == 1, "CAPABILITY"].mean() - w.loc[w["FEMALE"] == 0, "CAPABILITY"].mean()
                ),
            })

    pred_df = pd.concat(prediction_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    ranks = pd.DataFrame(rank_rows)
    gender = pd.DataFrame(gender_rows)

    # Summary by model across test years.
    summary = metrics.groupby("model", as_index=False).agg(
        n_years=("test_year", "nunique"),
        mean_rmse=("rmse", "mean"),
        mean_mae=("mae", "mean"),
        mean_r2=("r2", "mean"),
        mean_spearman_pred_actual=("spearman_r_pred_vs_actual", "mean"),
        mean_pearson_pred_actual=("pearson_r_pred_vs_actual", "mean"),
        mean_residual_sd=("residual_sd", "mean"),
    )
    baseline_rmse = summary.loc[summary["model"] == "baseline_formula", "mean_rmse"].iloc[0]
    summary["delta_rmse_vs_baseline"] = summary["mean_rmse"] - baseline_rmse

    return pred_df, metrics, ranks, gender, summary


def write_manifest(panel: pd.DataFrame):
    manifest = {
        "seed": SEED,
        "years_covered": sorted(panel["Year"].unique().tolist()),
        "target_years": TARGET_YEARS,
        "feature_columns": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
        },
        "leaky_columns_excluded": sorted(LEAKY_COLUMNS),
        "notes": [
            "xgboost/lightgbm unavailable; HistGradientBoostingRegressor used as surrogate",
            "Constituency fixed effects are not used directly; historical constituency information enters via lagged constituency-party shares",
            "Baseline formula is the existing deterministic fallback chain: constituency-party -> state-party -> party-national -> state -> global mean",
        ],
    }
    with open(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main():
    print("Loading full TCPD GE history for sensitivity analysis...")
    df = load_tcpd_ge(years=None)
    panel = build_lag_panel(df)
    panel = add_analysis_baseline(panel)
    # Keep only the rows needed for the paper's target years and the prior history
    # used to train them.
    panel = panel[panel["Year"] <= 2019].copy()

    # Basic coverage diagnostics.
    coverage = panel.groupby("Year", as_index=False).agg(
        n=("Vote_Share_Percentage", "size"),
        female_share=("FEMALE", "mean"),
        baseline_available=("ANALYSIS_BASELINE_AVAILABLE", "mean"),
        baseline_mean=("ANALYSIS_BASELINE_EXPECTED_SHARE", "mean"),
    )
    coverage.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_coverage.csv", index=False)

    pred_df, metrics, ranks, gender, summary = evaluate_models(panel)
    pred_df.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_predictions.csv", index=False)
    metrics.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_metrics.csv", index=False)
    ranks.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_rank_correlations.csv", index=False)
    gender.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_gender_effects.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "tcpd_expected_vote_sensitivity_summary.csv", index=False)
    write_manifest(panel)

    print("\n=== SENSITIVITY SUMMARY ===")
    print(summary.round(4).to_string(index=False))
    print("\nSaved sensitivity outputs to experiments/results/.")


if __name__ == "__main__":
    main()
