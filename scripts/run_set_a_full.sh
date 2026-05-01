#!/usr/bin/env bash
set -euo pipefail

python scripts/run_ablation.py \
  --set A \
  --versions V1 V2 V3 \
  --seeds 42 123 7 \
  --ecommerce tasks/ecommerce_scenarios.json \
  --reference tasks/reference_scenarios.json \
  --output-dir results/set_a_full \
  --timestamped-output
