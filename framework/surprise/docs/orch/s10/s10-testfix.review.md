# 审查包 · s10-testfix

- 生成时间：2026-10-15T21:42:12+11:00
- 基线：`session/s10`（b724b160bf81）
- 分支：`grok/s10-testfix` @ 5451d7436994，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 7m21s
- grok：grok 1.0.46 (2765805b9442)；会话 `78414ba6-0d6d-498b-8d8c-09c10cdbf2a6`

## 红旗汇总

- 门槛未通过（退出码 1）
- 测试里被改写的断言 3 处（逐条确认没有放宽）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-testfix
git diff -M --stat session/s10..grok/s10-testfix
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/tests/test_surprise_s10_frame.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/tests/test_surprise_s10_frame.py` |  |

提交：

- 5451d74 Junke: test(s10-testfix): assert missing roles via absent modules

## 2. diff 统计

```text
 framework/tests/test_surprise_s10_frame.py | 25 +++++++++++++++++++++----
 1 file changed, 21 insertions(+), 4 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，2m42s；passed 714，skipped 3

```text
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 50%]
........................................................................ [ 60%]
........................................................................ [ 70%]
........................................................................ [ 80%]
........................................................................ [ 90%]
.....................................................................    [100%]
714 passed, 3 skipped in 161.99s (0:02:41)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，19m23s

```text

[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (53s)
[FAIL] switches: ValueError: role 'prior' is not available: No module named 'surprise.roles.prior'
[FAIL] prior: ModuleNotFoundError: No module named 'surprise.roles.prior'
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] vocab_inventor: ModuleNotFoundError: No module named 'surprise.roles.vocab_inventor'
[FAIL] oracle_inventor: ModuleNotFoundError: No module named 'surprise.roles.oracle_inventor'
[FAIL] translator_real: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] m3: gates/s10_llm/m3 is missing: the orchestrator records it with real calls after the merge
S10 GATE: FAIL (4/12 groups passed)
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

