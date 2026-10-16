# 报告 · s12-move

## 改了哪些文件

提交 `c331f54`（纯 `git mv`，相似度 100%）和 `07eff4c`（导入、锚点、新文件）。`git log --follow` 能从新路径追回 `55c5512`。工作区干净。

- `framework/surprise/baselines/coevodb_v1/main.py`：移动自 `framework/main.py`；改了导入和 `PROJECT_DIR` 锚点。
- `framework/surprise/baselines/coevodb_v1/evolution/{bandit,co_evolution,coverage,playbook}.py`：移动自 `framework/evolution/`，内容未改。
- `framework/surprise/baselines/coevodb_v1/agents/bug_hunter.py`：移动自 `framework/agents/bug_hunter.py`；相对导入改为 `agents.*`，`coverage.features` 改为新路径。
- `framework/surprise/baselines/coevodb_v1/guidelines/{__init__.py,llm_guideline.py}`：移动自 `framework/guidelines/`，内容未改。
- `framework/surprise/baselines/coevodb_v1/coverage/{features.py,store.py}`：移动自 `framework/coverage/`，内容未改。
- `framework/surprise/baselines/coevodb_v1/coverage/__init__.py`：移动自 `framework/coverage/__init__.py`；两条导入改为新路径。
- `framework/archive/coevo/` 下 8 个文件：移动自 `framework/coevo/`，内容未改。
- `framework/archive/repair_bench/` 下 9 个文件：移动自 `framework/repair_bench/`；`run_bench.py` 与 `run_localize.py` 只改了 `sys.path` 锚点。
- `framework/surprise/baselines/coevodb_v1/__init__.py`：新增，仅 docstring。
- `framework/surprise/baselines/coevodb_v1/evolution/__init__.py`：新增，仅 docstring。
- `framework/surprise/baselines/coevodb_v1/agents/__init__.py`：新增，仅 docstring。
- `framework/archive/__init__.py`：新增，仅 docstring。
- `framework/archive/README.md`：新增，说明归档了 `coevo` 与 `repair_bench`。
- `framework/main.py`：新增转发器，跑 `surprise.baselines.coevodb_v1.main`。
- `framework/evolution/__init__.py`：修改，`coevo.controller` 改为 `archive.coevo.controller`。
- `framework/campaigns/pg_coldstart.py`：修改，`evolution.coverage` 改为新路径。
- `framework/scripts/corpus_hunt.py`、`flaky_mine.py`、`llm_rule_gen.py`：修改，`evolution.co_evolution` 改为新路径。
- `framework/scripts/make_playbook_seed.py`、`make_playbook_seed_v2.py`：修改，`evolution.playbook` 与 `repair_bench.run_bench` 改为新路径。
- `framework/testing/test_new_components.py`：修改，`evolution.bandit`、`coverage.features`、`coverage.store` 改为新路径。
- `framework/tests/test_diagnosis_dce.py`：修改，函数内 `evolution.bandit` 改为新路径。
- `framework/tests/test_verified_loop.py`、`framework/test_simple.py`：修改，`coevo` 改为 `archive.coevo`。
- `framework/tests/test_surprise_s11_grid.py`：修改，只把核对 `--mode` 表的那一处读路径改到搬走后的 `main.py`。
- `.gitignore`：修改，`framework/repair_bench/runs/` 改为 `framework/archive/repair_bench/runs/`。

`git diff -M --stat session/s12..HEAD`：

