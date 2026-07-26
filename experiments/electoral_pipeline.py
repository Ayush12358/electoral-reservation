"""Shared data-loading and measurement utilities for electoral capability analyses.

This module deliberately computes constituency total votes and candidate vote shares
on the full ECI/parliament dataset *before* merging to MyNeta controls. Computing
vote shares after dropping unmatched affidavit rows biases vote shares upward for
matched candidates and invalidates residuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd

DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("experiments/results")

EDUCATION_MAP = {
    "Graduate": 3,
    "Post Graduate": 4,
    "Doctorate": 5,
    "Graduate Professional": 3.5,
    "12th Pass": 2,
    "10th Pass": 1.5,
    "8th Pass": 1,
    "5th Pass": 0.5,
    "Literate": 0.5,
    "Illiterate": 0,
    "Not Given": np.nan,
    "Others": np.nan,
}

NATIONAL_PARTIES = {
    "INC", "BJP", "CPI", "CPM", "BSP", "NCP", "AITC",
    "INDIAN NATIONAL CONGRESS", "BHARATIYA JANATA PARTY",
    "COMMUNIST PARTY OF INDIA", "COMMUNIST PARTY OF INDIA (MARXIST)",
    "BAHUJAN SAMAJ PARTY", "NATIONALIST CONGRESS PARTY",
    "ALL INDIA TRINAMOOL CONGRESS",
}


def clean_key(value: object) -> str:
    """Aggressive key cleaning for candidate/constituency names."""
    if pd.isna(value):
        return ""
    value = str(value).upper().strip()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    value = re.sub(r"\b(SHRI|SMT|DR|PROF|ADV|CAPT|LT|COL)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def name_similarity(a: object, b: object) -> float:
    return SequenceMatcher(None, clean_key(a), clean_key(b)).ratio()


def load_parliament(years: Iterable[int] = (2004, 2009)) -> pd.DataFrame:
    parliament = pd.read_csv(DATA_DIR / "parliament_final.csv", low_memory=False)
    parliament["SEX"] = parliament["SEX"].astype(str).str.strip().str.upper()
    parliament = parliament[parliament["SEX"].isin(["M", "F"])].copy()
    parliament = parliament[parliament["YEAR"].isin(list(years))].copy()
    parliament["VOTES"] = pd.to_numeric(parliament["VOTES"], errors="coerce")
    parliament = parliament.dropna(subset=["VOTES"])
    parliament = parliament[parliament["VOTES"] > 0].copy()

    parliament = parliament.reset_index(drop=True)
    parliament["PARL_ROW_ID"] = np.arange(len(parliament))
    parliament["NAME_CLEAN"] = parliament["NAME"].map(clean_key)
    parliament["PC_CLEAN"] = parliament["PC"].map(clean_key)
    parliament["PARTY_CLEAN"] = parliament["PARTY"].map(clean_key)

    # Vote-share denominator must be all candidates in the constituency-year.
    parliament["TOTAL_VOTES"] = parliament.groupby(["YEAR", "PC"], observed=True)["VOTES"].transform("sum")
    parliament["VOTE_SHARE"] = parliament["VOTES"] / parliament["TOTAL_VOTES"] * 100
    parliament["WINNER"] = (parliament.groupby(["YEAR", "PC"], observed=True)["VOTES"].rank(method="first", ascending=False) == 1).astype(int)
    return parliament


def load_myneta(years: Iterable[int] = (2004, 2009)) -> pd.DataFrame:
    frames = []
    for year in years:
        path = DATA_DIR / f"myneta_{year}.csv"
        if path.exists():
            frames.append(pd.read_csv(path, low_memory=False))
    if not frames:
        raise FileNotFoundError("No MyNeta files found for requested years")
    myneta = pd.concat(frames, ignore_index=True)
    myneta["YEAR"] = pd.to_numeric(myneta["Year"], errors="coerce").astype("Int64")
    myneta = myneta[myneta["YEAR"].isin(list(years))].copy()
    myneta["CANDIDATE_CLEAN"] = myneta["Candidate"].map(clean_key)
    myneta["CONSTITUENCY_CLEAN"] = myneta["Constituency"].map(clean_key)
    myneta["PARTY_CLEAN"] = myneta["Party"].map(clean_key)
    myneta["Criminal Cases"] = pd.to_numeric(myneta["Criminal Cases"], errors="coerce").fillna(0).astype(int)
    myneta["Total Assets"] = pd.to_numeric(myneta["Total Assets"], errors="coerce").fillna(0)
    myneta["Total Liabilities"] = pd.to_numeric(myneta["Total Liabilities"], errors="coerce").fillna(0)
    myneta["LOG_ASSETS"] = np.log1p(myneta["Total Assets"])
    myneta["HAS_CRIMINAL"] = (myneta["Criminal Cases"] > 0).astype(int)
    myneta["EDU_NUM"] = myneta["Education"].map(EDUCATION_MAP)
    myneta["MYNETA_ROW_ID"] = np.arange(len(myneta))
    return myneta


def add_expected_vote_share(parliament: pd.DataFrame) -> pd.DataFrame:
    """Add baseline expected vote share and residuals using full election data."""
    df_2004 = parliament[parliament["YEAR"] == 2004].copy()
    df_2009 = parliament[parliament["YEAR"] == 2009].copy()

    party_state_2004 = df_2004.groupby(["STATE", "PARTY"], observed=True).agg(
        STATE_AVG_SHARE=("VOTE_SHARE", "mean"),
        GROUP_SIZE=("VOTE_SHARE", "size"),
    ).reset_index()
    df_2004 = df_2004.merge(party_state_2004, on=["STATE", "PARTY"], how="left")
    df_2004["EXPECTED_VOTE_SHARE"] = df_2004["STATE_AVG_SHARE"]
    df_2004["EXPECTED_SOURCE"] = "party-state mean (2004)"

    party_const_2004 = df_2004.groupby(["PC", "PARTY"], observed=True).agg(
        PARTY_CONST_SHARE=("VOTE_SHARE", "mean")
    ).reset_index()
    df_2009 = df_2009.merge(party_const_2004, on=["PC", "PARTY"], how="left")
    df_2009 = df_2009.merge(party_state_2004, on=["STATE", "PARTY"], how="left")
    df_2009["EXPECTED_SOURCE"] = np.where(
        df_2009["PARTY_CONST_SHARE"].notna(),
        "party-constituency",
        "state-level fallback",
    )
    df_2009["EXPECTED_VOTE_SHARE"] = df_2009["PARTY_CONST_SHARE"].fillna(df_2009["STATE_AVG_SHARE"])

    df = pd.concat([df_2004, df_2009], ignore_index=True)
    df = df.dropna(subset=["EXPECTED_VOTE_SHARE"]).copy()
    df["CAPABILITY"] = df["VOTE_SHARE"] - df["EXPECTED_VOTE_SHARE"]
    df["FEMALE"] = (df["SEX"] == "F").astype(int)
    df["YEAR_2009"] = (df["YEAR"] == 2009).astype(int)
    df["WINNABLE"] = (df["EXPECTED_VOTE_SHARE"] > 35).astype(int)
    df["PARTY_UPPER"] = df["PARTY"].map(clean_key)
    df["NATIONAL_PARTY"] = df["PARTY_UPPER"].isin(NATIONAL_PARTIES).astype(int)
    df["SEAT_TYPE"] = "General"
    if "CATEGORY" in df.columns:
        cat = df["CATEGORY"].astype(str).str.upper()
        df.loc[cat.str.contains("SC", na=False), "SEAT_TYPE"] = "SC Reserved"
        df.loc[cat.str.contains("ST", na=False), "SEAT_TYPE"] = "ST Reserved"
    df["IS_SC"] = (df["SEAT_TYPE"] == "SC Reserved").astype(int)
    df["IS_ST"] = (df["SEAT_TYPE"] == "ST Reserved").astype(int)
    return df


def exact_merge(parliament_with_residuals: pd.DataFrame, myneta: pd.DataFrame) -> pd.DataFrame:
    controls = myneta[[
        "CANDIDATE_CLEAN", "CONSTITUENCY_CLEAN", "PARTY_CLEAN", "YEAR",
        "Criminal Cases", "HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM", "Education",
        "Total Assets", "Total Liabilities", "MYNETA_ROW_ID",
    ]].copy()
    merged = parliament_with_residuals.merge(
        controls,
        left_on=["NAME_CLEAN", "PC_CLEAN", "PARTY_CLEAN", "YEAR"],
        right_on=["CANDIDATE_CLEAN", "CONSTITUENCY_CLEAN", "PARTY_CLEAN", "YEAR"],
        how="left",
        indicator=True,
    )
    # Enforce one parliament row -> at most one control row. Duplicate MyNeta rows
    # otherwise inflate the analysis sample and validation counts.
    merged["_match_rank"] = np.where(merged["_merge"].eq("both"), 0, 1)
    merged = merged.sort_values(["PARL_ROW_ID", "_match_rank", "MYNETA_ROW_ID"], na_position="last")
    merged = merged.drop_duplicates(subset=["PARL_ROW_ID"], keep="first").copy()
    merged["MERGED"] = (merged["_merge"] == "both").astype(int)
    merged["MATCH_METHOD"] = np.where(merged["MERGED"].eq(1), "exact_name_pc_party_year", "unmatched")
    merged["MATCH_CONFIDENCE"] = np.where(merged["MERGED"].eq(1), 1.0, np.nan)
    return merged


def build_analysis_dataset(years: Iterable[int] = (2004, 2009), matched_only: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (analysis_data, full_merged_audit_data)."""
    parliament = add_expected_vote_share(load_parliament(years))
    myneta = load_myneta(years)
    merged = exact_merge(parliament, myneta)
    if matched_only:
        df = merged[merged["MERGED"] == 1].copy()
    else:
        df = merged.copy()
    for col in ["HAS_CRIMINAL", "LOG_ASSETS", "EDU_NUM"]:
        if col in df:
            if col == "EDU_NUM":
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna(df[col].median() if df[col].notna().any() else 0)
    return df, merged


def compute_match_upper_bounds(parliament: pd.DataFrame, myneta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, p_year in parliament.groupby("YEAR"):
        m_year = myneta[myneta["YEAR"] == year]
        rows.append({
            "year": int(year),
            "parliament_rows": len(p_year),
            "myneta_rows": len(m_year),
            "upper_bound_if_every_affidavit_matched": min(len(p_year), len(m_year)) / len(p_year),
        })
    rows.append({
        "year": "all",
        "parliament_rows": len(parliament),
        "myneta_rows": len(myneta),
        "upper_bound_if_every_affidavit_matched": min(len(parliament), len(myneta)) / len(parliament),
    })
    return pd.DataFrame(rows)
