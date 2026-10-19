# 审查包 · s15-rundata

- 生成时间：2026-10-19T16:26:50+11:00
- 基线：`session/s15`（c4bace369102）
- 分支：`grok/s15-rundata` @ 564b602faa26，基线之上 1 个提交
- 运行：共 2 轮（返工 0 轮），最近一轮退出码 0，用时 12m57s
- 执行者：codex codex-cli 0.163.0；会话 `01a1526d-fc4a-7252-b57e-129330b6a9c5`；换过执行者：第 1 轮之后 grok → codex

## 红旗汇总

- 门槛未通过（退出码 1）
- 执行者日志里有 1 条 error / turn.failed 事件

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s15..grok/s15-rundata
git diff -M --stat session/s15..grok/s15-rundata
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/metrics/rundata.py`、`framework/surprise/metrics/rq.py`、`framework/surprise/metrics/dedup.py`、`framework/surprise/metrics/curve.py`、`framework/tests/test_surprise_s15_rundata.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/metrics/curve.py` |  |
| M | `framework/surprise/metrics/dedup.py` |  |
| M | `framework/surprise/metrics/rq.py` |  |
| M | `framework/surprise/metrics/rundata.py` |  |
| A | `framework/tests/test_surprise_s15_rundata.py` |  |

提交：

- 564b602 Junke: metrics(s15): stream run ledgers and preserve metric outputs

## 2. diff 统计

```text
 framework/surprise/metrics/curve.py          |  57 ++-
 framework/surprise/metrics/dedup.py          |   2 +-
 framework/surprise/metrics/rq.py             | 255 +++++++++--
 framework/surprise/metrics/rundata.py        | 230 +++++++++-
 framework/tests/test_surprise_s15_rundata.py | 661 +++++++++++++++++++++++++++
 5 files changed, 1144 insertions(+), 61 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，4m21s；passed 948，skipped 3

```text
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 98%]
...............                                                          [100%]
948 passed, 3 skipped in 260.57s (0:04:20)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，38m45s

```text
b/s1-r0 done
a/s2-r0 done
b/s2-r0 done
[FAIL] archive: pack failed: 1 D:\CoevoDB\.venv\Scripts\python.exe: No module named surprise.experiments.archive

