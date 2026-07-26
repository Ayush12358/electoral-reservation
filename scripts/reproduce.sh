#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FULL_BOOT_N="${FULL_BOOT_N:-100}"
RUN_EXTENDED="${RUN_EXTENDED:-1}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -n "$PYTHON_BIN" ]]; then
  : # Caller supplied an interpreter command available on PATH.
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v py.exe >/dev/null 2>&1; then
  PYTHON_BIN=py.exe
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  echo "Python interpreter not found. Set PYTHON_BIN or install Python." >&2
  exit 1
fi

"$PYTHON_BIN" experiments/analysis_with_controls.py
"$PYTHON_BIN" experiments/step1_model_report.py
"$PYTHON_BIN" experiments/validation_renomination.py
"$PYTHON_BIN" experiments/heterogeneity.py
"$PYTHON_BIN" experiments/interaction_model.py
"$PYTHON_BIN" experiments/sc_st_analysis.py
"$PYTHON_BIN" experiments/measurement_validation_suite.py
"$PYTHON_BIN" experiments/fuzzy_match_sensitivity.py
"$PYTHON_BIN" experiments/apply_entity_resolution_adjudication.py
"$PYTHON_BIN" experiments/bootstrap_uncertainty.py
"$PYTHON_BIN" experiments/full_pipeline_bootstrap.py --n-boot "$FULL_BOOT_N"

if [[ "$RUN_EXTENDED" == "1" ]]; then
  "$PYTHON_BIN" experiments/tcpd_pipeline.py
  "$PYTHON_BIN" experiments/tcpd_expected_vote_sensitivity.py
  "$PYTHON_BIN" experiments/extended_loksabha_analysis.py
  "$PYTHON_BIN" experiments/tcpd_future_performance_validation.py
  "$PYTHON_BIN" experiments/exit_test_sensitivity.py
  "$PYTHON_BIN" experiments/vidhansabha_replication.py
  "$PYTHON_BIN" experiments/manuscript_consistency_audit.py
fi

echo "Done. Outputs are in experiments/results/."
