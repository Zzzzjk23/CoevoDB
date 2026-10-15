# 审查包 · s10-frame

- 生成时间：2026-10-15T20:54:23+11:00
- 基线：`session/s10`（71a59c7f4247）
- 分支：`grok/s10-frame` @ f12b92a56b26，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 32m46s
- grok：grok 1.0.46 (2765805b9442)；会话 `a7fc28ba-77e2-4fdc-8c8a-4d766117f737`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 4 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-frame
git diff -M --stat session/s10..grok/s10-frame
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/base.py`、`framework/surprise/roles/runtime.py`、`framework/surprise/roles/constants.py`、`framework/surprise/roles/__init__.py`、`framework/surprise/hunter/hunter.py`、`framework/surprise/hunter/scoring.py`、`framework/surprise/hunter/operators.py`、`framework/surprise/hunter/extractor.py`、`framework/surprise/hunter/phi_worker.py`、`framework/surprise/experiments/loop.py`、`framework/tests/test_surprise_s10_frame.py`、`framework/tests/test_surprise_roles_runtime.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/experiments/loop.py` |  |
| M | `framework/surprise/hunter/extractor.py` |  |
| M | `framework/surprise/hunter/hunter.py` |  |
| M | `framework/surprise/hunter/operators.py` |  |
| M | `framework/surprise/hunter/phi_worker.py` |  |
| M | `framework/surprise/hunter/scoring.py` |  |
| A | `framework/surprise/roles/base.py` |  |
| M | `framework/surprise/roles/constants.py` |  |
| M | `framework/surprise/roles/runtime.py` |  |
| A | `framework/tests/test_surprise_s10_frame.py` |  |

提交：

- f12b92a Junke: s10-frame: shared plugin frame, Hunter hooks, and run vocabulary

## 2. diff 统计

```text
 framework/surprise/experiments/loop.py     | 201 +++++++--
 framework/surprise/hunter/extractor.py     |   4 +-
 framework/surprise/hunter/hunter.py        |  41 +-
 framework/surprise/hunter/operators.py     |  17 +-
 framework/surprise/hunter/phi_worker.py    |  10 +-
 framework/surprise/hunter/scoring.py       |  43 +-
 framework/surprise/roles/base.py           |  89 ++++
 framework/surprise/roles/constants.py      | 105 +++++
 framework/surprise/roles/runtime.py        | 140 +++++-
 framework/tests/test_surprise_s10_frame.py | 659 +++++++++++++++++++++++++++++
 10 files changed, 1246 insertions(+), 63 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，2m30s；passed 705，skipped 3

```text
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 50%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 91%]
............................................................             [100%]
705 passed, 3 skipped in 149.15s (0:02:29)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，16m35s

```text

