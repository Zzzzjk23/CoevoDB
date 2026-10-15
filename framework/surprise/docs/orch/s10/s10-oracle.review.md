# 审查包 · s10-oracle

- 生成时间：2026-10-15T21:47:33+11:00
- 基线：`session/s10`（e20563e6dc1c）
- 分支：`grok/s10-oracle` @ c63aeb2c1b3b，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 33m15s
- grok：grok 1.0.46 (2765805b9442)；会话 `41ea3709-37ea-4b3a-ae64-c74cf667d899`

## 红旗汇总

- pytest 未通过（退出码 1；failed 1，passed 724，skipped 3）
- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 2 处（确认没有吞掉失败）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-oracle
git diff -M --stat session/s10..grok/s10-oracle
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/oracle_inventor.py`、`framework/tests/test_surprise_s10_oracle_inventor.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/roles/oracle_inventor.py` |  |
| A | `framework/tests/test_surprise_s10_oracle_inventor.py` |  |

提交：

- c63aeb2 Junke: feat(s10-oracle): keep a rewrite template only when engines agree

## 2. diff 统计

```text
 framework/surprise/roles/oracle_inventor.py        | 541 +++++++++++++++++++++
 .../tests/test_surprise_s10_oracle_inventor.py     | 373 ++++++++++++++
 2 files changed, 914 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 1，2m49s；failed 1，passed 724，skipped 3

```text
........................................................................ [ 69%]
........................................................................ [ 79%]
........................................................................ [ 89%]
..........................................F............................. [ 98%]
........                                                                 [100%]
================================== FAILURES ===================================
_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-oracle/.orch/tmp/pytest-of-91484/pytest-4/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000200C63B3E70>

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
1 failed, 724 passed, 3 skipped in 168.53s (0:02:48)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，20m10s

```text

[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (20s)
[FAIL] switches: ValueError: role 'prior' is not available: No module named 'surprise.roles.prior'
[FAIL] prior: ModuleNotFoundError: No module named 'surprise.roles.prior'
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] vocab_inventor: ModuleNotFoundError: No module named 'surprise.roles.vocab_inventor'
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
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

