#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEDS_TO_RUN="${SEEDS_TO_RUN:-42 123 7}"
OUTPUT_DIR="${OUTPUT_DIR:-results/set_a_ecommerce_full}"

EMPTY_REFERENCE_FILE="$(mktemp "${TMPDIR:-/tmp}/empty_reference.XXXXXX.json")"
trap 'rm -f "$EMPTY_REFERENCE_FILE"' EXIT
printf '[]\n' > "$EMPTY_REFERENCE_FILE"

echo "[RUN] Set A ecommerce full"
echo "[RUN] versions: V1 V2 V3"
echo "[RUN] seeds: $SEEDS_TO_RUN"
echo "[RUN] output: $OUTPUT_DIR/YYYYMMDD/HHMMSS"

python3 scripts/run_ablation.py \
  --set A \
  --versions V1 V2 V3 \
  --seeds $SEEDS_TO_RUN \
  --ecommerce tasks/ecommerce_scenarios.json \
  --reference "$EMPTY_REFERENCE_FILE" \
  --output-dir "$OUTPUT_DIR" \
  --timestamped-output \
  --save-states false-alarms