[FAIL] constants: harness rewrites.LIBRARY_ENV must be 'SURPRISE_REWRITE_LIBRARY', got None
[PASS] frozen: harness changes since s09-done-r2: []; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[FAIL] library: AttributeError: module 'surprise.harness.oracles.rewrites' has no attribute 'template_problem'
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (17s)
[FAIL] switches: ValueError: role 'prior' is not available: No module named 'surprise.roles.prior'
[FAIL] prior: ModuleNotFoundError: No module named 'surprise.roles.prior'
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] vocab_inventor: ModuleNotFoundError: No module named 'surprise.roles.vocab_inventor'
[FAIL] oracle_inventor: ModuleNotFoundError: No module named 'surprise.roles.oracle_inventor'
[FAIL] translator_real: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] m3: gates/s10_llm/m3 is missing: the orchestrator records it with real calls after the merge
S10 GATE: FAIL (2/12 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: FAIL (exit 1)
GATES: FAIL (8/10 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/roles/runtime.py:328` `except Exception as exc:`
- `framework/surprise/roles/runtime.py:333` `except Exception as exc:`
- `framework/surprise/roles/runtime.py:475` `except Exception:`
- `framework/surprise/roles/runtime.py:479` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s10-frame.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s10-harness` @ dcf68f2628cd
- 移动 `refs/heads/session/s10` 71a59c7f4247 → 477d6eb88c3d

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-frame.jsonl`：4664 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 95，end 1，orch.exit 1，orch.start 1，plan 3，text 603，thought 2988，tool_call 206，tool_call_update 683，usage 81）；各轮合计 81 个模型回合，grok 上报花费 2.0083 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call run_terminal_command: {"command": "Remove-Item .orch\\tmp\\s10-frame-msg.txt; git status --short; git check-ignore -v .orch/report.md; git log -1 --format=\"%h %s\"", "description": "Remove scratch mes…
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s10-frame\n\n提交 `f12b92a`，分支 `grok/s10-frame`。跟踪文件工作树干净。未打 tag，未合并。\n\n## 改了哪些文件\n- `framework/s…
tool_update [in_progress]: .gitignore:16:.orch/.orch/report.md
tool_update [completed]: exit: 0 .gitignore:16:.orch/.orch/report.md f12b92a s10-frame: shared plugin frame, Hunter hooks, and run vocabulary
thought: Git 工作区干净，没有未提交的更改。
tool_call todo_write: {"todos": [{"id": "tests", "content": "tests: Fix frame-test defects and run acceptance", "status": "completed"}, {"id": "report", "content": "report: Commit and write .orch/repor…
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] base: base: Add roles/base.py and S10 constants\n- [completed] runtime: runtime: Extend RoleSet / build_role…
plan: {"entries": [{"content": "base: Add roles/base.py and S10 constants", "priority": "medium", "status": "completed"}, {"content": "runtime: Extend RoleSet / build_roles for six role…
text: 工作包 `s10-frame` 已完成，提交在 `grok/s10-frame` 的 `f12b92a`。报告在 `.orch/report.md`。 四个新角色只有插件协议和挂钩，没有实现。`RoleSet` 能加载打开的角色；Hunter 接受 prior、额外重写规则和词表；循环接受 `--vocabulary`，并只在 oracle invento…
end: stopReason=end_turn turns=81 cost_usd=2.00827868
orch.exit: {"pkg": "s10-frame", "run": 1, "at": "2026-10-15T20:54:12+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-frame

提交 `f12b92a`，分支 `grok/s10-frame`。跟踪文件工作树干净。未打 tag，未合并。

## 改了哪些文件
- `framework/surprise/roles/base.py`：新增。`PLUGINS`、冻结的 `RoleContext` / `Observed`，以及带空默认实现的 `Role`。不导入任何角色模块或模型客户端。
- `framework/surprise/roles/constants.py`：修改。在 S9 常数之后追加 S10 的全部常数，各带一行英文注释。`as_dict()` 未改。
- `framework/surprise/roles/runtime.py`：修改。公开 `ROLES`（六个名字）。`build_roles(..., oracles=())` 只导入打开的新角色；缺模块则 `ValueError: role {name!r} is not available: ...`。`RoleSet` 增加 `plugins`、`prior`、`rewrite_rules()`、`rewrite_library`，以及 `observe(event=)`、`after`、`step`、`report`、`manifest`、`close` 的插件挂钩。S9 两个角色的 `step` / `report` / `manifest["roles"]` 形状不变。
- `framework/surprise/hunter/scoring.py`：修改。`optimistic_rate` / `uncertainty` 接受 `prior_fails` / `prior_tests`，默认仍是残差先验。`score(..., prior=None)` 只在未探索区、且 `pseudo` 非空时改用这份计数。
- `framework/surprise/hunter/operators.py`：修改。`oracle_options(..., extra_rules=())` 在 `equivalent_query` 上先给冻结 `RULES`，再按给定顺序追加；与 `RULES` 相撞的 id 丢掉。`RULES` 本身未改。
- `framework/surprise/hunter/extractor.py`：修改。`PhiExtractor(..., registry_path=None)`。未给路径时命令行仍是 `[sys.executable, "-m", "surprise.hunter.phi_worker"]`。
- `framework/surprise/hunter/phi_worker.py`：修改。`--registry PATH` 时 `extract(case, registry=Registry.load(path))`。不读 stdin 做参数。
- `framework/surprise/hunter/hunter.py`：修改。`prior`、`extra_rules`、`registry`。`registry is None` 时用 `default_registry()`。`choose` 先按原顺序过滤并消耗 RNG，再在有幸存者时对 prior `prepare` 一次并打分。不导入 `surprise.roles`。
- `framework/surprise/experiments/loop.py`：修改。`run(..., vocabulary=None)`、CLI `--vocabulary`、六个 `--llm` 名字。有词汇表时同一份 `Registry.load` 给抽取器、Hunter、Diagnoser、Workbench 和角色；manifest 增加 `vocabulary`。`SURPRISE_REWRITE_LIBRARY` 仅在 `rewrite_library` 非空时设置，并在 `finally` 里恢复（含出错）。未给词汇表、未开角色时不导入 `surprise.roles`。
- `framework/tests/test_surprise_s10_frame.py`：新增。假插件与本地引擎，无网络、无密钥。
- `framework/tests/test_surprise_roles_runtime.py`：未改。

未建 `prior.py` / `translator.py` / `vocab_inventor.py` / `oracle_inventor.py`。未改 `roles/__init__.py`。

## 跑了哪些命令

按说明未跑 `python -m surprise.gates.s08 --only longrun`（代码摘要已变，预期失败），也未跑 `python -m surprise.gates.all`。

### `Set-Location framework; python -m pytest -q tests/test_surprise_s10_frame.py -k vocabulary_run --tb=short`

退出码 1。这是修复前的一次。最后 20 行：

```
surprise\experiments\loop.py:199: in run
    state.report = _write_report(state)
                   ^^^^^^^^^^^^^^^^^^^^
surprise\experiments\loop.py:673: in _write_report
    "new_families": _new_family_count(state.directory / "theory"),
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
surprise\experiments\loop.py:717: in _new_family_count
    return len(new_families(theory))
               ^^^^^^^^^^^^^^^^^^^^
surprise\metrics\dups.py:46: in new_families
    bench = Workbench.open(store_dir)
            ^^^^^^^^^^^^^^^^^^^^^^^^^
surprise\theory\workbench.py:137: in open
    store = TheoryStore.open(root, active)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
surprise\theory\store.py:187: in open
    store.head()
surprise\theory\store.py:200: in head
    raise StoreError("head.json: vocabulary does not match the registry")
E   surprise.theory.store.StoreError: head.json: vocabulary does not match the registry
=========================== short test summary info ===========================
FAILED tests/test_surprise_s10_frame.py::test_vocabulary_run_records_the_invented_feature_and_a_plain_run_does_not - surprise.theory.store.StoreError: head.json: vocabulary does not match the registry
1 failed, 12 deselected in 8.75s
```

### `Set-Location framework; python -m pytest -q tests/test_surprise_s10_frame.py --tb=short`

退出码 0。最后 20 行：

```
.............                                                            [100%]
13 passed in 13.15s
```

### `Set-Location framework; python -m pytest -q testing tests`

退出码 0。最后 20 行：

```
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 50%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 91%]
............................................................             [100%]
705 passed, 3 skipped in 153.36s (0:02:33)
```

### `Set-Location framework; python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism`

退出码 0。最后 20 行：

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (15s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (64s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (35s)
S08 GATE [only: no_llm, scoring, operators, candidates, lanes, determinism]: PASS (6/6 groups passed)
```

### `Set-Location framework; python -m surprise.gates.s09 --only isolation constants cache reject cap wiring replay`

退出码 0。最后 20 行：

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (51s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (50s)
S09 GATE [only: isolation, constants, cache, reject, cap, wiring, replay]: PASS (7/7 groups passed)
```

### `Set-Location framework; python -m surprise.gates.s10 --only frame`

退出码 0。最后 20 行：

```
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (20s)
S10 GATE [only: frame]: PASS (1/1 groups passed)
```

### `Set-Location framework; python -m surprise.gates.s10 --only constants`

退出码 1（说明里的预期失败）。最后 20 行：

```
[FAIL] constants: harness rewrites.LIBRARY_ENV must be 'SURPRISE_REWRITE_LIBRARY', got None
S10 GATE [only: constants]: FAIL (0/1 groups passed)
```

失败点是 harness 的 `rewrites.LIBRARY_ENV`。角色常数与 S9 常数的检查在这之前，该组没有更早的失败信息。`ROLES` 与 `PLUGINS` 的检查写在 harness 循环之后，这一组因此没有跑到它们。

## 与说明的偏差
1. `oracles` 放进传给 `_build_roles` 的 config 字典，没有给这个函数加新关键字。S9 wiring 测试的替身签名固定为 `(config, *, run_dir, extract, registry, engines, seed)`，新增 `oracles=` 会 TypeError。`_build_roles` 取出 `oracles` 再传给 `build_roles`。`config.json` 仍由 `_llm_public` 写出，不含 `oracles`。影响：只有循环内部的角色构建。
2. 循环只在 `observe` 的签名接受 `event`（或有 `**kwargs`）时才传入 `Observed`。S9 替身是 `observe(self, phi, label, record_id)`。真正的 `RoleSet.observe` 始终接受 `event`。影响：替身路径不导入 `surprise.roles.base`。
3. `prior`、`rewrite_rules`、`rewrite_library` 用 `hasattr` / `getattr(..., None)` 读取。S9 替身没有这些属性，因此不会把 prior 或 extra rules 交给 Hunter，也不会设置 `SURPRISE_REWRITE_LIBRARY`。影响：全关角色与只开 S9 两个角色的运行。
4. 额外规则只在与冻结 `RULES` 相撞时丢掉，彼此之间不去重。按说明字面实现。影响：`oracle_options` 的 `equivalent_query` 列表。
5. `extra_rules()` 在每次 `_explore` 开头调用一次。`_migrate` 在引擎少于两个时直接返回，否则也只在开头调用一次。不是每个 case 一次。影响：钩子若有副作用，次数按轮次而不是按候选。
6. `PhiExtractor._degrade` 未改。超时或 worker 错误仍走原来的降级 phi。词汇表只在 worker 成功路径上使用。影响：抽取失败时的 phi 与 S8 相同。
7. 带词汇表的运行在写报告的 `new_families` 时会失败：`metrics.dups.new_families` 用默认词表打开 theory，`head.json` 的摘要对不上。该文件不在允许改动的路径里。`loop._new_family_count` 在这次运行加载了词表时，用同一个 `Registry` 打开 theory 再数 family 数（与 `len(new_families(...))` 相同，都是 `len(families())`）。未给词汇表时仍调用 `new_families`。影响：`loop.run(..., vocabulary=...)` 能写完报告；全关词汇表的报告路径不变。上面退出码 1 的那次测试就是这个错误，修复后已通过。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。两处红旗都是预期的：S08 只有 `longrun` 因代码摘要变了而失败（编排者之后重跑长跑重钉），S10 其余组要等角色包与录制；四处 `except Exception` 都在关闭资源时收集第一个异常再抛出，没有吞掉失败。七处偏差都接受（S9 的替身签名、`new_families` 不认扩展词表时改用同一个 Registry 计数）。
