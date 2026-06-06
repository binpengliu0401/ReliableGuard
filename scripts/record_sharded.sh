#!/usr/bin/env bash
# Parallel, crash-safe Set A record via process sharding.
#
# Concurrency cannot use threads here: the ecommerce/reference DBs and the tool
# registry are process-global singletons (reset_env clears them, F4 injection
# mutates the registry), so concurrent scenarios in one process would corrupt
# each other. Instead we run N independent processes over disjoint scenario
# shards, each with its own SQLite files via RG_DB_SUFFIX. Each shard streams a
# JSONL checkpoint and uses --resume, so a crash only re-does that shard's tail.
#
# Usage:
#   scripts/record_sharded.sh [N] [OUT_DIR] [SEED]
#     N        number of parallel shards (default 4; raise cautiously — too many
#              concurrent requests will hit OpenRouter rate limits -> error rows)
#     OUT_DIR  output directory (default results/corpus)
#     SEED     record seed (default 42)
#
# After it finishes, replay all versions off the merged corpus:
#   python3 scripts/run_replay.py replay \
#     --corpus results/corpus/set_a_corpus.jsonl --out results/replay/set_a
set -euo pipefail

N="${1:-4}"
OUT_DIR="${2:-results/corpus}"
SEED="${3:-42}"

mkdir -p "$OUT_DIR"
echo "[SHARDED] launching $N shards (seed=$SEED) -> $OUT_DIR"

pids=()
for i in $(seq 0 $((N - 1))); do
  RG_DB_SUFFIX="shard$i" python3 scripts/run_replay.py record \
    --set A --seeds "$SEED" \
    --shard "$i" --num-shards "$N" --resume \
    --out "$OUT_DIR/shard$i.jsonl" \
    > "$OUT_DIR/shard$i.log" 2>&1 &
  pids+=("$!")
  echo "[SHARDED] shard $i -> pid ${pids[-1]} (log: $OUT_DIR/shard$i.log)"
done

# Wait for all shards; fail if any shard process exits non-zero.
status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    echo "[SHARDED] WARNING: shard pid $pid exited non-zero" >&2
    status=1
  fi
done

MERGED="$OUT_DIR/set_a_corpus.jsonl"
shard_files=()
for i in $(seq 0 $((N - 1))); do shard_files+=("$OUT_DIR/shard$i.jsonl"); done
python3 scripts/run_replay.py merge --shards "${shard_files[@]}" --out "$MERGED"

echo "[SHARDED] done (status=$status). Merged corpus: $MERGED"
echo "[SHARDED] next: python3 scripts/run_replay.py replay --corpus $MERGED --out results/replay/set_a"
exit "$status"