- `framework/tests/test_surprise_s10_frame.py:249` 原：`with pytest.raises(ValueError, match="not available") as caught:` → 同一处新增：`assert missing not in sys.modules`；`assert importlib.util.find_spec(missing) is None`；`with pytest.raises(ValueError, match="not available") as caught:`
- `framework/tests/test_surprise_s10_frame.py:251` 原：`assert "unknown role" not in str(caught.value)` → 同一处新增：`assert missing not in sys.modules`；`assert importlib.util.find_spec(missing) is None`；`with pytest.raises(ValueError, match="not available") as caught:`
- `framework/tests/test_surprise_s10_frame.py:252` 原：`assert PLUGINS[name] not in sys.modules` → 同一处新增：`assert missing not in sys.modules`；`assert importlib.util.find_spec(missing) is None`；`with pytest.raises(ValueError, match="not available") as caught:`

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s10-testfix.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s10-oracle` e20563e6dc1c → c63aeb2c1b3b
- 移动 `refs/heads/grok/s10-prior` b20092c12fca → 981f9733cb2c

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-testfix.jsonl`：1100 条事件（available_commands 22，end 1，orch.exit 1，orch.start 1，text 414，thought 327，tool_call 23，tool_call_update 295，usage 16）；各轮合计 16 个模型回合，grok 上报花费 0.1757 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: exit: 0 [grok/s10-testfix 5451d74] test(s10-testfix): assert missing roles via absent modules 1 file changed, 21 insertions(+), 4 deletions(-) 5451d7436994595ebca19bd047bb0cc8df8b…
thought: 提交已成功。工作树干净，尚未生成报告。 正在撰写工作包报告。将记录三个验收命令及其输出，跳过此前因目录错误而失败的尝试。 测试运行中，进度已过 70%。 完整测试已跑完，714 个用例全部通过，3 个跳过，耗时约 2 分 51 秒。Frame 测试与 Preimport 测试也各通过 13 个，耗时约 14 秒。未发现显著偏差。 delitem 列表额外覆…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s10-testfix\\.orch\\report.md", "content": "# 报告 · s10-testfix\n\n## 改了哪些文件\n\n- `framework/tests/test_surprise_s10_frame.py`：只改 `test_buil…
tool_call run_terminal_command: {"command": "Remove-Item -LiteralPath .orch\\tmp\\s10-testfix-msg.txt; git status --short; git log -1 --oneline", "description": "Remove commit-message scratch and confirm clean t…
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s10-testfix\n\n## 改了哪些文件\n\n- `framework/tests/test_surprise_s10_frame.py`：只改 `test_build_roles_…
tool_update [in_progress]: 5451d74 test(s10-testfix): assert missing roles via absent modules
tool_update [completed]: exit: 0 5451d74 test(s10-testfix): assert missing roles via absent modules
thought: 工作区干净，没有未提交的更改。
text: `test_build_roles_knows_six_names_and_loads_only_the_ones_on` 已改完并提交到 `grok/s10-testfix`（`5451d74`）。工作区干净，报告在 `.orch/report.md`。 这个测试不再假定四个角色模块不存在，也不再受同进程里谁先导入它们的影响： - 四个名字各自被指到 `…
end: stopReason=end_turn turns=16 cost_usd=0.1757018
orch.exit: {"pkg": "s10-testfix", "run": 1, "at": "2026-10-15T21:42:00+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-testfix

## 改了哪些文件

- `framework/tests/test_surprise_s10_frame.py`：只改 `test_build_roles_knows_six_names_and_loads_only_the_ones_on`。对 `prior`、`translator`、`vocab_inventor`、`oracle_inventor` 各用 `monkeypatch.context()` 把 `base.PLUGINS[name]` 指到 `surprise.roles._s10_missing_{name}`，先断言该路径不在 `sys.modules` 且 `importlib.util.find_spec` 为 `None`，再断言 `build_roles` 抛 `ValueError`（信息含 `not available`、不含 `unknown role`），并且该路径仍不在 `sys.modules`。上下文退出后 `PLUGINS` 恢复。调用 `_roles(..., ("translator", "prior", "prior"), ...)` 之前，用 `monkeypatch.delitem(sys.modules, ..., raising=False)` 卸掉 `surprise.roles.vocab_inventor`、`surprise.roles.oracle_inventor`、`surprise.roles._s10_fake_vocab_inventor` 以及四个 `_s10_missing_*` 假模块名。函数后半段的断言未改。
- 提交：`5451d74` `test(s10-testfix): assert missing roles via absent modules`（分支 `grok/s10-testfix`）。`git status` 干净。

## 跑了哪些命令

命令：`cd framework; python -m pytest -q tests/test_surprise_s10_frame.py`

退出码：0

输出末 20 行：

```
.............                                                            [100%]
13 passed in 13.98s
```

命令：`cd framework; python -m pytest -q testing tests`

退出码：0

输出末 20 行：

```
........................ss..................................s........... [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 50%]
........................................................................ [ 60%]
........................................................................ [ 70%]
........................................................................ [ 80%]
........................................................................ [ 90%]
.....................................................................    [100%]
714 passed, 3 skipped in 171.24s (0:02:51)
```

命令：`cd framework; python -c "import sys, types, pytest; sys.modules['surprise.roles.vocab_inventor'] = types.ModuleType('surprise.roles.vocab_inventor'); sys.exit(pytest.main(['-q', 'tests/test_surprise_s10_frame.py']))"`

退出码：0

输出末 20 行：

```
.............                                                            [100%]
13 passed in 14.30s
```

## 与说明的偏差

无。`import importlib.util` 写在该测试函数内部，没有改文件顶部的导入，也没有改其他函数。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。改写的三条断言就是说明规定的替换（指向确实不存在的模块后仍断言 not available、不是 unknown role、不进 sys.modules），没有放宽；导入检查之前先从 sys.modules 拿掉真模块。门槛失败来自其余包未合并与 S08 长跑待重钉。
