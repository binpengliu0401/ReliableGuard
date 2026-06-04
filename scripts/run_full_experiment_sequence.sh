#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

LOG_DIR="results/run_logs"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/full_experiment_${RUN_STAMP}.log"

mkdir -p "${LOG_DIR}"

run_step() {
  local name="$1"
  shift

  {
    echo
    echo "============================================================"
    echo "[START] ${name} at $(date)"
    echo "============================================================"
  } | tee -a "${LOG_FILE}"

  set +e
  "$@" 2>&1 | tee -a "${LOG_FILE}"
  local status=${PIPESTATUS[0]}
  set -e

  if [[ ${status} -eq 0 ]]; then
    {
      echo "============================================================"
      echo "[DONE] ${name} at $(date)"
      echo "============================================================"
    } | tee -a "${LOG_FILE}"
  else
    {
      echo "============================================================"
      echo "[FAILED] ${name} at $(date) status=${status}"
      echo "[ABORT] Stopping full experiment sequence."
      echo "============================================================"
    } | tee -a "${LOG_FILE}"
    exit "${status}"
  fi
}

echo "[LOG] ${LOG_FILE}"
echo "[GIT] $(git rev-parse --short HEAD 2>/dev/null || echo unknown)" | tee -a "${LOG_FILE}"

run_step "Set A full ablation" ./scripts/run_set_a_full.sh
run_step "Set B full ablation" ./scripts/run_set_b_full.sh
run_step "Structural ablation (paper RQ2)" ./scripts/run_structural_ablation.sh
run_step "Generate figures" python3 scripts/generate_figures.py

echo "[ALL DONE] $(date)" | tee -a "${LOG_FILE}"
