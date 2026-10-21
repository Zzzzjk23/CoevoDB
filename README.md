# CoevoDB

Research code for finding logic bugs in database engines, plus curated
reproducers of the bugs it has confirmed.

- `framework/` is the code. The current system is the surprise-driven
  framework in `framework/surprise/`: a falsifiable theory predicts a failure
  probability for every experiment, Hunter picks the next experiment by
  information value, and labels come only from seven oracles plus the CVE
  (Contract-Verified Evidence) pipeline. The LLM is never the bug oracle.
  The original CoevoDB (LLM Hunter/Fixer co-evolution) is kept as a baseline
  arm at `framework/surprise/baselines/coevodb_v1/`. Architecture:
  [framework/surprise/ARCHITECTURE.md](framework/surprise/ARCHITECTURE.md).
- `duckdb/`, `datafusion/`, `sqlite/`, `tidb/`, `postgres/`, `mariadb/`,
  `mysql/` hold the bug reproducers and `docs/` their evidence trail (see
  [Confirmed bug reproducers](#confirmed-bug-reproducers-31-families) below).

## Where the project stands

Work is cut into numbered sessions, each with one deliverable and one gate
(`framework/surprise/docs/SESSIONS.md`). S0–S12 migrated the old system to
the surprise-driven framework; S13 onward is the formal experiment campaign
(E1–E7 in `framework/surprise/docs/EXPERIMENT.md`), run on a dedicated
experiment server.

As of 2026-10-22: S0–S15 are done. S16 (PostgreSQL 16.15 as a target) has all
of its local code merged and is paused before its close-out. S19 (E1, the
DuckDB main comparison) is in its pilot stage on the server; the formal grid
waits for the project owner. **The live state, open issues and next steps are in
[framework/surprise/docs/HANDOFF.md](framework/surprise/docs/HANDOFF.md)**,
which is always newer than this README.

Git conventions: each session works on a branch session/sNN and ends with a
tag `sNN-done` (`sNN-done-r2` after acceptance fixes); work packages run on
branches grok/&lt;package&gt;; tags `sNN-deploy-N` mark what was deployed to the
server. `main` lags behind the session branches (last merge: S15).

## Reading order

The project documents under `framework/surprise/docs/` are written in Chinese.

1. `CLAUDE.md` — the rules every session follows, human or agent.
2. [framework/surprise/ARCHITECTURE.md](framework/surprise/ARCHITECTURE.md) — the parts of the framework.
3. [PLAN.md](framework/surprise/docs/PLAN.md) — the overall plan. Read-only; it
   changes only on the project owner's decisions (§9 lists them).
4. [SESSIONS.md](framework/surprise/docs/SESSIONS.md) — scope, deliverables and gate of every session.
5. [EXPERIMENT.md](framework/surprise/docs/EXPERIMENT.md) — the formal experiment protocol.
6. [HANDOFF.md](framework/surprise/docs/HANDOFF.md) — current state and open issues.
7. [DECISIONS.md](framework/surprise/docs/DECISIONS.md) — decision log, append-only.
8. [SERVER.md](framework/surprise/docs/SERVER.md) — the experiment server: environment, deployment, runbook.
9. [ORCHESTRATION.md](framework/surprise/docs/ORCHESTRATION.md) — how a session is run: the
   orchestrator writes the gate first, executors implement each work package
   in their own worktree (`tools/orch/grok_worker.py`), the orchestrator
   reviews and merges.
10. [framework/README.md](framework/README.md) and [framework/AGENTS.md](framework/AGENTS.md) — commands,
    environment variables, PostgreSQL notes.

## Ground rules

The full list is in `CLAUDE.md`; these are the ones that bite first.

- Secrets come only from environment variables (`DEEPSEEK_API_KEY`,
  `PUSHPLUS_TOKEN`). Never print them or put them in code, configs, logs,
  commits or chat. Everyone uses their own keys.
- The LLM never labels a case. Labels come only from the seven oracles plus CVE.
- `framework/surprise/harness/` and the manifest constants are frozen (the
  gates check the hash). S16 unfroze and re-froze them for PostgreSQL;
  any further change needs the project owner.
- Do only the current session's scope. Anything else goes into the open
  issues of HANDOFF.md. Each gate (`framework/surprise/gates/`) is written
  before the work it checks, and every earlier gate stays green.
- One orchestrator per session branch at a time.
- Only one person deploys to and launches runs on the experiment server. Never
  touch a running grid. The server checkout only ever checks out tags.

## Setting up a machine

Everything below is outside git (gitignored) and lives under the repository
root, with the same layout on Windows and on the server. Exact versions are in
SERVER.md §2 and the machine-readable list in SERVER.md §7.

| path | contents |
|---|---|
| `.venv` | main environment, Python 3.13.9: DuckDB 1.5.5, DataFusion 54.0.0, psycopg2-binary 2.9.13, sqlglot 30.21.0, pytest, matplotlib, scipy |
| `.venvs/duckdb-1.1.3` | DuckDB 1.1.3 plus psycopg2-binary (Version differential subprocess) |
| `.venvs/duckdb-1.1.3-full` | the whole framework on DuckDB 1.1.3 (S8 recall, E4) |
| `.venvs/datafusion-50.0.0` | DataFusion 50.0.0 and pyarrow (Version differential subprocess) |
| `.src/duckdb-v1.5.5`, `.src/datafusion-54.0.0`, `.src/postgresql-16.15` | engine sources the LLM roles read, at pinned commits (`framework/surprise/roles/constants.py`, `framework/surprise/roles/sources_map.py`) |
| `.orch/pg16` | PostgreSQL 16.15: the reference server on 127.0.0.1:55432, user `coevo`, and the binaries for per-run target instances |
| `.orch/pg15` | PostgreSQL 15.19 binaries (Version differential on PostgreSQL) |
| `.orch/jdk`, `.orch/sqlancer` | JDK 21 and the patched SQLancer build (SERVER.md §8) |
| `framework/results/s08/` | the four pinned S8 artifact directories (`pre`, `longrun`, `old_no_llm`, `recall113`); the gates check their bytes, so copy them, do not regenerate them |

The repository root also has `duckdb/` and `datafusion/` reproducer
directories, so `import duckdb` from the root "succeeds" without the package;
check `__version__` when verifying an environment. Machine-local paths can be
overridden by environment variables (table in
[framework/README.md](framework/README.md#machine-local-paths)).

## Tests and gates

Run from `framework/` with the main environment's interpreter
(`.venv/bin/python` on Linux). Do not run bare `pytest`: `framework/test_api.py`
calls the DeepSeek API when the key is set.

```bash
cd framework
../.venv/Scripts/python.exe -m pytest -q testing tests   # about 10 minutes
../.venv/Scripts/python.exe -m surprise.gates.all        # about an hour; exit code 0 = every gate passes
```

Several gates compare against session tags, so a clone needs the tags too.
More commands (Hunter loop, grids, reports, baselines, alerts, archives) are
in [framework/README.md](framework/README.md).

## Confirmed bug reproducers (31 families)

Confirmed logic bugs found during the earlier campaigns (multi-oracle
differential + plan-variant + metamorphic testing). Each directory contains
self-contained reproducers: a commented `.sql` file per bug family (version,
expected vs actual, upstream references), plus standalone verifier scripts
where applicable.

| engine | version | family | manifestation | status |
|---|---|---|---|---|
| DuckDB | 1.5.5 | [F1](duckdb/F1_correlated_exists_delim.sql) | correlated EXISTS self-join drops rows (deliminator + filter_pushdown) | still on main `d8cdaa3` |
| DuckDB | 1.5.5 | [F2](duckdb/F2_window_dup_partition.sql) | `PARTITION BY a,a` duplicate key mis-merged | fixed on main |
| DuckDB | 1.5.5 | [F5](duckdb/F5_parallel_cte_offset.sql) | CTE+OFFSET parallel row-drop (flaky) | worse on 1.5.5 than 1.1.3 |
| DuckDB | 1.5.5 | [F6](duckdb/F6_null_exists_notin.sql) | NULL/EXISTS (NOT-IN shape) wrong result | longstanding |
| DuckDB | 1.5.5 | [F7](duckdb/F7_interval_cse.sql) | interval equality is not a congruence (CSE substitution) | still on main `d8cdaa3` |
| DuckDB | 1.5.5 | [F10](duckdb/F10_window_frame_underflow.sql) | window frame-bound underflow: SIGFPE + INTERNAL + silent garbage | minimal shape fixed on main |
| DuckDB | 1.5.5 | [F11](duckdb/F11_merge_nmbs_rowid.sql) | MERGE without INSERT branch -> `Failed to bind rowid` INTERNAL | 1.5.5 release |
| DataFusion | 54.0.0 | [DF-A](datafusion/DF-A_except_all.sql) | `EXCEPT ALL` drops multiplicity and NULL rows | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-B](datafusion/DF-B_intersect_all.sql) | `INTERSECT ALL` returns LHS multiplicity, not min | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-D](datafusion/DF-D_generated_column.sql) | `GENERATED ALWAYS AS ... STORED` silently returns NULL | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-E](datafusion/DF-E_correlated_cte_alias.sql) | correlated subquery rejected outside WHERE; recursive CTE alias list dropped | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-F](datafusion/DF-F_using_key_coalesce.sql) | USING/NATURAL merged key NULL on RIGHT/FULL outer rows | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-G](datafusion/DF-G_decimal_literal.sql) | high-precision numeric literal silently loses precision | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-H](datafusion/DF-H_recursive_count.sql) | `count(*)` over recursive CTE -> internal error / Rust panic | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-I](datafusion/DF-I_all_subquery.sql) | `expr op ALL (subquery)` w/ unprojected column -> assertion | confirmed on 54.0.0 |
| DataFusion | 54.0.0 | [DF-J](datafusion/DF-J_lateral_unnest.sql) | lateral `UNNEST` unplannable | confirmed on 54.0.0 |
| SQLite | 3.51.2 | [SQLITE-A](sqlite/SQLITE-A_star_using_rightjoin.sql) | `SELECT *` over RIGHT/FULL + USING merged column -> spurious ambiguous column | deterministic 10/10 |
| SQLite | 3.51.2 | [SQLITE-B](sqlite/SQLITE-B_using_ambiguity.sql) | USING/NATURAL ambiguity check direction-asymmetric | deterministic 10/10 |
| SQLite | 3.51.2 | [SQLITE-C](sqlite/SQLITE-C_unistr.sql) | `unistr()` emits malformed UTF-8 (no surrogate pairing) | deterministic 10/10 |
| TiDB | v8.5.8 | [TIDB-A](tidb/TIDB-A_time_overflow.sql) | TIME overflow unchecked in TiDB layer (vs MySQL 9.7.1) | upstream pingcap/tidb#56865 still open |
| TiDB | v8.5.8 | [TIDB-B](tidb/TIDB-B_decimal_division.sql) | decimal division extra internal precision (compat gap) | low severity |
| PostgreSQL | 17.11/18.6/master | [PG-A](postgres/PG-A_excl_spgist_ndcoll.sql) | `EXCLUDE USING spgist` + nondeterministic collation -> constraint silently unenforced | novel (BUG #19641 covers query path only) |
| PostgreSQL | 17.11/18.6/master | [PG-B](postgres/PG-B_interval_out_reparse.sql) | `interval_out` emits literal `interval_in` rejects -> pg_dump file unrestorable | novel |
| PostgreSQL | 17.11/18.6/master | [PG-C](postgres/PG-C_time_interval_overflow.sql) | `time_mi`/`timetz_pl`/`timetz_mi` int64 wrap -> silent wrong time | extends BUG #19670 (1 of 4 sites reported) |
| PostgreSQL | 17.11/18.6 | [PG-D](postgres/PG-D_ssi_arbiter_probe.sql) | `ON CONFLICT` arbiter probe takes no SIREAD -> all-commit G2-item | known (Yandex thread); fixed master, not backported |
| PostgreSQL | 17.11/18.6/master | [PG-E](postgres/PG-E_ssi_doom_swallow.sql) | 40001 raised before SXACT_FLAG_DOOMED -> SAVEPOINT/plpgsql swallows it, txn commits | known (CF 6904); indep. repro + plpgsql path + A/B |
| PostgreSQL | 16.2..master | [PG-F](postgres/PG-F_memoize_param.sql) | Memoize key omits join param -> stale cache, wrong count | known (CF 7175/ee2bbec); A/B verified |
| PostgreSQL | 18.6/master | [PG-G](postgres/PG-G_bit_input_diag.sql) | `pg_input_error_info` vs real coercion disagree on SQLSTATE for `bit` | novel, low severity (diagnostics only) |
| MariaDB | 11.8.9 | [MDB-A](mariadb/MDB-A_quantified_doubleneg.sql) | `NOT(NOT(x <op> ANY/ALL))` returns complement; `<>` newly affected | upstream #121079/MDEV-40443 open |
| MariaDB | 11.8.9 | [MDB-B](mariadb/MDB-B_mergeview_window_quantified.sql) | merged source x window/agg x quantified -> empty set; derived/CTE hit | extends MDEV-40557/40780 (12 new shapes) |
| MySQL | 8.4.2 | [MYSQL-A](mysql/MYSQL-A_quantified_doubleneg.sql) | `NOT(NOT(quantified))` wrong result on 8.4 LTS | upstream #121079 (fixed only in 9.7) |

Run artifacts (`results/`, `framework/archive/repair_bench/runs/`) are
gitignored — the published bugs above are the curated outcome of ~200k
executions.

### Running the reproducers

Each `.sql` file is self-contained: header comments give version,
expected vs actual output, and upstream references.

- **DuckDB**: `python -c "import duckdb; ..."` or the `duckdb` CLI, e.g.
  `duckdb -c ".read duckdb/F7_interval_cse.sql"` (verified on `duckdb==1.5.5`).
- **DataFusion**: `pip install datafusion==54.0.0`, feed each statement
  to `SessionContext().sql(...)`.
- **SQLite**: any `sqlite3` >= 3.51 (the `unistr()` cases need 3.51+).
  A standalone verifier is included: `python sqlite/sqlite_unistr_hunt.py`.
- **TiDB**: `tiup playground` on 127.0.0.1:4000 plus a MySQL reference
  (divergence vs MySQL 9.7.1 is the oracle).
- **PostgreSQL**: `psql -f postgres/<file>.sql` against 17.x/18.x
  (PG-A needs an ICU build; PG-D/PG-E are two-session choreography —
  run the commented steps on two SERIALIZABLE connections in order).
- **MariaDB / MySQL**: feed each file to the `mariadb`/`mysql` client;
  the oracle is `NOT(NOT P) ≡ P` evaluated by the engine itself.

### Evidence (`docs/`)

- [UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md) — report-ready write-up
  per family, ranked by reportability (including excluded tiers and why)
- [FAMILY_LEDGER_155.md](docs/FAMILY_LEDGER_155.md) — full DuckDB 1.5.5
  ledger: signatures, version ladder, cross-engine adjudication
- [FAMILY_CASE_STUDIES.md](docs/FAMILY_CASE_STUDIES.md) — upstream
  "same-family recurrence" case studies motivating the family model
- [frame_fuzz_report.md](docs/frame_fuzz_report.md) — F10 fuzz campaign
  (828k combos, 10,670 hits: 1,836 SIGFPE + 2,866 INTERNAL + ~2,950 garbage)
- [FINAL_REPORT.md](docs/FINAL_REPORT.md) — campaign totals + SQLancer
  baseline comparison
- [manual_findings.jsonl](docs/manual_findings.jsonl) — curated family
  records; [recall_repros.json](docs/recall_repros.json) — canonical
  setup/query/fix_set per family

### Scope note

Only confirmed-tier families are included. Cases adjudicated as
unspecified-semantics / debug-setting / user-setting / spec-observation
(F3, F8, F9, F12, F13, DF-C) are documented in
[docs/UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md) but intentionally
not filed as bug reproducers.
