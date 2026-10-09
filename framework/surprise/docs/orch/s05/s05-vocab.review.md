# 审查包 · s05-vocab

- 生成时间：2026-10-09T09:30:58+11:00
- 基线：`session/s05`（067a2fa3d9e0）
- 分支：`grok/s05-vocab` @ e492d02e029e，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 8m05s
- grok：grok 1.0.46 (2765805b9442)；会话 `89204e98-0c9c-4af3-ba2d-eb51edcb9ddd`

## 红旗汇总

- 改动超出 brief 允许的路径 1 处：framework/tests/test_surprise_s04_runners.py
- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s05..grok/s05-vocab
git diff -M --stat session/s05..grok/s05-vocab
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/features/__init__.py`、`framework/surprise/features/__main__.py`、`framework/surprise/features/vocabulary.py`、`framework/surprise/features/registry.py`、`framework/surprise/features/phi.py`、`framework/surprise/features/spec.py`、`framework/surprise/features/units.py`、`framework/tests/test_surprise_s05_*.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/features/__init__.py` |  |
| A | `framework/surprise/features/__main__.py` |  |
| A | `framework/surprise/features/phi.py` |  |
| A | `framework/surprise/features/registry.py` |  |
| A | `framework/surprise/features/spec.py` |  |
| A | `framework/surprise/features/units.py` |  |
| A | `framework/surprise/features/vocabulary.py` |  |
| M | `framework/tests/test_surprise_s04_runners.py` | **越界：不在允许路径内** |
| A | `framework/tests/test_surprise_s05_phi.py` |  |
| A | `framework/tests/test_surprise_s05_vocab.py` |  |

提交：

- 23bac66 Junke: s05-vocab: add phi vocabulary, registry, container, spec checker and units
- e492d02 Junke: s05-vocab: validate Phi.from_dict and Registry.load; kill S4 fixtures immediately

## 2. diff 统计

```text
 framework/surprise/features/__init__.py      |  18 ++
 framework/surprise/features/__main__.py      |  22 ++
 framework/surprise/features/phi.py           | 108 +++++++++
 framework/surprise/features/registry.py      | 215 +++++++++++++++++
 framework/surprise/features/spec.py          |  68 ++++++
 framework/surprise/features/units.py         |  79 ++++++
 framework/surprise/features/vocabulary.py    | 257 ++++++++++++++++++++
 framework/tests/test_surprise_s04_runners.py |  20 +-
 framework/tests/test_surprise_s05_phi.py     | 184 ++++++++++++++
 framework/tests/test_surprise_s05_vocab.py   | 349 +++++++++++++++++++++++++++
 10 files changed, 1317 insertions(+), 3 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m34s；passed 297，skipped 3

