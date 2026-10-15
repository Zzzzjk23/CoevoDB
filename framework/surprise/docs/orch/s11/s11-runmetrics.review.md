# 审查包 · s11-runmetrics

- 生成时间：2026-10-16T05:09:04+11:00
- 基线：`session/s11`（8d9781a47c60）
- 分支：`grok/s11-runmetrics` @ 3e4873c7d231，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 47m54s
- grok：grok 1.0.46 (2765805b9442)；会话 `d209761f-2fa9-404b-b0ce-786b8695613b`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s11..grok/s11-runmetrics
git diff -M --stat session/s11..grok/s11-runmetrics
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/metrics/constants.py`、`framework/surprise/metrics/rundata.py`、`framework/surprise/metrics/rq.py`、`framework/surprise/metrics/boundary.py`、`framework/surprise/metrics/partition.py`、`framework/surprise/metrics/data/fix_conditions.json`、`framework/tests/test_surprise_s11_metrics.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| A | `framework/surprise/metrics/boundary.py` |  |
| A | `framework/surprise/metrics/constants.py` |  |
| A | `framework/surprise/metrics/data/fix_conditions.json` |  |
| A | `framework/surprise/metrics/partition.py` |  |
| A | `framework/surprise/metrics/rq.py` |  |
| A | `framework/surprise/metrics/rundata.py` |  |
| A | `framework/tests/test_surprise_s11_metrics.py` |  |

提交：

- 3e4873c Junke: metrics(s11): per-run RQ1-RQ6 metrics from a run directory

## 2. diff 统计

