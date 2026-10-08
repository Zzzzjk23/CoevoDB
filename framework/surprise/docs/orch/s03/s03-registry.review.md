# 审查包 · s03-registry

- 生成时间：2026-10-09T01:47:16+11:00
- 基线：`session/s03`（d337846ac53d）
- 分支：`grok/s03-registry` @ a7cce8be92c1，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 7m51s
- grok：grok 1.0.46 (2765805b9442)；会话 `8aec0aa4-ef39-41a5-b5a6-34107a876c89`

## 红旗汇总

- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s03..grok/s03-registry
git diff -M --stat session/s03..grok/s03-registry
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/__init__.py`、`framework/surprise/harness/oracles/registry.py`、`framework/surprise/harness/oracles/sound.py`、`framework/surprise/harness/evaluate.py`、`framework/surprise/harness/contracts.py`、`framework/surprise/harness/manifest.py`、`framework/tests/test_surprise_oracles.py`、`framework/tests/test_surprise_evaluate.py`、`framework/tests/test_surprise_contracts.py`、`framework/tests/test_surprise_s03_registry.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/harness/contracts.py` |  |
| M | `framework/surprise/harness/evaluate.py` |  |
| M | `framework/surprise/harness/manifest.py` |  |
| M | `framework/surprise/harness/oracles/__init__.py` |  |
| A | `framework/surprise/harness/oracles/registry.py` |  |
| A | `framework/surprise/harness/oracles/sound.py` |  |
| M | `framework/tests/test_surprise_contracts.py` |  |
| M | `framework/tests/test_surprise_evaluate.py` |  |
| M | `framework/tests/test_surprise_oracles.py` |  |
| A | `framework/tests/test_surprise_s03_registry.py` |  |

提交：

- c9c4da5 Junke: s03-registry: shared oracle registry and DataFusion sound adapters
- a7cce8b Junke: s03-registry: isolate missing-module tests with monkeypatch

## 2. diff 统计

```text
 framework/surprise/harness/contracts.py        |   6 +-
 framework/surprise/harness/evaluate.py         |  32 +++-
 framework/surprise/harness/manifest.py         |   3 +
 framework/surprise/harness/oracles/__init__.py | 134 +++++++-------
 framework/surprise/harness/oracles/registry.py | 154 +++++++++++++++
 framework/surprise/harness/oracles/sound.py    | 106 +++++++++++
 framework/tests/test_surprise_contracts.py     |   4 +
 framework/tests/test_surprise_evaluate.py      |  58 ++++++
 framework/tests/test_surprise_oracles.py       |  28 ++-
 framework/tests/test_surprise_s03_registry.py  | 247 +++++++++++++++++++++++++
 10 files changed, 687 insertions(+), 85 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m07s；passed 165，skipped 3

