# Architecture of the surprise-driven framework

A falsifiable theory \(T\) assigns every experiment a failure probability \(P_T\). Surprise is \(-\log_2 P_T\) of the observed label. Hunter picks the next experiment by expected information value. Diagnoser and the LLM roles propose edits of \(T\); an acceptance rule decides whether each edit stays. Labels come only from seven oracles plus the CVE (Contract-Verified Evidence) pipeline. The LLM never labels.

This document describes the package under `surprise/` for a first-time reader of the repository. The migration plan is `surprise/docs/PLAN.md`.

## Data flow

```text
  Hunter                 harness                      ledger
 (SQL case) --> (execute, 7 oracles, CVE) --------> SQLite
                                                        |
                                                        v
                                                   theory T
                                            (phi, P_T, surprise, triage)
                                                        |
                        +-------------------------------+-------------------------------+
                        |                                                               |
                        v                                                               v
                   Diagnoser                                                     LLM roles
              (no-LLM edits)                                              (optional, gated)
                        |                                                               |
                        +-------------------------------+-------------------------------+
                                                        |
                                                        v
                                              accept or roll back
                                                        |
                                                        v
                                                 theory store
                                                        |
                                                        v
                                              Hunter (next case)
```

Hunter hands a SQL case to the harness. The harness executes it, runs one of the seven oracles, and labels the outcome through CVE. The ledger stores every attempt, including passes and invalids. The theory predicts \(P_T\), scores surprise, and triages the record. High-surprise failures go to Diagnoser; optional LLM roles propose specs, hypotheses, and rewrites. The workbench accepts an edit or rolls it back. The updated store is what Hunter scores against on the next step.

## `surprise/harness/` — frozen evaluator

The harness is the out-of-loop evaluator. It labels a query, writes the experiment record, and never consults an LLM.

- Contracts: `surprise/harness/contracts.py` (`SqlCase`, `Label` with \(y \in \{\mathrm{pass}, \mathrm{fail}, \mathrm{invalid}\}\), `ExperimentRecord`).
- SQLite ledger: `surprise/harness/ledger.py` (`Ledger.start_run`, `append`).
- Run manifest and `HASHED_PATHS`: `surprise/harness/manifest.py`. The hashed set covers this package plus the shared oracle, runner, rewrite, bisect, and minimizer modules it imports. `python -m surprise.harness.manifest verify surprise/gates/s04_frozen.json` checks the freeze.
- Seven oracles, registered in `surprise/harness/oracles/registry.py` and judged by `surprise.harness.oracles.judge`:
  - TLP — `surprise/harness/oracles/tlp.py`
  - NoREC — `surprise/harness/oracles/norec.py`
  - Plan variant — `surprise/harness/oracles/plan_variant.py`
  - Index presence — `surprise/harness/oracles/index_presence.py`
  - Equivalent query — `surprise/harness/oracles/equivalent_query.py`
  - Version differential — `surprise/harness/oracles/version_differential.py`
  - Cross-DBMS — `surprise/harness/oracles/cross_dbms.py`
- CVE, three cost tiers, in `surprise/harness/cve/`. Public entry: `surprise.harness.cve.certify`. Tier 1 reruns every discrepancy in a fresh process and checks premises. Tier 2 runs one attribution test when the theory already owns the failure. Tier 3 minimises and profiles (fix set, plan diff, version ladder) only for failures that go to Diagnoser.
- Callers: `surprise.harness.evaluate.evaluate` (raw oracle label) and `evaluate_final` (CVE label, one ledger row per call). The main loop uses `evaluate_final`.

This package has been frozen since S4. Changing it requires asking first.

## `surprise/features/` — \(\varphi\)

\(\varphi\) is the shared description of a query and the data it runs on. Three layers: AST (`surprise/features/ast.py`, sqlglot with a regex fallback), plan (`surprise/features/plan.py`), and data properties computed on the live tables (`surprise/features/data.py`). The container is `Phi` in `surprise/features/phi.py`.

- Units: `surprise/features/units.py` (`unit_of`, `unit_parts`) project \(\varphi\) onto (engine, oracle, construct, plan class, data class).
- Vocabulary and registry: `surprise/features/vocabulary.py` (`FeatureDef`) and `surprise/features/registry.py` (`Registry`, `default_registry`).
- Spec checker: `surprise/features/spec.py` (`check_spec`) tests \(\varphi(x) \models \mathrm{spec}\).
- Extraction: `surprise.features.extract.extract` in-process; `extract_isolated` in a child. Command: `python -m surprise.features`.

## `surprise/theory/` — theory \(T\)

\(T = (H, R, K^v)\). A hypothesis is a version-space pair \((S, G)\) plus identity \((I, \Delta P, V)\) and evidence. Residual \(R\) and validity \(K^v\) supply the rates that \(P_T\) mixes. Surprise is \(-\log_2 P_T(y \mid \mathrm{valid})\); invalid outcomes have no surprise. Triage buckets a valid outcome by how large that surprise is.