```text
 framework/surprise/metrics/boundary.py             | 117 ++++
 framework/surprise/metrics/constants.py            |  37 ++
 .../surprise/metrics/data/fix_conditions.json      |  13 +
 framework/surprise/metrics/partition.py            |  72 ++
 framework/surprise/metrics/rq.py                   | 731 +++++++++++++++++++++
 framework/surprise/metrics/rundata.py              | 113 ++++
 framework/tests/test_surprise_s11_metrics.py       | 723 ++++++++++++++++++++
 7 files changed, 1806 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

按 `--skip-tests` 跳过了 pytest 与门槛。

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
- 日志 `.orch/logs/s11-runmetrics.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s11-arms` @ 134967c2d427
- 删除 `refs/heads/grok/s11-fixes`（原 8d9781a47c60）
- 新增 `refs/heads/grok/s11-grid` @ 10adc21b1420
- 移动 `refs/heads/session/s11` 8d9781a47c60 → 10adc21b1420

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s11-runmetrics.jsonl`：5531 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 106，end 1，orch.exit 1，orch.start 1，plan 4，text 378，thought 3991，tool_call 221，tool_call_update 732，usage 94）；各轮合计 94 个模型回合，grok 上报花费 2.4285 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s11-runmetrics\n\n## 改了哪些文件\n- `framework/surprise/metrics/constants.py`：新增。七个指标常数和 `as_dict()`，…
tool_update [in_progress]: 3e4873c metrics(s11): per-run RQ1-RQ6 metrics from a run directory
tool_update [completed]: exit: 0 3e4873c metrics(s11): per-run RQ1-RQ6 metrics from a run directory
thought: Git 工作区干净，没有未提交的更改。
tool_call todo_write: {"todos": [{"id": "tests", "content": "写 test_surprise_s11_metrics.py 并跑通相关测试与门槛", "status": "completed"}, {"id": "finish", "content": "提交并写 .orch/report.md", "status": "completed…
tool_update [completed]: {"type": "Todo", "TodosUpdated": {"summary_for_prompt": "- [completed] impl: 实现 constants/rundata/rq/boundary/partition 与 fix_conditions\n- [completed] tests: 写 test_surprise_s11_…
plan: {"entries": [{"content": "实现 constants/rundata/rq/boundary/partition 与 fix_conditions", "priority": "medium", "status": "completed"}, {"content": "写 test_surprise_s11_metrics.py 并…
thought: 回复需完整且独立。
text: 工作包 `s11-runmetrics` 已完成，提交在 `grok/s11-runmetrics` 的 `3e4873c`。给一个运行目录，可以从账本、progress、理论和 `llm/` 账本算出 RQ1–RQ6 的单次运行指标。 `runmetrics`、`llm_metrics`、`rq6` 三组门槛都通过。全量测试 `789 passed, 3…
end: stopReason=end_turn turns=94 cost_usd=2.42851664
orch.exit: {"pkg": "s11-runmetrics", "run": 1, "at": "2026-10-16T05:08:51+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s11-runmetrics

## 改了哪些文件
- `framework/surprise/metrics/constants.py`：新增。七个指标常数和 `as_dict()`，元组保持为元组。
- `framework/surprise/metrics/rundata.py`：新增。只读打开一个运行目录（配置、报告、progress、唯一账本、按运行词表打开的理论、`llm/` 账本）。
- `framework/surprise/metrics/rq.py`：新增。`label_key`、`ledger_families`、`theory_lengths`、`ciao`、`run_metrics`、`old_metrics`。
- `framework/surprise/metrics/boundary.py`：新增。`classify`、`load_fix_conditions`、`compare`。
- `framework/surprise/metrics/partition.py`：新增。`pair_agreement`（含调整兰德指数，分母为 0 时为 None）。
- `framework/surprise/metrics/data/fix_conditions.json`：新增。说明里的那一条 F2，未改字、未加条目。
- `framework/tests/test_surprise_s11_metrics.py`：新增。手算例子、300 条合成观察的 CIAO、一次 `max_experiments=0` 的真实 `loop.run`，以及打开前后的目录哈希。

## 跑了哪些命令

命令在 `framework/` 下执行。

### `python -m pytest -q tests/test_surprise_s11_metrics.py --tb=line`

退出码：0

```
...............                                                          [100%]
15 passed in 8.29s
```

### `python -m surprise.gates.s11 --only runmetrics llm_metrics rq6`

退出码：0

```
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (26s)
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (35s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (4s)
S11 GATE [only: runmetrics, llm_metrics, rq6]: PASS (3/3 groups passed)
```

### `python -m surprise.gates.s11 --only constants`

退出码：1

```
[FAIL] constants: roles constant REQUEST_DEADLINE_S must be 600.0, got None
S11 GATE [only: constants]: FAIL (0/1 groups passed)
```

metrics 常数在这条失败之前已经核对过。失败文本是 `roles constant`，没有 `metrics constant`。`surprise.baselines.pure_llm` 还没被导入：角色常数先失败，组就停了。

### `python -m pytest -q testing tests`

退出码：0

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 54%]
........................................................................ [ 63%]
........................................................................ [ 72%]
........................................................................ [ 81%]
........................................................................ [ 90%]
........................................................................ [100%]
789 passed, 3 skipped in 190.98s (0:03:10)
```

3 个 skip 是原有测试，本包没有新增 skip / xfail。

## 与说明的偏差
- ciao 组未在 worktree 运行。测试里用 `Workbench` 观察 300 条合成记录，每 100 条 `checkpoint`，覆盖 `theory_lengths` 和 `ciao`（多代、选代、抽样、空批）。
- `p_t` 为 0 或 1 时，高惊讶不调用 `surprise_bits`（该函数要求概率严格落在 (0, 1) 内），这两条仍进入 Brier 和校准分箱。`curve.surprise_curve` 不走这个保护：窗口不大于记录数、且记录里有端点概率时，曲线仍会抛错。短跑门槛里的预测都在 (0, 1) 内。
- `prices` 里没有某次调用的模型名时，`usd` 抛 `ValueError`。说明没有规定这种缺价。
- `arm` 不是 dict 时视为未冻结。说明写的是 `arm` 为 None 或 `arm.get("freeze") != "theory"`；非 dict 的 `arm` 若直接 `.get` 会抛错。

理论家族键在已经用本运行词表打开的 `Workbench` 上按 `dups.new_families` 的规则计算，不调用还没有 `registry=` 的 `new_families()`。`recall.score` 用 `inspect.signature` 判断，有 `registry` 参数时才传入本运行的词表。这两处按说明处理，默认词表上与现有函数的结果一致。

## 未决问题
- `constants` 组停在 `surprise.roles.constants` 的 `REQUEST_DEADLINE_S`（得到 None）。这是别的包的常数，本包未改。
- `vocabulary` 门槛后半段要等 `s11-fixes` 给 `dups.new_families` 和 `recall.score` 加上 `registry=`。本包的 `run_metrics` 在扩展词表上可以算完（`test_extended_vocabulary_opens`）。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
