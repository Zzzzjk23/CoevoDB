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