```
 .gitignore                                         |   2 +-
 README.md                                          |  24 +-
 framework/AGENTS.md                                |  40 +--
 framework/README.md                                | 147 ++++------
 framework/archive/README.md                        |   7 +
 framework/archive/__init__.py                      |   1 +
 framework/{ => archive}/coevo/__init__.py          |   0
 framework/{ => archive}/coevo/archive.py           |   0
 framework/{ => archive}/coevo/controller.py        |   0
 framework/{ => archive}/coevo/executor.py          |   0
 framework/{ => archive}/coevo/generator.py         |   0
 framework/{ => archive}/coevo/models.py            |   0
 framework/{ => archive}/coevo/policy.py            |   0
 framework/{ => archive}/coevo/repair.py            |   0
 .../repair_bench/cases/sqlite_c/code_excerpt.c     |   0
 .../repair_bench/cases/sqlite_c/reproducers.tsv    |   0
 .../repair_bench/cases/sqlite_c/sanity.tsv         |   0
 framework/{ => archive}/repair_bench/run_bench.py  |   2 +-
 .../{ => archive}/repair_bench/run_localize.py     |   2 +-
 .../repair_bench/src_pristine/shell.c              |   0
 .../repair_bench/src_pristine/sqlite3.c            |   0
 .../repair_bench/src_pristine/sqlite3.h            |   0
 .../repair_bench/src_pristine/sqlite3ext.h         |   0
 framework/campaigns/pg_coldstart.py                |   2 +-
 framework/coverage/__init__.py                     |   6 -
 framework/evolution/__init__.py                    |   2 +-
 framework/main.py                                  | 311 +--------------------
 framework/scripts/corpus_hunt.py                   |   2 +-
 framework/scripts/flaky_mine.py                    |   2 +-
 framework/scripts/llm_rule_gen.py                  |   2 +-
 framework/scripts/make_playbook_seed.py            |   4 +-
 framework/scripts/make_playbook_seed_v2.py         |   4 +-
 framework/surprise/ARCHITECTURE.md                 | 172 ------------
 .../surprise/baselines/coevodb_v1/__init__.py      |   4 +
 .../baselines/coevodb_v1/agents/__init__.py        |   1 +
 .../baselines/coevodb_v1}/agents/bug_hunter.py     |   6 +-
 .../baselines/coevodb_v1/coverage/__init__.py      |   6 +
 .../baselines/coevodb_v1}/coverage/features.py     |   0
 .../baselines/coevodb_v1}/coverage/store.py        |   0
 .../baselines/coevodb_v1/evolution/__init__.py     |   1 +
 .../baselines/coevodb_v1}/evolution/bandit.py      |   0
 .../coevodb_v1}/evolution/co_evolution.py          |   0
 .../baselines/coevodb_v1}/evolution/coverage.py    |   0
 .../baselines/coevodb_v1}/evolution/playbook.py    |   0
 .../baselines/coevodb_v1}/guidelines/__init__.py   |   0
 .../coevodb_v1}/guidelines/llm_guideline.py        |   0
 framework/surprise/baselines/coevodb_v1/main.py    | 310 ++++++++++++++++++++
 framework/surprise/docs/HANDOFF.md                 |   6 +-
 framework/surprise/docs/orch/s12/s12-docs.brief.md | 109 --------
 .../surprise/docs/orch/s12/s12-docs.report.md      |  56 ----
 .../surprise/docs/orch/s12/s12-docs.review.md      | 181 ------------
 .../surprise/docs/orch/s12/s12-docs.rework1.md     |  21 --
 framework/test_simple.py                           |   8 +-
 framework/testing/test_new_components.py           |   6 +-
 framework/tests/test_diagnosis_dce.py              |   2 +-
 framework/tests/test_surprise_s11_grid.py          |   2 +-
 framework/tests/test_verified_loop.py              |  10 +-
 57 files changed, 436 insertions(+), 1025 deletions(-)
```

`session/s12`（`0c146e9`）不是本分支的祖先。合并基是 `938aee0`。上面这份两端比较把已经合进 `session/s12` 的 s12-docs（README、AGENTS、ARCHITECTURE、HANDOFF、`docs/orch/s12/s12-docs.*`）显示成了本分支相对那边的缺失。本包没有改这些文件。`framework/main.py` 在两端比较里也不显示为重命名，因为转发器占回了原路径；重命名在 `c331f54`，`git log --follow` 可追。`coverage/__init__.py` 同理：改完导入后默认 50% 相似度配不上，重命名提交本身是 100%。

## 跑了哪些命令

命令都在 `framework/` 下执行（除了 git）。五组 S12 门槛拆成三条跑，五组都通过。

### `python -m surprise.gates.s12 --only layout moves`

退出码 0。

```
[PASS] layout: 28 files moved (11 into coevodb_v1, 17 into archive), main.py forwards to surprise.baselines.coevodb_v1.main; 9 shared files and 5 shared directories in place, no copies (0s)
[PASS] moves: 164 old .py files of s11-done-r2 checked: 28 moved files (incl. non-Python) equal modulo import paths and 3 anchors, 11 import-edited in place, 132 untouched (5s)
S12 GATE [only: layout, moves]: PASS (2/2 groups passed)
```

### `python -m surprise.gates.s12 --only imports isolation`

退出码 0。