```text
........................ss..................................s........... [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
165 passed, 3 skipped in 6.66s
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，0m24s

```text
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 165 passed (baseline 64): 165 passed, 3 skipped in 6.68s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 32 files hashed (567be298985e); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
=== gate s03 ===
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
[FAIL] local: ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'
[FAIL] cross: ModuleNotFoundError: No module named 'surprise.harness.oracles.pg_reference'
[FAIL] version: ModuleNotFoundError: No module named 'surprise.harness.oracles.version_differential'
[FAIL] matrix: AssertionError: duckdb/index_presence hidden execution failure: {'y': 'invalid', 'oracle': 'index_presence', 'fail_kind': None, 'invalid_reason': 'harness_error', 'identity': {'switches': [], 'error_class': None, 'behavior': {}}, 'cve': {}, 'detail': {'exception': "ModuleNotFoundError: No module named 'surprise.harness.oracles.index_presence'"}}
S03 GATE: FAIL (1/5 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: FAIL (exit 1)
GATES: FAIL (2/3 passed)
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
- 日志 `.orch/logs/s03-registry.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/session/s03` d337846ac53d → e06357adbc75

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s03-registry.jsonl`：2841 条事件（available_commands 44，end 2，orch.exit 2，orch.start 2，plan 4，text 778，thought 1538，tool_call 102，tool_call_update 329，usage 40）；各轮合计 40 个模型回合，grok 上报花费 0.9707 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: warning: in the working copy of 'framework/tests/test_surprise_s03_registry.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-registry a7cce8b] s03-registry:…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/tests/test_surprise_s03_registry.py', LF will be replaced by CRLF the next time Git touches it [grok/s03-registry a7cce8b] s03-r…
thought: 正在更新 .orch/report.md，并删除临时的提交信息草稿。 正在重写 .orch/report.md，将本次返工纳入报告范围。报告会记录改动文件、命令退出码及末20行、偏差和未决问题，同时保留此前提交的上下文。
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s03-registry\\.orch\\report.md", "content": "# 报告 · s03-registry（第1轮返工）\n\n## 改了哪些文件\n- `framework/tests/test_surprise_s03_registry.py`：`te…
tool_call run_terminal_command: {"command": "Remove-Item .orch\\tmp\\msg.txt; git status --short", "description": "Remove scratch message; confirm clean tree"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "# 报告 · s03-registry\n\n## 改了哪些文件\n- `framework/surprise/harness/oracles/registry.py`：新增 `register` / `get_handler` / `run…
tool_update [completed]: exit: 0
thought: 检查了 git 状态，当前工作区干净。
text: 第1轮审查已按意见返工，提交 `a7cce8b`（`grok/s03-registry`）。 只改了 `framework/tests/test_surprise_s03_registry.py`。两个缺模块测试改为用 `monkeypatch` 复制 `_HANDLERS` 和 `_LAZY_MODULES`：先塞假的 pass handler，再从复制…
end: stopReason=end_turn turns=10 cost_usd=0.33374332
orch.exit: {"pkg": "s03-registry", "run": 2, "at": "2026-10-09T01:42:45+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s03-registry（第1轮返工）

## 改了哪些文件
- `framework/tests/test_surprise_s03_registry.py`：`test_missing_later_module_is_not_a_pass` 与 `test_evaluate_accounts_datafusion_and_missing_handler` 改为用 pytest `monkeypatch` 复制 `_HANDLERS` / `_LAZY_MODULES`。先在复制表里塞假的 pass handler，再从复制的 handler 表去掉 later ID，把 lazy 模块改成 `surprise.harness.oracles._s03_registry_absent_*`。退出时 monkeypatch 恢复。ImportError、evaluate 的 `invalid/harness_error`、LIMIT 的 `nondeterministic` 断言全部保留。

实现代码未改。未创建后三包文件。

提交：`a7cce8b`（`grok/s03-registry`；其上为 `c9c4da5`）

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
165 passed, 3 skipped in 6.59s
```

命令：`python -m surprise.gates.s03 --only registry`（在 `framework/`）
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
S03 GATE: PASS (1/1 groups passed)
```

命令：`python -m surprise.gates.s02`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 32 files hashed (567be298985e); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

## 与说明的偏差
无。审查要求只修测试长期有效性：缺模块路径不再依赖仓库里 later 文件是否存在；假 pass handler 被隔离后仍走 ImportError，不伪装成通过。

## 未决问题
- S3 的 local / cross / version / matrix 门槛组此时缺后续包，预期红，本包未改门槛。
````

## 8. 结论（编排者填）

合并。编排者读完整 diff 与返工 diff，独立复跑 pytest 为165 passed/3 skipped，S01 7/7、S02 5/5、S03 registry 1/1。唯一门槛红旗来自未派发的四类模块，符合阶段预期。修改均在允许路径，旧代码、门槛、conftest 零改动；无新增skip/xfail、无删有效断言、无新增吞错、无密钥。S2 拒绝 DataFusion/尚未实现ID 的过时断言按需求定向升级，并新增支持/错误断言。

返工1轮：第1轮的两个新增测试假定后三包的模块不存在；第2轮改为monkeypatch明确模拟缺模块，并先注入假的已存在handler验证隔离，所有错误与记账断言保留。实现代码没有返工。已核对各轮shell命令；执行者删过自己创建的一个临时提交信息文件，没有递归清理、没有被拒后绕过，也没有碰主检出区。后续brief再次强调不清理临时目录。

偏差：registry懒导入后要求模块自行register；后续三个brief已明确注册调用。brief提及的0790d4c是门槛提交，实际派发基线d337846只多了一次交接状态提交，代码一致。包花费两轮共约0.9707美元。
