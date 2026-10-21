# CoevoDB — Surprise-driven DBMS bug finding

The body of this tree is the surprise-driven framework in `surprise/`.
A falsifiable theory predicts a failure probability for every experiment;
Hunter selects the next case by information value; labels come only from
seven oracles plus the CVE (Contract-Verified Evidence) pipeline. The LLM
is **never the bug oracle**. The original CoevoDB (LLM Hunter/Fixer
co-evolution) is kept as a baseline arm. Architecture:
[surprise/ARCHITECTURE.md](surprise/ARCHITECTURE.md).

## Layout

| path | role |
|---|---|
| `surprise/` | surprise-driven framework (harness, features, theory, Hunter, Diagnoser, LLM roles, experiments, metrics, baselines, gates) |
| `oracles/`, `targets/`, `diagnosis/`, `seeds/`, `util/` | shared runners, oracles, bisect/σ, corpus, machine-local paths |
| `llm/`, `agents/base_agent.py`, `agents/bug_fixer.py`, `agents/json_utils.py`, `evolution/dce.py` | shared primitives (HTTP client, minimiser, DCE operators, call ledger) |
| `campaigns/` | PostgreSQL campaign scripts (`campaigns/pg_*.py`), moved from `scripts/` in S1 |
| `scripts/` | old-system experiment scripts plus the shared `scripts/cross_engine.py` |
| `archive/` | archived `archive/coevo/` prototype and `archive/repair_bench/` patch/localization benchmark |
| `tests/`, `testing/` | surprise-framework tests and the original CoevoDB tests |

## Running the surprise framework

Commands below are run from `framework/` with the interpreter of the
repository's main environment, `.venv` at the repository root (`python` below
stands for it; the root README lists the environment). LLM roles are off by default;
`--llm ROLE` turns one role on (repeatable) and requires `DEEPSEEK_API_KEY`.

Target engines are `duckdb`, `datafusion` and `postgres`. With
`--engine postgres` the run starts its own PostgreSQL 16.15 target and 15.19
old-version instances (`surprise/experiments/pg_instance.py`) and removes
them at the end; it reuses existing ones only when both
`COEVO_TARGET_PG_DSN` and `COEVO_OLD_PG_DSN` are set.

`--llm-tier` picks the endpoint for every role call: `fast` and `strong` are
DeepSeek; `glm-flash` is GLM 5.3 Flash through OpenRouter (provider order and
reasoning effort in `surprise/roles/providers.py`), the tier the S19 runs use.
Every tier reads its key from `DEEPSEEK_API_KEY`, so on a machine that runs
`glm-flash` that variable holds an OpenRouter key (this is how the server is
set up, `surprise/docs/SERVER.md` §5.2).

```bash
# API key is read from the environment; never put it in YAML.
export DEEPSEEK_API_KEY=...

# Hunter loop (roles off)
python -m surprise.experiments.loop --out DIR --seed 0 --engine duckdb --max-minutes 10

# Same on PostgreSQL, with every role on the GLM tier
python -m surprise.experiments.loop --out DIR --seed 0 --engine postgres --max-minutes 10 \
    --llm prior --llm implementer --llm conjecturer --llm-tier glm-flash

# Experiment grid, then a status dump
python -m surprise.experiments.grid run CONFIG --out DIR
python -m surprise.experiments.grid status DIR

# RQ1–RQ6 report and figures from a finished grid
python -m surprise.metrics.report GRID_DIR

# Baseline arms
# pure_llm calls the LLM and needs DEEPSEEK_API_KEY; --llm-offline answers from the cache only
python -m surprise.baselines.pure_llm --out DIR --seed 0
python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N
```

`python -m surprise.experiments.loop --help` lists every flag (engines,
oracles, freeze, Hunter policy, theory snapshots, LLM cache and cap).
`python -m surprise.baselines.old_no_llm --help` lists `--mode` (default
`no_llm`).

Alerts and archives for grid runs:

```bash
# Push alerts (credit exhausted, failing calls, stalls, grid finished) through pushplus;
# reads results only, needs PUSHPLUS_TOKEN, stops when the grid ends
python -m surprise.notify.watch results/NAME --pid GRID_PID

# Pack a finished grid, verify the archive, then prune the raw directory
python -m surprise.experiments.archive pack results/NAME --dest NAME.tar.gz
python -m surprise.experiments.archive verify NAME.tar.gz
python -m surprise.experiments.archive prune results/NAME --archive NAME.tar.gz
```

On the experiment server, grids are started by the scripts in
`surprise/docs/runs/`, following the runbooks next to them. The current ones
(`surprise/docs/runs/e1.sh`, `surprise/docs/runs/e1_pilot_glm.sh`) run each
grid from `results/NAME.work`, so SQL that an experiment generates cannot
write files into the code checkout. `surprise/docs/SERVER.md` §5 is
the full runbook.

## Tests and gates

```bash
# From framework/. Do not run bare `pytest`: framework/test_api.py
# calls the DeepSeek API when the key is set.
python -m pytest -q testing tests

# Every session gate; exit code 0 = pass
python -m surprise.gates.all
```

