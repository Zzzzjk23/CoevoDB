# 审查包 · s02-oracles

- 生成时间：2026-10-08T22:56:16+11:00
- 基线：`session/s02`（5a2fb50a3595）
- 分支：`grok/s02-oracles` @ 60fa36aa9a04，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 9m50s
- grok：grok 1.0.46 (2765805b9442)；会话 `8c1c2604-b67e-43ea-b121-6516ffff5c86`

## 红旗汇总

- 门槛未通过（退出码 1）
- 新增宽泛的异常捕获 1 处（确认没有吞掉失败）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s02..grok/s02-oracles
git diff -M --stat session/s02..grok/s02-oracles
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/harness/oracles/**`、`framework/surprise/harness/evaluate.py`、`framework/tests/test_surprise_oracles.py`、`framework/tests/test_surprise_evaluate.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/harness/evaluate.py` |  |
| A | `framework/surprise/harness/oracles/__init__.py` |  |
| A | `framework/surprise/harness/oracles/common.py` |  |
| A | `framework/surprise/harness/oracles/forms.py` |  |
| A | `framework/surprise/harness/oracles/norec.py` |  |
| A | `framework/surprise/harness/oracles/plan_variant.py` |  |
| A | `framework/surprise/harness/oracles/tlp.py` |  |
| A | `framework/tests/test_surprise_evaluate.py` |  |
| A | `framework/tests/test_surprise_oracles.py` |  |

提交：

- 7d9b9e2 Junke: S2: add three-valued adapters for TLP, NoREC, and plan variant
- 60fa36a Junke: S2: reject unstorable evaluate arguments before execution

## 2. diff 统计

```text
 framework/surprise/harness/evaluate.py             |  76 ++++
 framework/surprise/harness/oracles/__init__.py     |  94 +++++
 framework/surprise/harness/oracles/common.py       | 190 +++++++++
 framework/surprise/harness/oracles/forms.py        | 170 ++++++++
 framework/surprise/harness/oracles/norec.py        |  63 +++
 framework/surprise/harness/oracles/plan_variant.py | 123 ++++++
 framework/surprise/harness/oracles/tlp.py          | 146 +++++++
 framework/tests/test_surprise_evaluate.py          | 181 +++++++++
 framework/tests/test_surprise_oracles.py           | 443 +++++++++++++++++++++
 9 files changed, 1486 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，0m03s；passed 141，skipped 3

```text
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 50%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [100%][0m
[32m[32m[1m141 passed[0m, [33m3 skipped[0m[32m in 3.29s[0m[0m
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，0m17s

```text
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 141 passed (baseline 64): [32m[32m[1m141 passed[0m, [33m3 skipped[0m[32m in 3.28s[0m[0m
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-oracles\framework\surprise\harness\__init__.py)
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: FAIL (4/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- `framework/surprise/harness/evaluate.py:51` `except Exception as exc:`

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s02-oracles.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s02-manifest`（原 5a2fb50a3595）
- 移动 `refs/heads/session/s02` 5a2fb50a3595 → 522434ca531e

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s02-oracles.jsonl`：4719 条事件（auto_compact_completed 1，auto_compact_failed 1，auto_compact_started 2，available_commands 60，end 2，orch.exit 2，orch.start 2，plan 3，text 917，thought 3211，tool_call 95，tool_call_update 374，usage 49）；各轮合计 49 个模型回合，grok 上报花费 1.7739 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: 
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "1→\"\"\"Run one oracle judgement and append it to the experiment ledger.\n\nPass and invalid executions are recorded too. A failur…
tool_update [completed]: {"type": "GrepSearch", "stdout": [60, 119, 111, 114, 107, 115, 112, 97, 99, 101, 95, 114, 101, 115, 117, 108, 116, 32, 119, 111, 114, 107, 115, 112, 97, 99, 101, 95, 112, 97, 116,…
tool_update [in_progress]: 60fa36a S2: reject unstorable evaluate arguments before execution
tool_update [completed]: exit: 0 60fa36a S2: reject unstorable evaluate arguments before execution 7d9b9e2 S2: add three-valued adapters for TLP, NoREC, and plan variant 5a2fb50 orch(s02): correct a count…
thought: 检查了 git 状态，未发现工作区有未提交的更改。 返工已完成。evaluate.py 已添加 ExperimentRecord 占位符，测试通过，报告已更新第 1 轮返工章节。工作区干净，无需重复提交。
tool_call read_file: {"target_file": "D:\\CoevoDB\\.worktrees\\s02-oracles\\framework\\tests\\test_surprise_evaluate.py", "offset": 140, "limit": 50}
tool_update [completed]: {"type": "ReadFile", "FileContent": {"content": "140→ case = _case()\n with pytest.raises(ValueError):\n evaluate(case, \"no_such_oracle\", ledger=ledger, run_id=\"run-1\", purpos…
thought: 返工已完成。我将向用户汇报当前状态。
text: 第 1 轮返工已经在 `grok/s02-oracles` 的 `60fa36a` 上，工作区是干净的。`.orch/report.md` 末尾有「第 1 轮返工」一节。 `evaluate()` 仍先检查 `oracle`、引擎和 `run_id`。随后用一条丢弃的占位 `ExperimentRecord` 按契约校验 `purpose`、`p_t`、`…
end: stopReason=end_turn turns=12 cost_usd=0.64056612
orch.exit: {"pkg": "s02-oracles", "run": 2, "at": "2026-10-08T22:56:07+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s02-oracles

## 改了哪些文件
- `framework/surprise/harness/oracles/__init__.py`：新增 `IMPLEMENTED` 与 `judge`（筛查后调用旧 oracle，不吞异常）
- `framework/surprise/harness/oracles/forms.py`：新增 `GroupedForm`、`split_grouped`、`full_query`
- `framework/surprise/harness/oracles/common.py`：新增记录每次 `run` 的代理，以及 Candidate / None 到 `Label` 的映射
- `framework/surprise/harness/oracles/tlp.py`：新增 TLP 的 WHERE、GROUP BY、DISTINCT 适配器
- `framework/surprise/harness/oracles/norec.py`：新增 NoREC 适配器
- `framework/surprise/harness/oracles/plan_variant.py`：新增 plan variant 适配器（只把折叠后的查询当查询形式）
- `framework/surprise/harness/evaluate.py`：新增 `evaluate`，每次调用记一条账，判定异常记成 `harness_error`
- `framework/tests/test_surprise_oracles.py`：新增形式解析、三值标签、假 runner 与参数错误测试
- `framework/tests/test_surprise_evaluate.py`：新增记账、异常记账、拒绝不留记录、重开账本测试

提交：`7d9b9e2`（`grok/s02-oracles`）

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 50%]
.......................................................................  [100%]
140 passed, 3 skipped in 4.42s
```

命令：`python -m surprise.gates.s02 --only contracts ledger oracles evaluate`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE [only: contracts, ledger, oracles, evaluate]: PASS (4/4 groups passed)
```

命令：`python -m surprise.gates.s01`（在 `framework/`）
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 140 passed (baseline 64): 140 passed, 3 skipped in 3.84s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.all`（在 `framework/`）
退出码：1（说明里写明的预期：`manifest` 属于并行的另一个包）

```
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 140 passed (baseline 64): 140 passed, 3 skipped in 3.73s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-oracles\framework\surprise\harness\__init__.py)
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: FAIL (4/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

命令：`git status --short`（在 worktree 根，提交之后）
退出码：0
输出为空。

## 与说明的偏差
无。

## 未决问题
无。

## 第 1 轮返工

`evaluate` 在调用 `judge` 之前，用一条丢弃的占位 `ExperimentRecord` 按契约校验 `purpose`、`p_t`、`spec`、`phi`、`theory_version`。不合法则抛 `ValueError`，不调用 `runner_factory`，也不写账本。`oracle`、引擎、`run_id` 三项检查仍在最前面。

改动：
- `framework/surprise/harness/evaluate.py`：修改，执行前增加占位记录校验
- `framework/tests/test_surprise_evaluate.py`：修改，补 `purpose=""`、`p_t=1.5`、`spec` 含集合这三例

提交：`60fa36a`（`grok/s02-oracles`）

与说明的偏差：无。未决问题：无。

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 50%]
........................................................................ [100%]
141 passed, 3 skipped in 3.37s
```

命令：`python -m surprise.gates.s02 --only contracts ledger oracles evaluate`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE [only: contracts, ledger, oracles, evaluate]: PASS (4/4 groups passed)
```

命令：`python -m surprise.gates.s01`（在 `framework/`）
退出码：0

```
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 141 passed (baseline 64): 141 passed, 3 skipped in 3.32s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
```

命令：`python -m surprise.gates.all`（在 `framework/`）
退出码：1（预期：`manifest` 属于并行的另一个包；本 worktree 的门槛还没有编排者后补的 evaluate 参数检查）

```
=== gate s01 ===
[PASS] baseline tag: v1-baseline -> 55c5512
[PASS] skeleton: surprise/ + 10 subpackages import
[PASS] engine environments: duckdb 1.5.5; datafusion 54.0.0; sqlite 3.51.0; duckdb-1.1.3: duckdb 1.1.3; datafusion-50.0.0: datafusion 50.0.0
[PASS] main.py --help: exit 0
[PASS] pytest: 141 passed (baseline 64): 141 passed, 3 skipped in 3.30s
[PASS] campaign scripts: 41 scripts in campaigns/, 39 answer --help, 2 syntax-checked
[PASS] DuckDBRunner move: 6 import orders ok; _remote_exec imports in duckdb-1.1.3
S01 GATE: PASS (7/7 checks passed)
=== gate s02 ===
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[FAIL] manifest: ImportError: cannot import name 'manifest' from 'surprise.harness' (D:\CoevoDB\.worktrees\s02-oracles\framework\surprise\harness\__init__.py)
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: FAIL (4/5 groups passed)
=== summary ===
s01: PASS
s02: FAIL (exit 1)
GATES: FAIL (1/2 passed)
```

命令：`git status --short`（在 worktree 根，提交之后）
退出码：0
输出为空。
````

## 8. 结论（编排者填）

**合并（返工 1 轮）。** 理由，均为编排者独立核对，不采信第 7 节的自述：

- 范围：9 个新文件全部在允许路径内，禁区和旧代码零改动；worktree 干净。第 5 节列出的 ref 变化都是编排者自己的操作：合并并清理了 `grok/s02-manifest`，`session/s02` 因合并和补门槛而前移；主检出区干净。
- 复跑（第 3 节）：pytest 141 passed / 3 skipped（基线 126，新增 15 个）；`s01` 7/7；`s02` 的 contracts、ledger、oracles、evaluate 四组通过。红旗"门槛未通过"是预期的：manifest 组属于并行的另一个包，这个 worktree 里没有。
- 读完了七个模块的全部代码（`oracles/__init__.py`、`common.py`、`forms.py`、`tlp.py`、`norec.py`、`plan_variant.py`、`evaluate.py`）：
  - 流程顺序与任务说明一致：`setup` 报错 → 确定性筛查 → 前提检查 → 换一个新 runner、包上记录代理、调旧 oracle 的 `check()`；用过的 runner 都在 `finally` 里关闭。
  - 什么算差异完全交给旧 `check()`：适配器里没有任何比较结果的代码，只有把 `Candidate` 映射成 `fail_kind`、把 None 按记录下来的结果拆成 pass / invalid、以及从记录里算行为画像。
  - plan variant 只看 `sql == full` 的执行，切换开关的语句不参与判定；变体与执行按顺序对应。
  - `split_grouped` 只认说明写的两种形态，选择列表是否含聚合或窗口函数用旧的 `tlp_applicable` 判断；`full_query` 三条分支与用例表的期望字符串一致。
  - 没有 LLM 调用；`Label` 里没有耗时或时间。
- 编排者另做的差分核对（门槛之外）：从种子语料取 60 个种子、经旧的变异器得到 196 个用例，每个用例对三个 oracle 各判两次，共 588 组。新标签（y、子类型或原因、开关）与一份直接调用旧 oracle 的独立映射逐组比较，**出入为 0，两次判定不一致为 0**。其中真实出现了 TLP 与 NoREC 的 wrong_result 各 1 例、plan variant 的 error_mismatch 1 例、timeout 1 例、值依赖错误 5 例。
- 红旗"新增宽泛的异常捕获 1 处"是任务说明要求的那一处：`evaluate.py` 里把判定过程中的异常记成 `invalid / harness_error` 并照样入账，旁边有注释。
- 红旗"ref 被删"是编排者清理已合并的 `grok/s02-manifest`。
- 日志：两轮的 shell 命令全部在 worktree 内（pytest、门槛、git status / add / commit），没有 pip，没有被 deny 规则拦下的调用；文件工具涉及的 47 个路径都在 worktree 内。diff 与日志里没有密钥。

返工的那一轮：

- 起因是任务说明和门槛都漏了一点，不是执行者理解错了。`evaluate()` 原先只在执行前检查 `oracle`、引擎、`run_id` 三项，`purpose`、`p_t`、`spec` 等是在判定之后构造记录时才校验的；这些参数不合法时，用例已经执行过了却没有记录。
- 编排者先在会话分支上给门槛的 evaluate 组补了检查（提交 522434c），并实测它能拦下第 1 轮的代码（三组坏参数共打开了 6 个 runner）。
- 第 2 轮的改法与返工意见一致：在 `judge` 之前用一个占位标签把 `ExperimentRecord` 构造一遍，校验规则仍只有契约里那一份；另加了一个测试。只改了 `evaluate.py` 和它的测试文件，适配器没有动，所以上面的差分核对结果仍然有效。
- 用主检出区的新门槛对这个分支的代码复核：contracts、ledger、oracles、evaluate 四组全部通过。

留意但不处理的一点：`theory/contracts.py`（上一个包）和这个包都依赖 `oracles.determinism` 里带下划线的函数（`_top_level_positions`、`_top_level_from_pos`），任务说明允许。S12 整理旧代码时如果动到它们，要同步改 `forms.py`。

