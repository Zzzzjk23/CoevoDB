#!/usr/bin/env bash
# E1 formal run (S19): full (glm-flash), nollm and sqlancer x seeds 1001-1005 on DuckDB 1.5.5, 24 hours a cell,
# six cells at once (two seed blocks of three arms). pure_llm is not run (user's decision, PLAN §9, 2026-10-20).
# Runs inside tmux on the server; the shell must already have DEEPSEEK_API_KEY (the OpenRouter key) and
# PUSHPLUS_TOKEN, which ~/.bashrc loads (SERVER.md §5.2). Starts the pushplus watcher next to the grid.
# Output: ~/CoevoDB/framework/results/e1/, results/e1.log, results/e1.notify.log
set -u
PY=~/CoevoDB/.venv/bin/python
name=e1
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
$PY -m surprise.experiments.grid run surprise/docs/grids/e1.json --out results/$name 2>&1 | tee -a results/$name.log
$PY -m surprise.experiments.grid status results/$name 2>&1 | tee -a results/$name.log
$PY -m surprise.metrics.report results/$name 2>&1 | tee -a results/$name.log
wait
echo "== $name end $(date -u +%FT%TZ)" | tee -a results/$name.log
