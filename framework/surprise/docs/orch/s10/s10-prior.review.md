# 审查包 · s10-prior

- 生成时间：2026-10-15T22:01:05+11:00
- 基线：`session/s10`（e20563e6dc1c）
- 分支：`grok/s10-prior` @ 981f9733cb2c，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 4m43s
- grok：grok 1.0.46 (2765805b9442)；会话 `f56f3b33-436e-4346-9554-8e2937a64e3e`

## 红旗汇总

- pytest 未通过（退出码 1；failed 1，passed 725，skipped 3）
- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-prior
git diff -M --stat session/s10..grok/s10-prior
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/prior.py`、`framework/tests/test_surprise_s10_prior.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/roles/prior.py` |  |
| A | `framework/tests/test_surprise_s10_prior.py` |  |

提交：

- b20092c Junke: s10-prior: exploration prior with Brier-calibrated unit prices
- 981f973 Junke: s10-prior: skip non-string unit fields in a prior reply

## 2. diff 统计

```text
 framework/surprise/roles/prior.py          | 374 +++++++++++++++++++
 framework/tests/test_surprise_s10_prior.py | 561 +++++++++++++++++++++++++++++
 2 files changed, 935 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 1，3m55s；failed 1，passed 725，skipped 3

```text
........................................................................ [ 69%]
........................................................................ [ 79%]
........................................................................ [ 88%]
..........................................F............................. [ 98%]
.........                                                                [100%]
================================== FAILURES ===================================
_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-prior/.orch/tmp/pytest-of-91484/pytest-8/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000014857D429E0>

    def test_build_roles_knows_six_names_and_loads_only_the_ones_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValueError, match="unknown role"):
            _roles(tmp_path / "bad", ("diagnoser",))
        with pytest.raises(ValueError, match="non-empty"):
            _roles(tmp_path / "empty", ())
        for name in ("prior", "translator", "vocab_inventor", "oracle_inventor"):
>           with pytest.raises(ValueError, match="not available") as caught:
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           Failed: DID NOT RAISE ValueError

tests\test_surprise_s10_frame.py:249: Failed
=========================== short test summary info ===========================
FAILED tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on
1 failed, 725 passed, 3 skipped in 234.00s (0:03:54)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，17m46s

```text