- `framework/surprise/roles/oracle_inventor.py:473` `except Exception:`
- `framework/surprise/roles/oracle_inventor.py:479` `except Exception:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s10-oracle.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s10-prior` e20563e6dc1c → 981f9733cb2c
- 新增 `refs/heads/grok/s10-testfix` @ 5451d7436994
- 移动 `refs/heads/session/s10` e20563e6dc1c → 750b012971c8

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-oracle.jsonl`：4458 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 70，end 1，orch.exit 1，orch.start 1，text 752，thought 2715，tool_call 117，tool_call_update 743，usage 56）；各轮合计 56 个模型回合，grok 上报花费 1.5360 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_call run_terminal_command: {"command": "python .orch\\tmp\\write_report.py ; Remove-Item -LiteralPath \".orch\\tmp\\write_report.py\", \".orch\\tmp\\msg.txt\" -Force ; git status ; git status --short ; Test…
tool_update [in_progress]: 
tool_update [in_progress]: wrote .orch\report.md bytes=15530
tool_update [in_progress]: wrote .orch\report.md bytes=15530 On branch grok/s10-oracle nothing to commit, working tree clean
tool_update [in_progress]: wrote .orch\report.md bytes=15530 On branch grok/s10-oracle nothing to commit, working tree clean True
tool_update [completed]: exit: 0 wrote .orch\report.md bytes=15530 On branch grok/s10-oracle nothing to commit, working tree clean True False False False
tool_call read_file: {"target_file": "D:\\CoevoDB\\.worktrees\\s10-oracle\\.orch\\report.md"}
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "1→# 报告 · s10-oracle\n\n## 改了哪些文件\n\n- `framework/surprise/roles/oracle_inventor.py`：新增。oracle 发明者按实验节奏向网关提议 `query_wrap` / `predic…
thought: 报告看起来完整且准确。 工作包已全部完成。Git 状态干净，提交 c63aeb2。所有 gates 已通过。pytest 中仅有一个旧帧测试存在已知失败。报告已生成，偏差点（call）已在其中说明。
text: 工作包 `s10-oracle` 已提交到 `grok/s10-oracle`，提交 `c63aeb2`。工作区干净。报告在 `.orch/report.md`（未入库）。 oracle 发明者在 `equivalent_query` 打开时，于第 1、101、201 次实验后各向网关提议一次改写模板，最多 3 次。模板只有在 DuckDB、DataFus…
end: stopReason=end_turn turns=56 cost_usd=1.53596496
orch.exit: {"pkg": "s10-oracle", "run": 1, "at": "2026-10-15T21:47:12+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-oracle

## 改了哪些文件

- `framework/surprise/roles/oracle_inventor.py`：新增。oracle 发明者按实验节奏向网关提议 `query_wrap` / `predicate_wrap` 模板，多引擎一致才写入 `rewrites.json`。

- `framework/tests/test_surprise_s10_oracle_inventor.py`：新增。覆盖调用节奏、提示纯度、每种拒收原因、真实引擎验收、`load_library`、`rules()` 与 `certify`。

提交：`c63aeb2`，分支 `grok/s10-oracle`。

## 跑了哪些命令

下面每段是命令、退出码、输出的最后 20 行（不足 20 行则整段）。未跑 `python -m surprise.gates.s10` 的 `isolation` 与 `switches`（要六个角色都在），也未跑 `python -m surprise.gates.all`。说明要求本包不跑这两项。

### 起点全套

```
cd framework
python -m pytest -q testing tests
```

退出码：0

```
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 10%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 20%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 30%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 40%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 50%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 60%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 70%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 80%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 90%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m    [100%][0m
[32m[32m[1m714 passed[0m, [33m3 skipped[0m[32m in 169.13s (0:02:49)[0m[0m
```

### 本包测试

```
cd framework
python -m pytest -q tests/test_surprise_s10_oracle_inventor.py
```

退出码：0

```
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                              [100%][0m
[32m[32m[1m11 passed[0m[32m in 2.80s[0m[0m
```

### S10 门槛（指定的五组）

```
cd framework
python -m surprise.gates.s10 --only constants frozen library frame oracle_inventor
```

退出码：0

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (19s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
S10 GATE [only: constants, frozen, library, frame, oracle_inventor]: PASS (5/5 groups passed)
```

### S09 门槛（指定的三组）

```
cd framework
python -m surprise.gates.s09 --only isolation wiring replay
```

退出码：0

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (53s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (50s)
S09 GATE [only: isolation, wiring, replay]: PASS (3/3 groups passed)
```

### 改完之后的全套

```
cd framework
python -m pytest -q testing tests
```

退出码：1

```
================================== FAILURES ===================================
[31m[1m_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________[0m

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-oracle/.orch/tmp/pytest-of-91484/pytest-3/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000002C44BA0BE70>

    [0m[94mdef[39;49;00m[90m [39;49;00m[92mtest_build_roles_knows_six_names_and_loads_only_the_ones_on[39;49;00m(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> [94mNone[39;49;00m:[90m[39;49;00m
        [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33munknown role[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
            _roles(tmp_path / [33m"[39;49;00m[33mbad[39;49;00m[33m"[39;49;00m, ([33m"[39;49;00m[33mdiagnoser[39;49;00m[33m"[39;49;00m,))[90m[39;49;00m
        [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33mnon-empty[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
            _roles(tmp_path / [33m"[39;49;00m[33mempty[39;49;00m[33m"[39;49;00m, ())[90m[39;49;00m
        [94mfor[39;49;00m name [95min[39;49;00m ([33m"[39;49;00m[33mprior[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33mtranslator[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33mvocab_inventor[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33moracle_inventor[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
>           [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33mnot available[39;49;00m[33m"[39;49;00m) [94mas[39;49;00m caught:[90m[39;49;00m
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^[90m[39;49;00m
[1m[31mE           Failed: DID NOT RAISE ValueError[0m

[1m[31mtests\test_surprise_s10_frame.py[0m:249: Failed
[36m[1m=========================== short test summary info ===========================[0m
[31mFAILED[0m tests/test_surprise_s10_frame.py::[1mtest_build_roles_knows_six_names_and_loads_only_the_ones_on[0m - Failed: DID NOT RAISE ValueError
[31m[31m[1m1 failed[0m, [32m724 passed[0m, [33m3 skipped[0m[31m in 169.74s (0:02:49)[0m[0m
```

## 与说明的偏差

1. `oracle_prompt` 比说明里的签名多一个可选关键字参数 `call: int | None = None`。传入时，提示最后一行是 `This is proposal round {call} of {ORACLE_CALLS_PER_RUN}.`。角色每次调用都传 `call=self._calls + 1`。原因：网关按提示文本缓存回复。第 1 次调用若没有收下规则，第 2 次与第 3 次的库相同，提示文本相同，传输不会再次执行，而门槛要 `len(script.calls) == 3`。这一行是调度轮次，回放时稳定，不是记录号、假设号或运行号。不传 `call` 时，提示正文与说明第 2 节一致。影响：`s10 --only oracle_inventor` 能计满 3 次调用并通过；省略这一行时该组会计成 1 次调用并失败。

2. 第 6 节的可选真实调用没有做。调用次数 0，模型没有提出模板，验收结论无。缓存目录未使用。验收由脚本传输、本包测试和上面的门槛覆盖。

3. 起点那次全套是在 `test_surprise_s10_oracle_inventor.py` 被收集之前跑的，结果 714 passed、3 skipped、退出码 0。`oracle_inventor.py` 在那次运行中途才出现；套件仍以 0 退出，说明 `test_surprise_s10_frame.py` 里那条「角色尚不存在」的断言当时已经跑完。改完后的全套是 724 passed、3 skipped、1 failed。

## 未决问题

`framework/tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on` 对 `prior`、`translator`、`vocab_inventor`、`oracle_inventor` 逐个期望 `ValueError` 且消息匹配 `not available`。本 worktree 里前三个模块文件不存在，第四个 `framework/surprise/roles/oracle_inventor.py` 已存在，所以循环在 `oracle_inventor` 上得到 `Failed: DID NOT RAISE ValueError`（`tests/test_surprise_s10_frame.py:249`）。同函数后面「`surprise.roles.oracle_inventor` 不在 `sys.modules`」的断言没有执行到。这条测试不在允许改动的路径里，本包没有改它，也没有把模块做成不可导入（那样 S10 的 `oracle_inventor` 组过不了）。因此 `python -m pytest -q testing tests` 的退出码是 1。通过数 724，不少于起点 714；skip 仍是 3。本包 11 条测试、S10 指定的 5 组和 S09 指定的 3 组都是退出码 0。另一分支 `grok/s10-testfix` 的 `5451d74` 已把这条断言改成「指向磁盘上不存在的模块再期望 not available」。该提交不是本分支的祖先，本包没有把它合并进来。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。pytest 唯一的失败是 frame 那条测试（已由 s10-testfix 在会话分支上修好），S01 因此失败；S08 只差长跑重钉。两处 `except Exception` 在验收投票里把跑不起来的引擎记为 error / skipped、关 runner 时忽略关闭错误，只影响模板验收，不产生标签。偏差（提示末行带调用轮次，避免三次调用被缓存折成一次）接受；没做真实调用，M3 录制时核对提示。