[FAIL] docs: SERVER.md: no heading '### 5.7 \u5e76\u884c\u7f51\u683c'
[PASS] scope: 10 paths changed (s14-done-r2..work tree), all in scope; harness and lower layers untouched (0s)
S15 GATE: FAIL (2/11 groups passed)
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
s10: PASS
s11: FAIL (exit 1)
s12: PASS
s13: PASS
s14: PASS
s15: FAIL (exit 1)
GATES: FAIL (12/15 passed)
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
- 日志 `.orch/logs/s15-rundata.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s15-grid` c4bace369102 → 6692708408e0
- 移动 `refs/heads/grok/s15-llm` c4bace369102 → 6a907c03c1fe
- 移动 `refs/heads/session/s15` c4bace369102 → b6abeb12a56f

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s15-rundata.jsonl`：3288 条事件（available_commands 54，error 1，item.completed 55，item.started 44，orch.exit 2，orch.start 2，text 108，thought 2658，thread.started 1，tool_call 88，tool_call_update 224，turn.completed 1，turn.started 1，usage 49）；各轮合计 codex：1 轮，输入 3292630 token（其中缓存 3185152），输出 24815（其中推理 14163），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git commit -m "metrics(s15): stream run ledgers and preserve metric outputs"'
exec [exit 0]: [grok/s15-rundata 564b602] metrics(s15): stream run ledgers and preserve metric outputs 5 files changed, 1144 insertions(+), 61 deletions(-) create mode 100644 framework/tests/tes…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@' import json from pathlib import Path names = ['rundata-focused.log', 'rundata-focused-final.log', 'ru…
exec [exit 0]: {"rundata-focused.log": " \"executions\": 7,\n \"wall_s\": 3600.0,\n \"llm_calls\": 0,\n \"input_tokens\": 0,\n \"output_tokens\": 0,\n \"usd\": None,\n \"per_family\": {\n \"exec…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git diff --check; git rev-parse --short HEAD; git branch --show-current'
exec [exit 0]: 564b602 grok/s15-rundata
file_change [completed]: add D:\CoevoDB\.worktrees\s15-rundata\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git show --stat --oneline HEAD; git check-ignore .orch/report.md; Get-Content -Encod…
exec [exit 0]: 564b602 metrics(s15): stream run ledgers and preserve metric outputs framework/surprise/metrics/curve.py | 57 ++- framework/surprise/metrics/dedup.py | 2 +- framework/surprise/met…
text: 已提交 `564b602`，工作树干净。 - 测试：948 passed，3 skipped。 - S15 流式门槛通过：输出一致，峰值 358 MB，翻倍增加 42 MB。 - S11 指定七组全部通过。 实现扩展及完整记录见 [报告](D:/CoevoDB/.worktrees/s15-rundata/.orch/report.md)。
end: tokens in=3292630 cached=3185152 out=24815 reasoning=14163
orch.exit: {"pkg": "s15-rundata", "run": 2, "at": "2026-10-19T15:44:39+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s15-rundata

分支：`grok/s15-rundata`；提交：`564b602`。
接续上一位执行者留下的 5 个文件，保留可用的流式聚合、延迟物化、SQLancer 和去重改动，修复指标公式并替换大 JSON 的固定头尾截取实现。

## 改了哪些文件

- `framework/surprise/metrics/rundata.py`（修改）：只读读取元数据和 COUNT，按 seq 流式读取，records 首次访问才缓存；识别三种 kind；对指标扫描中的超大 detail 使用只读 SQLite Blob 分块定位和省略，保留默认完整记录迭代。
- `framework/surprise/metrics/rq.py`（修改）：一遍扫描仅保留指标所需字段和数值；恢复 Brier 参考值 rate * (1-rate)，保持全部既有指标结果；SQLancer 执行数取 report，缺失时传播 None。
- `framework/surprise/metrics/dedup.py`（修改）：从迭代器筛选并仅保存失败记录，顺序和结果不变。
- `framework/surprise/metrics/curve.py`（修改）：按流累计完整窗口，保留丢弃尾窗和原有浮点求和顺序。
- `framework/tests/test_surprise_s15_rundata.py`（新增）：13 项测试，覆盖顺序/内容、延迟读取、文件不变、kind、旧实现完整输出、SQLancer、dedup、空账本、兼容属性不被指标路径使用，以及跨块转义/UTF-8/嵌套同名字段。

测得峰值：9500 条记录为 **358 MB**，翻倍至 19000 条后增加 **42 MB**（约 400 MB；门槛输出取整）。上限分别为 800 MB 和 120 MB。输出 SHA256 为 `2a6310744d89e0075ee14f4fac94a961093b9644e65b1ed118adbc87b56c458d`，与冻结值一致。

## 跑了哪些命令

Python 验证命令在 `framework/` 执行；git 命令在 worktree 根执行。最终测试日志由 PowerShell 的 `2>&1 | Tee-Object -FilePath ../.orch/tmp/<日志名>; exit $LASTEXITCODE` 留存，目录未清理。以下逐次给出退出码与输出末 20 行；不足 20 行时全部贴出。

### 首次检查继承改动

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`1`

```text
        }
        assert got["run"]["experiments"] == len(records)
        assert got["rq1"]["executions"] == len(records)
        assert got["rq1"]["families"] == ledger_families(records, data.progress)
        assert got["rq1"]["family_count"] == 1
        assert got["rq1"]["families"][0]["elapsed_s"] == 1.5
        assert got["rq1"]["families"][0]["seq"] == 1
        assert got["rq1"]["duplicate_rate"] == duplicate_rate(_profiled_keys(records))
        assert got["rq1"]["theory_families"] is None
        assert got["rq1"]["families_per_1000"] == 1000.0 / len(records)
        brier, reference = _brier(records)
        assert got["rq2"]["valid"] == len(_valid(records))
        assert got["rq2"]["brier"] == brier
>       assert got["rq2"]["brier_reference"] == reference
E       assert 0.6 == 0.24

tests\test_surprise_s15_rundata.py:259: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s15_rundata.py::test_run_metrics_matches_the_materialized_helpers
1 failed, 5 passed in 0.98s
```

发现继承改动的 Brier 参考值错误，已恢复原公式；原断言保留。

### 修复继承改动后

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`0`

```text
......                                                                   [100%]
6 passed in 1.06s
```

### 新增完整基准对照时

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`1`

```text
                "executions": 7,
                "wall_s": 3600.0,
                "llm_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "usd": None,
                "per_family": {
                    "executions": 7.0,
                    "llm_calls": 0.0,
                    "tokens": 0.0,
                    "usd": None
                }
            }
        }
E       NameError: name 'true' is not defined

