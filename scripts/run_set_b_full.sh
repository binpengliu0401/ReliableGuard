#!/usr/bin/env bash
set -euo pipefail

python3 scripts/run_ablation.py \
  --set B \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --tier-b tasks/tier_b_prompts.json \
  --output-dir results/set_b_full \
  --timestamped-output