- Version space: `surprise/theory/vspace.py` (`generalize`, `specialize`, `covers`, `reduce_conjunction`).
- Hypotheses: `surprise/theory/hypothesis.py`; identity: `surprise/theory/identity.py`.
- Residual, validity, prediction, triage: `surprise/theory/residual.py`, `surprise/theory/validity.py`, `surprise/theory/predict.py` (`surprise_bits`, `triage`, `Prediction`).
- In-memory theory: `surprise/theory/theory.py` (`Theory.predict`, `Theory.observe`).
- Store, per-generation snapshots, edit log, rollback, negative memory: `surprise/theory/store.py` (`TheoryStore`).
- Acceptance and MDL: `surprise/theory/edits.py`, `surprise/theory/length.py`. Acceptance is in this order: reject if the fingerprint is in negative memory; reject if there are no bets; reject if surprise on the trigger records rises; reject if surprise on the hold-out records rises; reject if (trigger change + hold-out change + length change) is not strictly negative; otherwise accept. A rejection on trigger or hold-out goes into negative memory. A broken bet rolls the theory back to the snapshot before that edit and replays later observations.
- Workbench: `surprise/theory/workbench.py` (`Workbench.create` / `open`, `predict`, `observe`, `propose`, `assess`, `rollback`, `compress`). This is what the loop holds.
- Constants of \(T\) are written into the run manifest by `surprise/theory/manifest.py` and pinned by the session gates. Command: `python -m surprise.theory`.

## `surprise/hunter/` — choosing the next experiment

Four candidate lanes (`LANES` in `surprise/hunter/hunter.py`): refine, generalize, migrate, explore. Scoring is `surprise/hunter/scoring.py`: \(\mathrm{value} = P_{\mathrm{valid}} \times (D + \beta \cdot U)\), with a down-weight for hypotheses that have already been probed. Every \(N\)th choice is reserved for exploration.