tests\test_surprise_s15_rundata.py:525: NameError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s15_rundata.py::test_run_metrics_matches_complete_pre_s15_output
1 failed, 12 passed in 1.64s
```

新增基准字典有 true/false 字面量笔误，已改为 Python 的 True/False；未删除或放宽断言。

### 最终定向测试

命令：`python -m pytest -q tests/test_surprise_s15_rundata.py`  
退出码：`0`

```text
.............                                                            [100%]
13 passed in 1.57s
```

### 完整测试

命令：`python -m pytest -q testing tests`  
退出码：`0`

```text
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 83%]
........................................................................ [ 90%]
........................................................................ [ 98%]
...............                                                          [100%]
948 passed, 3 skipped in 338.35s (0:05:38)
```

3 个 skip 来自既有测试，本包未新增 skip / xfail。

### S15 流式门槛

命令：`python -m surprise.gates.s15 --only stream`  
退出码：`0`

```text
[PASS] stream: same metrics as before S15 on 9500 records; peak 358 MB (before: 3.3 GB on 8600); doubled ledger adds 42 MB (327s)
S15 GATE [only: stream]: PASS (1/1 groups passed)
```

### S11 指定门槛

命令：`python -m surprise.gates.s11 --only runmetrics llm_metrics rq6 dedup coverage pure_llm grid`  
退出码：`0`

```text
[PASS] runmetrics: 31 records, 1 ledger families, Brier 0.2194, 1 high-surprise records, invalid 14, theory length 193.0; all recomputed (36s)
[PASS] llm_metrics: 15 experiments replayed; 2 conjectures, survival 0.0, accuracy 0.7142857142857143 over 7 settled bets; families via {'implement': 0, 'bet': 1, 'translate': 0, 'llm_rule': 0, 'invented_feature': 0}; 23 calls (52s)
[PASS] rq6: classify, F2 fix conditions (1 entries), pair agreement as hand-computed; F2 hypothesis too_narrow (missing [], extra 9 literals); recall 0.5 (6s)
[PASS] dedup: 3 failures, 1 true duplicates; sigma p/r 1.0/1.0, membership p/r None/0.0 (8s)
[PASS] coverage: 4 upstream regression seeds x 2 oracles on 1.5.5 and 1.1.3; {'plan_variant': {'old': {'pass': 4}, 'new': {'pass': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}, 'equivalent_query': {'old': {'invalid': 4}, 'new': {'invalid': 4}, 'fail_old_pass_new': [], 'fail_both': [], 'fail_new_only': []}} (9s)
[PASS] pure_llm: 16 cases from 4 cached calls replayed identically; labels {'pass': 15, 'invalid': 1}; 0 families (9s)
[PASS] grid: 2 arms x 2 seeds in 4.1 min, resumed, report and 7 figures in one command; median families/hour {'surprise': 29.828751645366374, 'old': 29.92434905114654}; p 1.0, A12 0.375 (247s)
S11 GATE [only: runmetrics, llm_metrics, rq6, dedup, coverage, pure_llm, grid]: PASS (7/7 groups passed)
```

### 提交

命令：`git commit -m "metrics(s15): stream run ledgers and preserve metric outputs"`  
退出码：`0`

```text
[grok/s15-rundata 564b602] metrics(s15): stream run ledgers and preserve metric outputs
 5 files changed, 1144 insertions(+), 61 deletions(-)
 create mode 100644 framework/tests/test_surprise_s15_rundata.py
```

### 最终检查

命令：`git status --short; git diff --check; git rev-parse --short HEAD; git branch --show-current`  
退出码：`0`

```text
564b602
grok/s15-rundata
```

git status --short 与 git diff --check 均无输出；工作树干净。

## 与说明的偏差

实现扩展：`iter_records` 增加可选参数 `keep_detail=False`，仅供 `run_metrics` 使用。验收账本有一条约 483 MB 的 JSON；指标不读取 label.detail，而整条解析会产生很高的瞬时内存。因此该模式对大于 32 MiB 的记录使用只读 Blob 分块扫描，只省略 label.detail，再交给 ExperimentRecord.from_json。它不依赖键顺序或固定头尾长度。默认 `iter_records()`、兼容属性 `records` 和 dedup 仍读取完整记录；全部指标 SHA256 不变。没有会话范围或允许路径之外的代码改动。

未改 harness、门槛、文档、旧逻辑和 metrics/report.py；未新增依赖，未打 tag、合并、rebase、push 或切换分支。未自行复制/链接主检出区 framework/results；翻倍账本由指定门槛自身在临时目录构造。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
