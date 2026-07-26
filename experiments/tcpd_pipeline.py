"""TCPD-based pipeline extending the electoral analysis to 2004-2019 Lok Sabha
and providing Vidhan Sabha (state assembly) replication.

Uses TCPD GE/AE datasets which provide:
- Pre-computed Vote_Share_Percentage
- Sex, Party, Votes, Constituency_Type (GEN/SC/ST)
- Incumbent, Recontest, No_Terms
- MyNeta_education (84% coverage), TCPD_Prof_Main (88%)
- Party_Type_TCPD classification
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm

DATA_DIR = Path("data")
OUTPUT_DIR = Path("experiments/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TCPD_GE_PATH = DATA_DIR / "TCPD_GE_All_States_2026-7-26.csv.gz"
TCPD_AE_PATH = DATA_DIR / "TCPD_AE_All_States_2026-7-26.csv.gz"


def load_tcpd_ge(years=(2004, 2009, 2014, 2019)) -> pd.DataFrame:
    """Load and clean TCPD Lok Sabha dataset."""
    df = pd.read_csv(TCPD_GE_PATH, low_memory=False)

    # Standardize sex
    df["Sex"] = df["Sex"].str.upper().str.strip()
    df = df[df["Sex"].isin(["M", "F"])].copy()
    df["FEMALE"] = (df["Sex"] == "F").astype(int)

    # Filter years if requested; allow full-history loads for rolling sensitivity analyses.
    if years is not None:
        df = df[df["Year"].isin(list(years))].copy()

    # Ensure numeric
    df["Votes"] = pd.to_numeric(df["Votes"], errors="coerce")
    df["Vote_Share_Percentage"] = pd.to_numeric(df["Vote_Share_Percentage"], errors="coerce")
    df["Valid_Votes"] = pd.to_numeric(df["Valid_Votes"], errors="coerce")
    df["Electors"] = pd.to_numeric(df["Electors"], errors="coerce")
    df["N_Cand"] = pd.to_numeric(df["N_Cand"], errors="coerce")
    df["Margin"] = pd.to_numeric(df["Margin"], errors="coerce")
    df["Margin_Percentage"] = pd.to_numeric(df["Margin_Percentage"], errors="coerce")

    # Drop rows with missing key fields
    df = df.dropna(subset=["Votes", "Vote_Share_Percentage"])
    df = df[df["Votes"] > 0].copy()

    # Clean keys
    df["STATE_CLEAN"] = df["State_Name"].str.replace("_", " ").str.strip().str.upper()
    df["PC_CLEAN"] = df["Constituency_Name"].str.strip().str.upper()
    df["PARTY_CLEAN"] = df["Party"].str.strip().str.upper()
    df["NAME_CLEAN"] = df["Candidate"].str.strip().str.upper()

    # Seat type
    df["SEAT_TYPE"] = "General"
    ct = df["Constituency_Type"].astype(str).str.upper()
    df.loc[ct.str.contains("SC", na=False), "SEAT_TYPE"] = "SC Reserved"
    df.loc[ct.str.contains("ST", na=False), "SEAT_TYPE"] = "ST Reserved"

    # Party type
    df["NATIONAL_PARTY"] = (df["Party_Type_TCPD"] == "National Party").astype(int)
    df["IS_INDEPENDENT"] = (df["Party_Type_TCPD"] == "Independents").astype(int)

    # Incumbent / recontest / tenure / turncoat
    df["INCUMBENT"] = df["Incumbent"].fillna(False).astype(int)
    df["RECONTEST"] = df["Recontest"].fillna(False).astype(int)
    df["TURNCOAT"] = df["Turncoat"].fillna(False).astype(int)
    df["NO_TERMS"] = pd.to_numeric(df["No_Terms"], errors="coerce").fillna(0)

    # Education (ordinal mapping from MyNeta categories in TCPD)
    edu_map = {
        "Graduate": 3, "Post Graduate": 4, "Doctorate": 5,
        "Graduate Professional": 3.5, "12th Pass": 2, "10th Pass": 1.5,
        "8th Pass": 1, "5th Pass": 0.5, "Literate": 0.5,
        "Illiterate": 0, "Not Given": np.nan, "Others": np.nan,
    }
    df["EDU_NUM"] = df["MyNeta_education"].map(edu_map)

    # Profession flags
    prof = df["TCPD_Prof_Main_Desc"].fillna("").str.lower()
    df["IS_PROFESSIONAL"] = prof.str.contains("lawyer|doctor|engineer|professor|teacher", na=False).astype(int)
    df["IS_BUSINESS"] = prof.str.contains("business|industrial|trade", na=False).astype(int)
    df["IS_AGRICULTURE"] = prof.str.contains("agriculture|farmer", na=False).astype(int)
    df["IS_POLITICS"] = prof.str.contains("political|social work|activist", na=False).astype(int)

    # Winner flag
    df["WINNER"] = (df["Position"] == 1).astype(int)

    # Coalition/alliance (from Party_Type_TCPD)
    df["IS_NATIONAL_PARTY"] = (df["Party_Type_TCPD"] == "National Party").astype(int)
    df["IS_STATE_PARTY"] = df["Party_Type_TCPD"].str.contains("State-based", na=False).astype(int)

    # Delimitation period
    # Pre-2008: Assembly_No <= 13; Post-2008: >= 14
    df["POST_DELIMITATION"] = (df["Assembly_No"] >= 14).astype(int)

    return df


def load_tcpd_ae(years=None) -> pd.DataFrame:
    """Load and clean TCPD Vidhan Sabha dataset."""
    df = pd.read_csv(TCPD_AE_PATH, low_memory=False)

    # Standardize sex
    df["Sex"] = df["Sex"].str.upper().str.strip()
    df = df[df["Sex"].isin(["M", "F"])].copy()
    df["FEMALE"] = (df["Sex"] == "F").astype(int)

    if years is not None:
        df = df[df["Year"].isin(list(years))].copy()

    # Ensure numeric
    for col in ["Votes", "Vote_Share_Percentage", "Valid_Votes", "Electors", "N_Cand", "Margin", "Margin_Percentage"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Votes", "Vote_Share_Percentage"])
    df = df[df["Votes"] > 0].copy()

    # Seat type
    df["SEAT_TYPE"] = "General"
    ct = df["Constituency_Type"].astype(str).str.upper()
    df.loc[ct.str.contains("SC", na=False), "SEAT_TYPE"] = "SC Reserved"
    df.loc[ct.str.contains("ST", na=False), "SEAT_TYPE"] = "ST Reserved"

    # Party type
    df["NATIONAL_PARTY"] = (df["Party_Type_TCPD"] == "National Party").astype(int)
    df["IS_INDEPENDENT"] = (df["Party_Type_TCPD"] == "Independents").astype(int)

    # Incumbent / recontest / tenure / turncoat
    df["INCUMBENT"] = df["Incumbent"].fillna(False).astype(int)
    df["RECONTEST"] = df["Recontest"].fillna(False).astype(int)
    df["TURNCOAT"] = df["Turncoat"].fillna(False).astype(int)
    df["NO_TERMS"] = pd.to_numeric(df["No_Terms"], errors="coerce").fillna(0)

    # Education
    edu_map = {
        "Graduate": 3, "Post Graduate": 4, "Doctorate": 5,
        "Graduate Professional": 3.5, "12th Pass": 2, "10th Pass": 1.5,
        "8th Pass": 1, "5th Pass": 0.5, "Literate": 0.5,
        "Illiterate": 0, "Not Given": np.nan, "Others": np.nan,
    }
    df["EDU_NUM"] = df["MyNeta_education"].map(edu_map)
    df["WINNER"] = (df["Position"] == 1).astype(int)

    return df


def add_tcpd_expected_vote_share(df: pd.DataFrame) -> pd.DataFrame:
    """Add expected vote share using TCPD's pre-computed vote shares.

    For each election T, the expected vote share for party P in constituency C is:
    - 2004: party-state mean (no prior data in TCPD at party-constituency level)
    - 2009: party-constituency mean from 2004 (with state fallback)
    - 2014: party-constituency mean from 2009 (with state fallback)
    - 2019: party-constituency mean from 2014 (with state fallback)
    """
    df = df.sort_values(["Year", "State_Name", "Constituency_Name", "Party"]).copy()

    years = sorted(df["Year"].unique())
    results = []

    for i, year in enumerate(years):
        yr_df = df[df["Year"] == year].copy()

        if i == 0:
            # First election: use party-state mean
            party_state = yr_df.groupby(["STATE_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                STATE_AVG_SHARE=("Vote_Share_Percentage", "mean"),
                GROUP_SIZE=("Vote_Share_Percentage", "size"),
            ).reset_index()
            yr_df = yr_df.merge(party_state, on=["STATE_CLEAN", "PARTY_CLEAN"], how="left")
            yr_df["EXPECTED_VOTE_SHARE"] = yr_df["STATE_AVG_SHARE"]
            yr_df["EXPECTED_SOURCE"] = f"party-state mean ({year})"
        else:
            prev_year = years[i - 1]
            prev_df = df[df["Year"] == prev_year]

            # Party-constituency baseline from previous election
            party_const = prev_df.groupby(["PC_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                PARTY_CONST_SHARE=("Vote_Share_Percentage", "mean")
            ).reset_index()

            # Party-state baseline from previous election
            party_state = prev_df.groupby(["STATE_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                STATE_AVG_SHARE=("Vote_Share_Percentage", "mean")
            ).reset_index()

            yr_df = yr_df.merge(party_const, on=["PC_CLEAN", "PARTY_CLEAN"], how="left")
            yr_df = yr_df.merge(party_state, on=["STATE_CLEAN", "PARTY_CLEAN"], how="left")

            yr_df["EXPECTED_SOURCE"] = np.where(
                yr_df["PARTY_CONST_SHARE"].notna(),
                f"party-constituency ({prev_year})",
                f"state-level fallback ({prev_year})",
            )
            yr_df["EXPECTED_VOTE_SHARE"] = yr_df["PARTY_CONST_SHARE"].fillna(yr_df["STATE_AVG_SHARE"])

            # Also merge group size for diagnostics
            grp = prev_df.groupby(["STATE_CLEAN", "PARTY_CLEAN"], observed=True).agg(
                GROUP_SIZE=("Vote_Share_Percentage", "size")
            ).reset_index()
            yr_df = yr_df.merge(grp, on=["STATE_CLEAN", "PARTY_CLEAN"], how="left")

        results.append(yr_df)

    out = pd.concat(results, ignore_index=True)
    out = out.dropna(subset=["EXPECTED_VOTE_SHARE"]).copy()
    out["CAPABILITY"] = out["Vote_Share_Percentage"] - out["EXPECTED_VOTE_SHARE"]
    out["YEAR_2009"] = (out["Year"] == 2009).astype(int)
    out["YEAR_2014"] = (out["Year"] == 2014).astype(int)
    out["YEAR_2019"] = (out["Year"] == 2019).astype(int)
    out["WINNABLE"] = (out["EXPECTED_VOTE_SHARE"] > 35).astype(int)
    out["IS_SC"] = (out["SEAT_TYPE"] == "SC Reserved").astype(int)
    out["IS_ST"] = (out["SEAT_TYPE"] == "ST Reserved").astype(int)

    return out


def fit_ols_female(df, controls, dep_var="CAPABILITY"):
    """Run OLS: dep_var ~ FEMALE + controls, HC3 SEs."""
    cols = ["FEMALE"] + controls
    available = [c for c in cols if c in df.columns]
    # Ensure unique columns
    seen = set()
    unique_cols = []
    for c in available:
        if c not in seen:
            seen.add(c)
            unique_cols.append(c)
    X = sm.add_constant(df[unique_cols].astype(float), has_constant="add")
    y = df[dep_var].astype(float)
    m = sm.OLS(y, X).fit(cov_type="HC3")
    coef = float(m.params["FEMALE"])
    se = float(m.bse["FEMALE"])
    p = float(m.pvalues["FEMALE"])
    ci = m.conf_int().loc["FEMALE"]
    lo = float(ci.iloc[0]) if hasattr(ci, 'iloc') else float(ci[0])
    hi = float(ci.iloc[1]) if hasattr(ci, 'iloc') else float(ci[1])
    r2 = float(m.rsquared)
    n = int(m.nobs)
    return coef, se, p, lo, hi, r2, n
