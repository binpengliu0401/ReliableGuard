#!/usr/bin/env bash
set -euo pipefail

python3 scripts/run_ablation.py \
  --set A \
  --versions V3_NoStructural \
  --seeds 42 123 7 \
  --domain ecommerce \
  --ecommerce tasks/ecommerce_scenarios.json \
  --output-dir results/rq3_ablation \
  --timestamped-output
