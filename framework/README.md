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

Commands below are run from `framework/`. LLM roles are off by default;
`--llm ROLE` turns one role on (repeatable) and requires `DEEPSEEK_API_KEY`.

```bash
# API key is read from the environment; never put it in YAML.
export DEEPSEEK_API_KEY=...

# Hunter loop (roles off)
python -m surprise.experiments.loop --out DIR --seed 0 --engine duckdb --max-minutes 10

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

## Tests and gates

```bash
# From framework/. Do not run bare `pytest`: framework/test_api.py
# calls the DeepSeek API when the key is set.
python -m pytest -q testing tests

# Every session gate; exit code 0 = pass
python -m surprise.gates.all
```

Gates depend on machine-local resources (engine venvs, a PostgreSQL
reference, source checkouts, long-run artifacts). See
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