```
[PASS] imports: 361 files scanned: no import of an old location, every first-party import resolves; 27 moved or shared modules import; 3 scripts answer --help; coevo smoke: executed=5, invalid=0, confirmed_new_bugs=0, new_plans=10 (21s)
[PASS] isolation: no-LLM loop loads none of 4 moved LLM modules; every harness module imported without ['archive', 'surprise.baselines.coevodb_v1']; nothing in surprise/ imports coevodb_v1 (1s)
S12 GATE [only: imports, isolation]: PASS (2/2 groups passed)
```

### `python -m surprise.gates.s12 --only old_arm`

退出码 0。

```
[PASS] old_arm: --help identical at the new location, through main.py and at s11-done-r2; 9 artifacts of a 2-iteration no_llm run equal to the base (3s / 3s); old_no_llm arm 61s, ended killed, metrics keys ['cost', 'rq1', 'rq2', 'rq3'] (70s)
S12 GATE [only: old_arm]: PASS (1/1 groups passed)
```

### `python -m pytest -q testing tests`

退出码 0。输出不足 20 行，以下是末尾全部。

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 30%]
........................................................................ [ 38%]
........................................................................ [ 46%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 92%]
........................................................................ [ 99%]
..                                                                       [100%]
935 passed, 3 skipped in 274.48s (0:04:34)
```

### `python -m surprise.gates.s01`

退出码 0。

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 935 passed (baseline 64): 935 passed, 3 skipped in 323.16s (0:05:23)
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s07`

退出码 0。

```
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (0s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
[PASS] imports: 16 theory files import no model and no old code; 5 import orders load in fresh processes (2s)
[PASS] edits: 20 malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic (0s)
[PASS] accept: hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not (0s)
[PASS] rollback: a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback (0s)
[PASS] journal: reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail (1s)
[PASS] mdl: merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself (2s)
[PASS] families: fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber (0s)
[PASS] ciao: mean surprise of the old records by generation: 0.537, 0.074, 0.074 bits (0s)
[PASS] replay: 74 experiments, 11 hypotheses; confirmed fail: 48, confirmed pass: 5, pending fail: 13, unexplored fail: 4, unexplored pass: 1; 47/54 repeats predicted before execution, 47 at tier 2; wrong edit e1 rolled back by s07-replay:49; compress applied [], declined ['merge:h6+h10:holdout', 'merge:h9+h11:holdout']; absorbed twice: [] (275s)
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (68s)
S07 GATE: PASS (15/15 groups passed)
```

### `python -m surprise.gates.s04`

退出码 0。

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (21s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (21s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (18s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (25s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (40s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (75s)
[PASS] freeze: 51 files (31 in the harness), hash 98b70d9e81fc, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s08`

退出码 1。

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (14s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (56s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (33s)
[FAIL] longrun: artifact directory results/s08/longrun is missing on this machine
[FAIL] sawtooth: artifact directory results/s08/longrun is missing on this machine
[FAIL] duplicates: artifact directory results/s08/longrun is missing on this machine
[FAIL] recall: artifact directory results/s08/recall113 is missing on this machine
S08 GATE: FAIL (7/11 groups passed)
```

没有跑 `python -m surprise.gates.all`。

## 与说明的偏差

- S08 退出码 1。失败的四组要读 `framework/results/s08/longrun` 和 `framework/results/s08/recall113`。这两个目录在本 worktree 里没有（gitignore 的本机产物）。主检出 `D:\CoevoDB\framework\results\s08` 里有，其中 `longrun` 约 723MB。代码侧七组通过；S04 `freeze` 通过，指纹 `98b70d9e81fc`。按说明没有建指向 worktree 外的链接，也没有把产物复制进来。
- `framework/coevo`、`framework/guidelines`、`framework/coverage`、`framework/repair_bench` 还留着空目录（0 个文件）。`git mv` 之后删空目录被权限拒绝，没有换别的办法再删。git 不跟踪它们。`layout` 只检查这些目录里还有没有 `.py`，已经通过。

## 未决问题

- S08 的 longrun / sawtooth / duplicates / recall 要在带有 `results/s08/longrun` 与 `results/s08/recall113` 的检出上再跑一次才能按说明判通过。本包没有改 harness 与 `HASHED_PATHS` 里的文件。
- `session/s12` 在本分支切出之后又合入了 s12-docs（`HEAD..session/s12` 有 5 个提交）。本包按说明没有 merge / rebase。编排者合并时要处理文档与本包移动的交叉。
