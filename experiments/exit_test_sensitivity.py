"""Systematic sensitivity analysis for the proposed institutional-correction exit test.

The five-condition diagnostic is a design framework, not a normative rule.  This
script varies parity bands and persistence windows over the TCPD Lok Sabha panel
and records which conditions are observable from candidate-level election data.
"""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from tcpd_pipeline import OUTPUT_DIR, add_tcpd_expected_vote_share, load_tcpd_ge


YEARS = (2004, 2009, 2014, 2019)
# ECI Atlas 2024 reports women as 48.6% of registered electors.  This is a
# transparent contemporary benchmark, not a contemporaneous denominator for all
# historical election years in the panel.
WOMEN_POPULATION_SHARE = 0.486
LOWER_BOUNDS = (0.6, 0.7, 0.8, 0.9, 1.0)
UPPER_BOUNDS = (1.0, 1.1, 1.2, 1.3, 1.4)
PERSISTENCE_WINDOWS = (1, 2, 3, 4)


def max_consecutive_true(values: list[bool]) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading TCPD Lok Sabha data for exit-test sensitivity...")
    df = add_tcpd_expected_vote_share(load_tcpd_ge(years=YEARS))
    # Open seats are approximated as general seats because this application has no
    # women's-reserved Lok Sabha seats during the period.
    df = df[df["SEAT_TYPE"] == "General"].copy()

    metrics = []
    for year in YEARS:
        sub = df[df["Year"] == year]
        winners = sub[sub["WINNER"] == 1]
        winnable = sub[sub["WINNABLE"] == 1]
        capable_cutoff = sub["CAPABILITY"].median()
        capable = sub[sub["CAPABILITY"] >= capable_cutoff]
        female_win_probability = capable.loc[capable["FEMALE"] == 1, "WINNER"].mean()
        male_win_probability = capable.loc[capable["FEMALE"] == 0, "WINNER"].mean()
        metrics.append({
            "year": year,
            "n_candidates": len(sub),
            "women_candidate_share": sub["FEMALE"].mean(),
            "women_winner_share": winners["FEMALE"].mean(),
            "women_winnable_ticket_share": winnable["FEMALE"].mean(),
            "female_capable_win_probability": female_win_probability,
            "male_capable_win_probability": male_win_probability,
            "representation_ratio": winners["FEMALE"].mean() / WOMEN_POPULATION_SHARE,
            "winnable_ticket_ratio": winnable["FEMALE"].mean() / WOMEN_POPULATION_SHARE,
            "capable_win_probability_ratio": female_win_probability / male_win_probability,
            "distributional_breadth_observable": False,
            "note": "Breadth requires a pre-specified within-group attribute and is not identified in this dataset.",
        })
    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(OUTPUT_DIR / "exit_test_year_metrics.csv", index=False)

    rows = []
    for lower, upper, persistence in itertools.product(LOWER_BOUNDS, UPPER_BOUNDS, PERSISTENCE_WINDOWS):
        if lower > upper:
            continue
        yearly = metrics_df.copy()
        yearly["representation_pass"] = yearly["representation_ratio"].between(lower, upper)
        yearly["ticket_pass"] = yearly["winnable_ticket_ratio"].between(lower, upper)
        yearly["conversion_pass"] = yearly["capable_win_probability_ratio"].between(lower, upper)
        yearly["three_observable_conditions_pass"] = yearly[[
            "representation_pass", "ticket_pass", "conversion_pass"
        ]].all(axis=1)
        max_run = max_consecutive_true(yearly["three_observable_conditions_pass"].tolist())
        rows.append({
            "lower_parity_bound": lower,
            "upper_parity_bound": upper,
            "persistence_cycles": persistence,
            "max_consecutive_observable_passes": max_run,
            "observable_conditions_pass_persistence": max_run >= persistence,
            "five_condition_exit_determinable": False,
            "five_condition_exit_pass": False,
            "reason": "Distributional breadth is unobserved; a five-condition pass cannot be claimed.",
        })
    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(OUTPUT_DIR / "exit_test_sensitivity.csv", index=False)

    manifest = {
        "strategy": "systematic sensitivity analysis",
        "years": list(YEARS),
        "population_share_assumption": WOMEN_POPULATION_SHARE,
        "parity_bounds_tested": {"lower": list(LOWER_BOUNDS), "upper": list(UPPER_BOUNDS)},
        "persistence_windows_tested": list(PERSISTENCE_WINDOWS),
        "observable_conditions": ["open-seat representation", "winnable-ticket parity", "capable-candidate win probability"],
        "unobserved_condition": "distributional breadth",
        "interpretation": "Thresholds are calibrated design choices for sensitivity analysis, not universal standards.",
    }
    with open(OUTPUT_DIR / "exit_test_sensitivity_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(metrics_df[["year", "representation_ratio", "winnable_ticket_ratio", "capable_win_probability_ratio"]].to_string(index=False))
    print(f"Saved {len(sensitivity)} threshold/persistence combinations.")


if __name__ == "__main__":
    main()
