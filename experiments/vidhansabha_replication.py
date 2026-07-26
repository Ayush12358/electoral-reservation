"""Vidhan Sabha (State Assembly) replication of the electoral capability framework.

Uses TCPD AE data to test whether the framework generalizes beyond Lok Sabha.
Selects the 5 largest states by number of constituencies for tractability.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path

from tcpd_pipeline import OUTPUT_DIR, load_tcpd_ae, fit_ols_female

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. LOAD DATA
# ============================================================
print("Loading TCPD Vidhan Sabha data...")
ae = load_tcpd_ae()
print(f"  Total M/F candidates: {len(ae)}")
print(f"  Years: {sorted(ae['Year'].unique())}")
print(f"  States: {ae['State_Name'].nunique()}")

# Select states with at least 4 elections in the data
state_counts = ae.groupby("State_Name")["Year"].nunique()
states_4plus = state_counts[state_counts >= 4].sort_values(ascending=False)
print(f"\n  States with 4+ elections: {len(states_4plus)}")
for s, c in states_4plus.head(10).items():
    n_cand = len(ae[ae["State_Name"] == s])
    print(f"    {s}: {c} elections, {n_cand} candidates")

# Use the top 5 states for the main analysis
TOP_STATES = states_4plus.head(5).index.tolist()
print(f"\n  Using top 5 states: {TOP_STATES}")

ae_top = ae[ae["State_Name"].isin(TOP_STATES)].copy()
ae_top["PC_CLEAN"] = ae_top["Constituency_Name"].str.strip().str.upper()
ae_top["Party_CLEAN"] = ae_top["Party"].str.strip().str.upper()

# ============================================================
# 2. ADD EXPECTED VOTE SHARE (within each state)
# ============================================================
print("\nAdding expected vote share...")

# For state assembly, we use party-state-constituency baselines
# within each state, computing across all available years
results = []
for state in TOP_STATES:
    state_df = ae_top[ae_top["State_Name"] == state].copy()
    years = sorted(state_df["Year"].unique())

    for i, year in enumerate(years):
        yr_df = state_df[state_df["Year"] == year].copy()

        if i == 0:
            # First election for this state: party-state mean
            party_state = yr_df.groupby("Party_CLEAN", observed=True).agg(
                STATE_AVG_SHARE=("Vote_Share_Percentage", "mean")
            ).reset_index()
            yr_df = yr_df.merge(party_state, on="Party_CLEAN", how="left")
            yr_df["EXPECTED_VOTE_SHARE"] = yr_df["STATE_AVG_SHARE"]
        else:
            prev_year = years[i - 1]
            prev_df = state_df[state_df["Year"] == prev_year]

            # Party-constituency baseline
            party_const = prev_df.groupby(["PC_CLEAN", "Party_CLEAN"], observed=True).agg(
                PARTY_CONST_SHARE=("Vote_Share_Percentage", "mean")
            ).reset_index()
            # Party-state fallback
            party_state = prev_df.groupby("Party_CLEAN", observed=True).agg(
                STATE_AVG_SHARE=("Vote_Share_Percentage", "mean")
            ).reset_index()

            yr_df = yr_df.merge(party_const, on=["PC_CLEAN", "Party_CLEAN"], how="left")
            yr_df = yr_df.merge(party_state, on="Party_CLEAN", how="left")
            yr_df["EXPECTED_VOTE_SHARE"] = yr_df["PARTY_CONST_SHARE"].fillna(yr_df["STATE_AVG_SHARE"])

        results.append(yr_df)

ae_ext = pd.concat(results, ignore_index=True)
ae_ext = ae_ext.dropna(subset=["EXPECTED_VOTE_SHARE"]).copy()
ae_ext["CAPABILITY"] = ae_ext["Vote_Share_Percentage"] - ae_ext["EXPECTED_VOTE_SHARE"]
ae_ext["EDU_NUM"] = ae_ext["EDU_NUM"].fillna(0)
ae_ext["INCUMBENT"] = ae_ext["INCUMBENT"].fillna(0).astype(int)
ae_ext["NATIONAL_PARTY"] = ae_ext["NATIONAL_PARTY"].fillna(0).astype(int)
ae_ext["IS_INDEPENDENT"] = ae_ext["IS_INDEPENDENT"].fillna(0).astype(int)
ae_ext["WINNER"] = ae_ext["WINNER"].fillna(0).astype(int)
ae_ext["WINNABLE"] = (ae_ext["EXPECTED_VOTE_SHARE"] > 35).astype(int)

print(f"  Extended sample: {len(ae_ext)}")

# ============================================================
# 3. MEASUREMENT MODEL FIT
# ============================================================
print("\n" + "=" * 60)
print("MEASUREMENT MODEL FIT")
print("=" * 60)

for state in TOP_STATES:
    state_df = ae_ext[ae_ext["State_Name"] == state]
    for y in sorted(state_df["Year"].unique()):
        yr = state_df[state_df["Year"] == y]
        ss_res = np.sum((yr["Vote_Share_Percentage"] - yr["EXPECTED_VOTE_SHARE"]) ** 2)
        ss_tot = np.sum((yr["Vote_Share_Percentage"] - yr["Vote_Share_Percentage"].mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        print(f"  {state} {y}: R² = {r2:.4f}, N = {len(yr)}")

# ============================================================
# 4. REGRESSIONS
# ============================================================
print("\n" + "=" * 60)
print("REGRESSIONS")
print("=" * 60)

# Year dummies within each state
ae_ext["YEAR_DUMMY"] = ae_ext["Year"].astype(str)
year_dummies = pd.get_dummies(ae_ext["YEAR_DUMMY"], prefix="YEAR", drop_first=True, dtype=int)
ae_ext = pd.concat([ae_ext, year_dummies], axis=1)
year_cols = [c for c in ae_ext.columns if c.startswith("YEAR_")]

# Overall regression
controls = ["INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM"] + year_cols
pooled_coef, pooled_se, pooled_p, pooled_lo, pooled_hi, pooled_r2, pooled_n = fit_ols_female(ae_ext, controls)
print(f"\n  Overall (5 states, pooled): coef={pooled_coef:.4f}, SE={pooled_se:.4f}, p={pooled_p:.4f}, N={pooled_n}")

# By state
state_rows = []
for state in TOP_STATES:
    state_df = ae_ext[ae_ext["State_Name"] == state]
    year_dummies_s = pd.get_dummies(state_df["Year"].astype(str), prefix="YEAR", drop_first=True, dtype=int)
    state_df = pd.concat([state_df, year_dummies_s], axis=1)
    year_cols_s = [c for c in state_df.columns if c.startswith("YEAR_")]
    controls_s = ["INCUMBENT", "NATIONAL_PARTY", "IS_INDEPENDENT", "EDU_NUM"] + year_cols_s
    coef, se, p, lo, hi, r2, n = fit_ols_female(state_df, controls_s)
    state_rows.append({
        "State": state, "Female_Coef": round(coef, 4), "SE": round(se, 4),
        "p_value": round(p, 4), "N": n, "N_female": int(state_df["FEMALE"].sum()),
    })
    print(f"  {state}: coef={coef:.4f}, SE={se:.4f}, p={p:.4f}, N={n}, N_f={state_df['FEMALE'].sum()}")

state_reg = pd.DataFrame(state_rows)
state_reg.to_csv(OUTPUT_DIR / "vidhansabha_by_state.csv", index=False)

# ============================================================
# 5. THREE-STAGE DECOMPOSITION (POOLED)
# ============================================================
print("\n" + "=" * 60)
print("THREE-STAGE DECOMPOSITION (POOLED)")
print("=" * 60)

f_rate = ae_ext["FEMALE"].mean()
w_f = ae_ext.loc[ae_ext["FEMALE"] == 1, "WINNABLE"].mean()
w_m = ae_ext.loc[ae_ext["FEMALE"] == 0, "WINNABLE"].mean()
cap_f = ae_ext.loc[(ae_ext["FEMALE"] == 1) & (ae_ext["WINNABLE"] == 1), "CAPABILITY"].mean()
cap_m = ae_ext.loc[(ae_ext["FEMALE"] == 0) & (ae_ext["WINNABLE"] == 1), "CAPABILITY"].mean()
cap_gap = cap_f - cap_m if not (np.isnan(cap_f) or np.isnan(cap_m)) else np.nan
win_f = ae_ext.loc[ae_ext["FEMALE"] == 1, "WINNER"].mean()
win_m = ae_ext.loc[ae_ext["FEMALE"] == 0, "WINNER"].mean()

print(f"  Candidate share: {f_rate*100:.1f}%")
print(f"  Winnable: F={w_f*100:.1f}%, M={w_m*100:.1f}%")
print(f"  Capability gap (winnable): {cap_gap:.4f}")
print(f"  Win rate: F={win_f*100:.1f}%, M={win_m*100:.1f}%")

# ============================================================
# 6. SAVE RESULTS
# ============================================================
summary = {
    "n_total": len(ae_ext),
    "n_female": int(ae_ext["FEMALE"].sum()),
    "female_pct": round(ae_ext["FEMALE"].mean() * 100, 1),
    "states": str(TOP_STATES),
    "years": str(sorted(ae_ext["Year"].unique().tolist())),
    "candidate_share": round(f_rate * 100, 1),
    "winnable_female": round(w_f * 100, 1),
    "winnable_male": round(w_m * 100, 1),
    "capability_gap_winnable": round(cap_gap, 4) if not np.isnan(cap_gap) else None,
    "win_rate_female": round(win_f * 100, 1),
    "win_rate_male": round(win_m * 100, 1),
    "overall_female_coef": round(pooled_coef, 4),
    "overall_female_se": round(pooled_se, 4),
    "overall_female_p": round(pooled_p, 4),
}
pd.Series(summary).to_csv(OUTPUT_DIR / "vidhansabha_summary.csv")
ae_ext.to_csv(OUTPUT_DIR / "vidhansabha_analysis.csv", index=False)

print(f"\nSaved: {OUTPUT_DIR / 'vidhansabha_summary.csv'}")
print("Done.")
