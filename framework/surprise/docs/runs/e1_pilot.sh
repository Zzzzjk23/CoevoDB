#!/usr/bin/env bash
# E1 pilot (S19): the same 2-hour grid at concurrency 8, then 4, then 1 (seed 9101 only).
# Runs inside tmux on the server; DEEPSEEK_API_KEY must already be in this shell's environment.
# Output: ~/CoevoDB/framework/results/e1-pilot-c{8,4,1}/ and results/e1-pilot-c{8,4,1}.log
set -u
PY=~/CoevoDB/.venv/bin/python
cd ~/CoevoDB/framework || exit 2
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY is not set" >&2
  exit 2
fi
echo "deployed: $(git -C ~/CoevoDB describe --tags --exact-match 2>/dev/null || echo untagged)"
for c in 8 4 1; do
  name=e1-pilot-c$c
  echo "== $name start $(date -u +%FT%TZ)" | tee -a results/$name.log
  $PY -m surprise.experiments.grid run surprise/docs/grids/e1_pilot_c$c.json --out results/$name 2>&1 | tee -a results/$name.log
  $PY -m surprise.experiments.grid status results/$name 2>&1 | tee -a results/$name.log
  $PY -m surprise.metrics.report results/$name 2>&1 | tee -a results/$name.log
  echo "== $name end $(date -u +%FT%TZ)" | tee -a results/$name.log
done
echo "E1 pilot finished $(date -u +%FT%TZ)"