[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (18s)
[FAIL] switches: ValueError: role 'translator' is not available: No module named 'surprise.roles.translator'
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] vocab_inventor: ModuleNotFoundError: No module named 'surprise.roles.vocab_inventor'
[FAIL] oracle_inventor: ModuleNotFoundError: No module named 'surprise.roles.oracle_inventor'
[FAIL] translator_real: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] m3: gates/s10_llm/m3 is missing: the orchestrator records it with real calls after the merge
S10 GATE: FAIL (5/12 groups passed)
=== summary ===
s01: FAIL (exit 1)
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: FAIL (exit 1)
GATES: FAIL (7/10 passed)
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
- 日志 `.orch/logs/s10-prior.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s10-oracle` @ c63aeb2c1b3b
- 新增 `refs/heads/grok/s10-testfix` @ 5451d7436994
- 移动 `refs/heads/session/s10` e20563e6dc1c → ba423d1abac3

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-prior.jsonl`：2668 条事件（available_commands 59，end 2，orch.exit 2，orch.start 2，plan 8，text 710，thought 976，tool_call 113，tool_call_update 744，usage 52）；各轮合计 52 个模型回合，grok 上报花费 1.4135 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call search_replace: {"file_path": "D:\\CoevoDB\\.worktrees\\s10-prior\\.orch\\report.md", "old_string": "## 未决问题\n`test_build_roles_knows_six_names_and_loads_only_the_ones_on` 需要编排者在合并第一个新角色模块后，改成只对尚…
tool_call run_terminal_command: {"command": "Remove-Item -Force .orch\\tmp\\msg.txt; git status", "description": "Remove scratch message; confirm clean tree"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "## 未决问题\n`test_build_roles_knows_six_names_and_loads_only_the_ones_on` 需要编排者在合并第一个新角色模块后，改成只对尚未落地的插件断言 `not available`。`s…
tool_update [in_progress]: On branch grok/s10-prior nothing to commit, working tree clean
tool_update [completed]: exit: 0 On branch grok/s10-prior nothing to commit, working tree clean
tool_call todo_write: {"todos": [{"id": "r3", "status": "completed"}], "merge": true}
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] r1: Skip non-str unit in _ingest\n- [completed] r2: Add test for unhashable/non-str units\n- [completed] r3:…
plan: {"entries": [{"content": "Skip non-str unit in _ingest", "priority": "medium", "status": "completed"}, {"content": "Add test for unhashable/non-str units", "priority": "medium", "…
text: 第 1 轮返工已提交 `981f973`。 `_ingest` 现在在把 `unit` 放进集合之前先确认它是字符串；列表、字典、数字这类项会跳过，不定价，也不再抛 `TypeError`。新增 `test_non_string_unit_in_reply_is_skipped`：合法项定上价，其余问过的单元记 `unpriced`。已有测试未改。 **验…
end: stopReason=end_turn turns=12 cost_usd=0.42867404
orch.exit: {"pkg": "s10-prior", "run": 2, "at": "2026-10-15T22:00:55+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-prior

提交 `b20092c`，分支 `grok/s10-prior`。跟踪文件工作树干净。未打 tag，未合并，未 push。

## 改了哪些文件
- `framework/surprise/roles/prior.py`：新增。`build(ctx)`、`ExplorationPrior`（`prepare` / `pseudo` / `weight` / `brier` / `priced` / `observe` / `step` / `report` / `manifest`）、纯函数 `prior_evidence` 与 `prior_prompt`。证据只来自 `ctx.readers` 的 DataFusion changelog 与 DuckDB issue tests。
- `framework/tests/test_surprise_s10_prior.py`：新增。脚本传输覆盖分批、每选择一次、问过不再问、坏回复、Brier 校准、结算条件、证据与提示、`build_roles` + Hunter 的 U。

## 跑了哪些命令

按说明未跑 `python -m surprise.gates.s10 --only switches`（六个角色都在才能过），也未跑 `python -m surprise.gates.all`。

### `cd framework; python -m pytest -q tests/test_surprise_s10_prior.py`

退出码 0。最后 20 行：

```
...........                                                              [100%]
11 passed in 0.40s
```

### `cd framework; python -m pytest -q testing tests`

退出码 1。最后 20 行：

```
================================== FAILURES ===================================
_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-prior/.orch/tmp/pytest-of-91484/pytest-3/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000027CA4B3EAC0>

    def test_build_roles_knows_six_names_and_loads_only_the_ones_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValueError, match="unknown role"):
            _roles(tmp_path / "bad", ("diagnoser",))
        with pytest.raises(ValueError, match="non-empty"):
            _roles(tmp_path / "empty", ())
        for name in ("prior", "translator", "vocab_inventor", "oracle_inventor"):
>           with pytest.raises(ValueError, match="not available") as caught:
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           Failed: DID NOT RAISE ValueError

tests\test_surprise_s10_frame.py:249: Failed
=========================== short test summary info ===========================
FAILED tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on - Failed: DID NOT RAISE ValueError
1 failed, 724 passed, 3 skipped in 169.34s (0:02:49)
```

未在改动前单独记起点。s10-frame 报告当时是 705 passed / 3 skipped。当前 724 passed / 3 skipped / 1 failed。本包新增 11 条测试；那 1 条失败是 s10-frame 假定四个新角色模块都不存在。skip 仍是 3。通过数 724 高于 705。

### `cd framework; python -m surprise.gates.s10 --only isolation`

退出码 1（说明预期：只因为别的角色模块还不存在而失败）。最后 20 行：

```
[FAIL] isolation: probe failed: Traceback (most recent call last):
  File "<string>", line 4, in <module>
    import surprise.roles.translator
ModuleNotFoundError: No module named 'surprise.roles.translator'

S10 GATE [only: isolation]: FAIL (0/1 groups passed)
```

### `cd framework; python -m surprise.gates.s10 --only constants frozen library frame prior`

退出码 0。最后 20 行：

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (18s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
S10 GATE [only: constants, frozen, library, frame, prior]: PASS (5/5 groups passed)
```

### `cd framework; python -m surprise.gates.s09 --only isolation wiring replay`

退出码 0。最后 20 行：

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (52s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (51s)
S09 GATE [only: isolation, wiring, replay]: PASS (3/3 groups passed)
```

### 真实调用（可选）

1 次 `deepseek-flash` 网络调用（`PRIOR_TIER=fast`，未用 strong）。给 `PRIOR_UNITS[:4]` 定价，缓存目录 `.orch/tmp/prior_live/`（不入库）。网关 `status=ok`，4/4 单元定上价，`p_fail` 在 0.05–0.08。结论：当前提示在 fast 档能拿到合法 JSON。

## 与说明的偏差
pytest 整包退出码 1：`tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on` 对 `("prior", "translator", "vocab_inventor", "oracle_inventor")` 逐个断言 `build_roles` 抛 `ValueError: not available`。`prior.py` 落地后 `"prior"` 不再抛。说明禁止改旧测试，本包未改该文件。门槛 `prior` 组 5/5 通过。

## 未决问题
`test_build_roles_knows_six_names_and_loads_only_the_ones_on` 在本 worktree 里仍失败（假定四个角色模块都不存在）。审查确认这是预期的，编排者另派包修它。本包未改该文件。

## 第 1 轮返工

提交 `981f973`。只改审查指出的一处。

### 改了什么
- `framework/surprise/roles/prior.py`：`_ingest` 在把 `unit` 放进集合之前先要求它是 `str`；列表、字典、数字等项跳过，与没问过的单元一样不定价。
- `framework/tests/test_surprise_s10_prior.py`：新增 `test_non_string_unit_in_reply_is_skipped`。已有测试未改。

### `cd framework; python -m pytest -q tests/test_surprise_s10_prior.py`

退出码 0。最后 20 行：

```
............                                                             [100%]
12 passed in 0.87s
```

### `cd framework; python -m pytest -q testing tests`

退出码 1。最后 20 行：

```
================================== FAILURES ===================================
_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-prior/.orch/tmp/pytest-of-91484/pytest-7/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000002055C51EF20>

    def test_build_roles_knows_six_names_and_loads_only_the_ones_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValueError, match="unknown role"):
            _roles(tmp_path / "bad", ("diagnoser",))
        with pytest.raises(ValueError, match="non-empty"):
            _roles(tmp_path / "empty", ())
        for name in ("prior", "translator", "vocab_inventor", "oracle_inventor"):
>           with pytest.raises(ValueError, match="not available") as caught:
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E           Failed: DID NOT RAISE ValueError

tests\test_surprise_s10_frame.py:249: Failed
=========================== short test summary info ===========================
FAILED tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on - Failed: DID NOT RAISE ValueError
1 failed, 725 passed, 3 skipped in 173.75s (0:02:53)
```

只这一条 frame 测试失败（审查预期）。skip 仍是 3。通过数 725（上一轮 724，本轮新增 1 条测试）。

### `cd framework; python -m surprise.gates.s10 --only constants frozen library frame prior`

退出码 0。最后 20 行：

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (21s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
S10 GATE [only: constants, frozen, library, frame, prior]: PASS (5/5 groups passed)
```
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并，返工 1 轮（回复里非字符串的 `unit` 会让 `_ingest` 抛 TypeError、整次运行出错；已改为跳过并加测试）。pytest 唯一的失败是 frame 那条测试（已由 s10-testfix 修好），S01 因此失败；S08 只差长跑重钉。执行者做了 1 次真实调用（fast 档），4 个单元都定上价。
