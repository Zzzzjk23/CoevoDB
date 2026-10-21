#!/usr/bin/env bash
# E1 GLM pilot (S19, 2026-10-21): arm `full` on tier glm-flash, seeds 9101 and 9102, 2 hours, both cells at once.
# Runs inside tmux on the server; the shell must already have DEEPSEEK_API_KEY (the OpenRouter key) and
# PUSHPLUS_TOKEN, which ~/.bashrc loads (SERVER.md §5.2). Starts the pushplus watcher next to the grid.
# Usage: bash e1_pilot_glm.sh [NAME]; NAME defaults to e1-pilot-glm and picks grids/<NAME with _ for ->.json
# (e1-pilot-glm2 is the rerun after the provider and reasoning changes).
# Output: ~/CoevoDB/framework/results/<NAME>/, results/<NAME>.log, results/<NAME>.notify.log
set -u
PY=~/CoevoDB/.venv/bin/python
name=${1:-e1-pilot-glm}
config=surprise/docs/grids/$(echo "$name" | tr - _).json
cd ~/CoevoDB/framework || exit 2
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY is not set" >&2
  exit 2
fi
if [ -z "${PUSHPLUS_TOKEN:-}" ]; then
  echo "PUSHPLUS_TOKEN is not set: the watcher will not push" >&2
fi
echo "deployed: $(git -C ~/CoevoDB describe --tags --exact-match 2>/dev/null || echo untagged)" | tee -a results/$name.log
echo "== $name start $(date -u +%FT%TZ)" | tee -a results/$name.log
# The watcher waits for the grid to write grid.json, then follows the grid process and stops with it.
(
  pid=""
  for _ in $(seq 120); do
    pid=$(pgrep -f -o "surprise.experiments.grid run .*results/$name\$")
    if [ -n "$pid" ] && [ -f results/$name/grid.json ]; then
      break
    fi
    sleep 5
  done
  if [ -z "$pid" ]; then
    echo "watcher: grid process not found" >> results/$name.notify.log
    exit 1
  fi
  exec $PY -m surprise.notify.watch results/$name --pid "$pid" >> results/$name.notify.log 2>&1
) &
$PY -m surprise.experiments.grid run "$config" --out results/$name 2>&1 | tee -a results/$name.log
$PY -m surprise.experiments.grid status results/$name 2>&1 | tee -a results/$name.log
$PY -m surprise.metrics.report results/$name 2>&1 | tee -a results/$name.log
wait
echo "== $name end $(date -u +%FT%TZ)" | tee -a results/$name.log