Gates depend on machine-local resources (engine venvs, the PostgreSQL
reference and binaries, source checkouts, the pinned S8 artifacts) listed in
the root [README](../README.md#setting-up-a-machine), and several compare
against session tags. Current gate results and known failures are in
[surprise/docs/HANDOFF.md](surprise/docs/HANDOFF.md).

## The old CoevoDB (baseline arm)

The original LLM Hunter/Fixer co-evolution loop lives in
`surprise/baselines/coevodb_v1/`. `main.py` forwards to it, so

```bash
python main.py --engine duckdb --mode no_llm ...
```

is the same as `python -m surprise.baselines.coevodb_v1.main ...`. Nine
`--mode` values: `full`, `random_category`, `no_llm`, `coverage_only`,
`dce_only`, `shuffled_diag`, `coevo`, `coevo_warm`, `coevo_frozen`. As a
comparison arm, run it by wall-clock with
`python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm]`.

Examples of the forwarded entry point:

```bash
# Feedback-guided campaign on DuckDB
python main.py --engine duckdb --mode full --iterations 100 \
    --queries-per-iter 8 --seed-mutations-per-iter 20

# PostgreSQL (pgserver launches an embedded PG 16.2 automatically)
python main.py --engine postgres --mode full --iterations 100 \
    --pg-datadir /tmp/coevo_pg

# Ablations
python main.py --engine duckdb --mode random_category ...   # no feedback
python main.py --engine duckdb --mode no_llm ...            # seed-only
```

### Bug verdict taxonomy

| verdict | meaning |
|---|---|
| `true_bug` | sound oracle hit or adjudicated mismatch, minimized + deduped |
| `false_positive` | oracle fired but triage showed the test/rewrite was invalid |
| `version_divergence` | old vs new DuckDB differ; not counted as a bug |
| `cross_engine_divergence` | PG vs DuckDB differ; supporting evidence only |
| `skipped_nondeterministic` | ordering ties / volatile functions make the test unjudgeable |

Only `true_bug` counts toward campaign goals. Version and cross-engine
divergences are reported separately.

### Honesty boundaries

- The first confirmed bug (DuckDB deliminator `EXISTS` self-join, see
  `results/run_20260913_234645`) was found in iteration 0, before feedback had
  any effect — it validates the oracle pipeline, not the co-evolution claim.
- `version_divergence` and `cross_engine_divergence` are never counted as bugs.
- UCB1 regret bounds assume a fixed arm set and stationary rewards; Fixer-spawned
  root-cause arms break stationarity, so the bandit guarantee is empirical, not
  a theorem we claim for the full system.

See [RESEARCH_PLAN.md](RESEARCH_PLAN.md) for hypotheses and experiment gates,
and [BRIEF_coevo_framework.md](BRIEF_coevo_framework.md) for the engineering spec.

## Machine-local paths

A few entry points need resources that live outside the checkout. Every
one is overridable via environment variables (`util/paths.py`); the
fallbacks are the original developer layout (`~/work/db_safety/...`) and
simply won't resolve on a fresh clone — set the variables instead of
editing source.

| env var | resource |
|---|---|
| `DEEPSEEK_API_KEY` | LLM credential (referenced as `${DEEPSEEK_API_KEY}` in config.yml) |
| `COEVO_PGBLD` | root of PG assert/ASan build prefixes (`pg186_assert`, `pgmaster_inject`, ...) |
| `COEVO_PG_PREFIX` | full install prefix used by PostgresRunner (overrides `--build` resolution) |
| `COEVO_PG_EXTRA_OPTS` | extra postmaster `-c` opts for LocalPgServer |
| `COEVO_OLD_VENV` | old-DuckDB venv for the differential oracle (or `--old-duckdb-venv`) |
| `COEVO_DUCKDB_SRC` | DuckDB source checkout for `archive/repair_bench/run_localize.py` |
| `COEVO_ARGUS_DIR` | sibling Argus checkout for `scripts/argus_*` |
| `COEVO_KEYS_YML` | `{key, completion_url}` file for repair_bench drivers |

Script docstrings use `$COEVO_PGBLD/<build>` as the canonical prefix form.

The surprise framework finds its resources under the repository root (through
the git common directory, so every worktree shares one copy) and works on a
fresh clone once they are in place. These variables override the defaults:

| env var | resource |
|---|---|
| `PUSHPLUS_TOKEN` | pushplus token for the `surprise.notify` alerts |
| `COEVO_VENVS` | directory of the versioned interpreters (default `.venvs`) |
| `SURPRISE_SOURCE_ROOT` | parent of the engine source checkouts the LLM roles read (default `.src`) |
| `COEVO_REFERENCE_PG_DSN` | PostgreSQL reference for Cross-DBMS (default host 127.0.0.1, port 55432, user `coevo`) |
| `COEVO_TARGET_PG_DSN`, `COEVO_OLD_PG_DSN` | PostgreSQL target (16.15) and old-version (15.19) instances; set by each run for its own instances, or set both to reuse running ones |
| `COEVO_PG_BIN`, `COEVO_PG_OLD_BIN` | `bin` directories of 16.15 and 15.19 for the per-run instances (default under `.orch/pg16` and `.orch/pg15`) |
| `COEVO_JAVA`, `COEVO_SQLANCER_HOME` | Java and the SQLancer build for the SQLancer arm (default `.orch/jdk` and `.orch/sqlancer`) |
