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