- `Hunter.candidates`, `Hunter.choose`, `Hunter.record` are the loop-facing API.
- Operators: `surprise/hunter/operators.py`. \(\varphi\) extraction: `surprise/hunter/extractor.py`.
- Shared mutation operators come from `evolution/dce.py` (Hunter's refine/generalize lanes).

## `surprise/diagnoser/` — LLM-free edits

`surprise/diagnoser/diagnoser.py` (`Diagnoser.after`, `Diagnoser.periodic`) turns a minimised high-surprise failure into a tighter conjunction and fires the periodic MDL compress and checkpoint beats. Minimisation (ddmin) and bisect already ran in CVE tier 3, using `agents/bug_fixer.py` (`_minimize`) and `diagnosis/bisect.py`. Version-space updates on observe are `Theory`'s job; accepting or rolling back an edit is the workbench's. Diagnoser only proposes.

## `surprise/roles/` — LLM gateway

Roles are off unless the loop is given `--llm ROLE`. The gateway (`surprise/roles/gateway.py`) caches by prompt hash + model + seed (`surprise/roles/cache.py`, `cache_key`), accounts per role, and enforces a call cap. A reply without a prediction is rejected (`surprise/roles/schema.py`). Transport (`surprise/roles/transport.py`) reuses `agents/base_agent.py` for the HTTP client and `llm/ledger.py` for the global call ledger; it reads `DEEPSEEK_API_KEY`.

Six roles, each independently switchable (`surprise/roles/runtime.py`, `build_roles`):

| Role | Module | Proposes |
|---|---|---|
| implementer | `surprise/roles/implementer.py` | a SQL case for an open spec |
| conjecturer | `surprise/roles/conjecturer.py` | a hypothesis with bets |
| prior | `surprise/roles/prior.py` | an exploration prior |
| translator | `surprise/roles/translator.py` | a migrated spec |
| vocab_inventor | `surprise/roles/vocab_inventor.py` | a candidate feature |
| oracle_inventor | `surprise/roles/oracle_inventor.py` | a candidate rewrite rule |

## `surprise/experiments/` — main loop and grid

- `surprise/experiments/loop.py`: Hunter → `evaluate_final` → `Workbench.observe` → Diagnoser / roles → accept or roll back. Command: `python -m surprise.experiments.loop --out DIR --seed N --engine duckdb --max-minutes M`. Repeat `--llm ROLE` to turn a role on.
- `surprise/experiments/grid.py`: a JSON config of arm × seed × repeat, one child process per cell. Commands: `python -m surprise.experiments.grid run CONFIG --out DIR` and `python -m surprise.experiments.grid status DIR`.

## `surprise/metrics/` — evaluation from the ledger

Every metric is computed from the ledger (passes and invalids included). Nothing in this package labels.

- RQ1–RQ6 of one run: `surprise/metrics/rq.py` (`run_metrics`).
- CIAO: `surprise/metrics/rq.py` (`ciao(wb)`), generation snapshots of the theory scored on generation batches of records.
- RQ6 family partitions vs human labels: `surprise/metrics/partition.py` (`pair_agreement`).
- RQ6 hypothesis boundary vs upstream fix (`match` / `too_wide` / `too_narrow` / `mixed`): `surprise/metrics/boundary.py`; fix conditions in `surprise/metrics/data/fix_conditions.json`.
- RQ6 known-bug recall: `surprise/metrics/recall.py`.
- Duplicate rate and family counts: `surprise/metrics/dups.py`.
- One-run directory: `surprise/metrics/rundata.py` (`RunData`).
- Surprise curve: `surprise/metrics/curve.py`. Statistical tests (median, Mann–Whitney U, Vargha–Delaney \(\hat{A}_{12}\)): `surprise/metrics/stats.py`.
- Report and figures: `python -m surprise.metrics.report GRID_DIR`.
- Offline \(\sigma\) vs membership-test dedup: `surprise/metrics/dedup.py`. Coverage of upstream regression tests: `surprise/metrics/coverage.py` (measurement only; it does not write labels).

## `surprise/baselines/` — comparison arms

- `surprise/baselines/old_no_llm.py`: wall-clock run of the original CoevoDB. Command: `python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm]`.
- `surprise/baselines/pure_llm.py`: LLM generation through the same oracles and CVE. Command: `python -m surprise.baselines.pure_llm --out DIR --seed N`.
- `surprise/baselines/sqlancer.py`: transcribed SQLancer summary (`surprise/baselines/data/sqlancer_summary.json`); it does not run SQLancer.
- `surprise/baselines/coevodb_v1/`: the original bandit + playbook loop, moved here as a baseline. See [Relation to the old system](#relation-to-the-old-system).

## `surprise/gates/` — session gates

One gate per implementation session, run in order by `surprise/gates/all.py`. From `framework/`: `python -m surprise.gates.all`. Each gate is `python -m surprise.gates.s01` through `python -m surprise.gates.s12`; exit code 0 means that session's checks passed. Executors do not edit this package.

## Invariants

- The LLM never labels. Labels come from the seven oracles plus CVE.
- The harness is frozen from S4: `HASHED_PATHS` in `surprise/harness/manifest.py` and the digest file `surprise/gates/s04_frozen.json`. Theory and feature constants are written into the run manifest and pinned by the gates. Changing a frozen constant requires asking first.
- Until the close-out of this migration, old code is moved, not rewritten. Import paths may change; logic may not.

## Relation to the old system

Shared primitives stay where they were, once (plan A). Moving them would unfreeze the harness (`HASHED_PATHS` includes several of these files) and invalidate the long-run code digests that pin `surprise/hunter/`, `surprise/diagnoser/`, and `surprise/experiments/`.

| Path | Why it stays |
|---|---|
| `evolution/dce.py` | Hunter mutation operators |
| `agents/bug_fixer.py` | CVE tier-3 minimisation (`_minimize`) |
| `agents/base_agent.py`, `agents/json_utils.py` | HTTP client reused by `surprise/roles/transport.py` |
| `llm/ledger.py` | call ledger reused by the gateway |
| `oracles/`, `targets/` | runners and the original oracle implementations the harness wraps |
| `diagnosis/bisect.py`, `diagnosis/signature.py` | bisect / \(\sigma\) tools |
| `scripts/cross_engine.py` | cross-engine quorum used by Cross-DBMS |
| `seeds/`, `util/` | corpus and machine-local paths |

What moved into `surprise/baselines/coevodb_v1/` is only the old loop's private code: `surprise/baselines/coevodb_v1/main.py`; `surprise/baselines/coevodb_v1/evolution/` (bandit, co-evolution, coverage, playbook); `surprise/baselines/coevodb_v1/agents/bug_hunter.py`; `surprise/baselines/coevodb_v1/guidelines/`; and `surprise/baselines/coevodb_v1/coverage/` (AST × plan operator × boundary-value features). `framework/main.py` forwards with `runpy.run_module("surprise.baselines.coevodb_v1.main", ...)`, so `python main.py --engine duckdb --mode no_llm ...` still works. The nine `--mode` values are `full`, `random_category`, `no_llm`, `coverage_only`, `dce_only`, `shuffled_diag`, `coevo`, `coevo_warm`, `coevo_frozen`.

`archive/` holds the early verified co-evolution prototype (`archive/coevo/`) and the patch/localization benchmark (`archive/repair_bench/`). Both remain importable: `evolution/__init__.py` imports `archive.coevo.controller`, and `tests/test_verified_loop.py` covers it. `archive/README.md` says what is archived. Run artifacts under `archive/repair_bench/runs/` are gitignored.

`campaigns/` holds the PostgreSQL campaign scripts (`campaigns/pg_*.py`) that S1 moved out of `scripts/`. What remains in `scripts/` is old-system experiment scripts plus the shared `scripts/cross_engine.py`.

## Document index

| Doc | Role |
|---|---|
| `surprise/docs/PLAN.md` | master plan (read-only unless the user makes a new decision) |
| `surprise/docs/SESSIONS.md` | twelve implementation sessions, deliverables, and gates |
| `surprise/docs/HANDOFF.md` | session-to-session handoff, including each layer's current interface |
| `surprise/docs/DECISIONS.md` | append-only decision log |
| `surprise/docs/ORCHESTRATION.md` | how work packages are dispatched |