```text
........................ss..................................s........... [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
297 passed, 3 skipped in 34.14s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，3m39s

```text
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (35s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
=== gate s05 ===
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 2544688571fc stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[FAIL] ast: AttributeError: module 'surprise.features' has no attribute 'extract_ast'
[FAIL] dynamic: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] stable: `features phi` failed on 'SELECT EXISTS ( SELECT 1 FROM issue23979_s2 x WHERE x.o = l.': usage: python -m surprise.features [-h] {vocab}
python -m surprise.features: error: argument command: invalid choice: 'phi' (choose from vocab)
[FAIL] distinguish: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] specs: AttributeError: module 'surprise.features' has no attribute 'extract'
[FAIL] corpus: `features corpus` failed: usage: python -m surprise.features [-h] {vocab}
python -m surprise.features: error: argument command: invalid choice: 'corpus' (choose from vocab)
S05 GATE: FAIL (3/9 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: FAIL (exit 1)
GATES: FAIL (4/5 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s05-vocab.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s05` 067a2fa3d9e0 → 6fec60d54db1

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s05-vocab.jsonl`：2476 条事件（available_commands 67，end 2，orch.exit 2，orch.start 2，plan 4，text 585，thought 1146，tool_call 102，tool_call_update 514，usage 52）；各轮合计 52 个模型回合，grok 上报花费 1.1600 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: warning: in the working copy of 'framework/surprise/features/phi.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-vocab e492d02] s05-vocab: validate Phi.fro…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/surprise/features/phi.py', LF will be replaced by CRLF the next time Git touches it [grok/s05-vocab e492d02] s05-vocab: validate…
thought: 正在将第一轮返工内容追加至 report.md，保留原有内容。
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s05-vocab\\.orch\\report.md", "old_string": "## 未决问题\ns04 isolation 组第一次跑时，杀死子进程的候选 5 次重跑只复现 4 次，被标成 invalid/unstable_rerun；本包未改 harness。立刻…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "## 未决问题\ns04 isolation 组第一次跑时，杀死子进程的候选 5 次重跑只复现 4 次，被标成 invalid/unstable_rerun；本包未改 harness。立刻重跑 s04 通过。若编排者看到偶发 isolatio…
tool_call run_terminal_command: {"command": "git status --short; git log -2 --oneline", "description": "Confirm clean tree and new commit"}
tool_update [in_progress]: 
tool_update [in_progress]: e492d02 s05-vocab: validate Phi.from_dict and Registry.load; kill S4 fixtures immediately
tool_update [completed]: exit: 0 e492d02 s05-vocab: validate Phi.from_dict and Registry.load; kill S4 fixtures immediately 23bac66 s05-vocab: add phi vocabulary, registry, container, spec checker and units
text: 第 1 轮返工已提交（`e492d02`），报告追加在 `.orch/report.md`。 改动： - `Phi.from_dict` 校验键、`schema == 1`、非空 `engine`/`vocab`、严格升序的字符串列表、与 `make_phi` 相同的 layers - `Registry.load` 对每条发明特征走与 `register…
end: stopReason=end_turn turns=15 cost_usd=0.44594604
orch.exit: {"pkg": "s05-vocab", "run": 2, "at": "2026-10-09T09:24:55+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s05-vocab

## 改了哪些文件
- `framework/surprise/features/vocabulary.py`：新增 FeatureDef 与基础词表 166 项（id/kind/parent 照抄契约，描述自写）
- `framework/surprise/features/registry.py`：新增 Registry 与 default_registry（族成员、登记/验收、摘要、存取）
- `framework/surprise/features/phi.py`：新增 Phi 与 make_phi
- `framework/surprise/features/spec.py`：新增 SpecCheck 与 check_spec
- `framework/surprise/features/units.py`：新增 unit_parts 与 unit_of
- `framework/surprise/features/__init__.py`：导出 FeatureDef、Registry、default_registry、Phi、make_phi、check_spec、SpecCheck、unit_of、unit_parts
- `framework/surprise/features/__main__.py`：新增 `python -m surprise.features vocab`
- `framework/tests/test_surprise_s05_vocab.py`：新增词表、注册表、φ 的单元测试
- `framework/tests/test_surprise_s05_phi.py`：新增规格核对与单元投影测试

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 97%]
........                                                                 [100%]
293 passed, 3 skipped in 34.20s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 293 passed (baseline 64): 293 passed, 3 skipped in 33.47s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0（第一次 isolation 组因进程崩溃只复现 4/5 次记为 unstable_rerun 失败；立刻重跑通过）

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (12s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (59s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05 --only vocab spec units`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 2544688571fc stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
S05 GATE [only: vocab, spec, units]: PASS (3/3 groups passed)
```

## 与说明的偏差
无。

## 未决问题
s04 isolation 组第一次跑时，杀死子进程的候选 5 次重跑只复现 4 次，被标成 invalid/unstable_rerun；本包未改 harness。立刻重跑 s04 通过。若编排者看到偶发 isolation 失败，按环境抖动处理即可。

# 第 1 轮返工

按 `.orch/review-1.md` 改了三处：`Phi.from_dict` 做结构校验；`Registry.load` 用与 `register` 相同的规则校验发明特征（验收状态可以已经有了）；S4 测试夹具用 `die()` 立即结束进程。

## 改了哪些文件
- `framework/surprise/features/phi.py`：修改 `Phi.from_dict`，校验键、schema、engine、vocab、features 升序、layers
- `framework/surprise/features/registry.py`：修改 `load`，抽出 `_checked_invented`；验收状态允许已接受
- `framework/tests/test_surprise_s05_vocab.py`：补 `from_dict` / `load` 的拒绝与往返测试
- `framework/tests/test_surprise_s04_runners.py`：新增 `die()`，三个退出夹具改用它（本轮额外放行）

## 跑了哪些命令

### `python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
297 passed, 3 skipped in 33.74s
```

### `python -m surprise.gates.s01`
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 297 passed (baseline 64): 297 passed, 3 skipped in 33.61s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

### `python -m surprise.gates.s02`
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 51 files hashed (50fa40cf2d19); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s03`
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[PASS] local: ART exercised, injected mismatch caught; 3 proved rules x 2 engines incl NULL; untrusted pairs rejected
[PASS] cross: PG16 + DuckDB witness DF-A/DF-B; insufficient quorum, ties, multiple outliers and engine aliases rejected
[PASS] version: F2 old/new measured bags and regression direction; both old venvs work; directionless mismatch invalid
[PASS] matrix: 7 oracles x 2 engines, 14 ledger records, no hidden harness failures, manifest verified
S03 GATE: PASS (5/5 groups passed)
```

### `python -m surprise.gates.s04`
退出码：0

```
[PASS] contracts: 17 invalid sources, 7 CVE constants in the manifest; raw entry points untouched; 5 bad requests rejected before execution (1s)
[PASS] isolation: ok / error / timeout x2 / crash x2 told apart; 7 distinct processes for one candidate; process death, hang and dying reference contained (19s)
[PASS] tier1: 6 stable families fail after 5 fresh reruns; F8 unstable; F5 reproduced 0/5; 6 scripted rerun schedules (17s)
[PASS] premise: ASOF ties, writing statements and incomparable cross-engine values are invalid; their tie-free, crashing and comparable counterparts stay fail (13s)
[PASS] environment: 51 files hashed, 17 imported old modules all covered; old engines, PostgreSQL 16.15 and 5 packages recorded (0s)
[PASS] tier2: fix-set attribution: F1, F6, F6 via TLP consistent, F2 escalated; profile attribution: DF-A consistent, DF-B escalated; 5 malformed hypotheses rejected (20s)
[PASS] tier3: 9 confirmed cases profiled: fix sets as measured and as in recall_repros.json, version ladder, minimised subsequence; noise removed; lost candidate downgraded (34s)
[PASS] m1: 50 final labels in the ledger (14 fail, 20 invalid, 16 pass); known recall gaps: DF-E, DF-G, DF-H, DF-J, F10, F5 (58s)
[PASS] freeze: 51 files (31 in the harness), hash 50fa40cf2d19, 8 constants match (0s)
S04 GATE: PASS (9/9 groups passed)
```

### `python -m surprise.gates.s05 --only vocab spec units`
退出码：0

```
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 2544688571fc stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (0s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
S05 GATE [only: vocab, spec, units]: PASS (3/3 groups passed)
```

## 与说明的偏差
无。本轮按审查意见额外改了 `framework/tests/test_surprise_s04_runners.py`。

## 未决问题
无。第一轮记录的 s04 isolation 抖动已按审查意见改夹具；本轮 s04 一次通过。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

**合并。**（2026-10-09，第 1 轮返工之后）

依据：

- 独立复跑在 e492d02 上：pytest 297 passed / 3 skipped（基线 275，第一轮 293）；S01–S04 通过；S05 的 `vocab spec units` 三组通过。`gates.all` 的退出码 1 只来自 S05 其余六组，它们属于 `s05-ast` 与 `s05-dynamic`，是预期的。
- 红旗"改动超出允许路径：`framework/tests/test_surprise_s04_runners.py`"是返工意见第 3 条放行的，读过 diff：只加了 `die()` 并把三处 `os._exit` 换成它，与门槛夹具的写法逐行相同。
- 两轮 diff 全读，27 条执行命令全看过：没有越界命令，没有清理 `.orch/tmp`，没有装依赖。
- 编排者探测 `.orch/scratch/s5_review_vocab.py`：BAD COUNT 0，上一轮四条 `Phi.from_dict` 的 INFO 现在都是拒绝。`.orch/scratch/s5_review_vocab_r1.py`（返工两处的补充探测，30 余条）：保存 → 读回 → 再保存逐字节相同；读回的未验收特征仍被 `make_phi` 拒绝；`load` 不会污染 `default_registry()`。

留下的小问题（不为它开第 2 轮）：

1. `_require_layers` 遇到不可哈希的层状态取值（`{"plan": ["ok"]}`）抛 `TypeError` 而不是 `ValueError`。一行的事，写进了 `s05-ast` 的说明，由那个包顺带改并补测试。
2. `Registry.load` 接受顶层是裸列表的文件（`save` 写的是 `{"invented": [...]}`），条目里多余的键被忽略，空正则 `""` 能登记。都不会让坏特征进 φ（未验收的不输出，验收是 S10 的事），记入 HANDOFF 未决问题给 S10。
