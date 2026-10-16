# 审查包 · s12-docs

- 生成时间：2026-10-16T15:23:38+11:00
- 基线：`session/s12`（174c8a2cb81a）
- 分支：`grok/s12-docs` @ 285977ec75b1，基线之上 2 个提交
- 运行：共 2 轮（返工 1 轮），最近一轮退出码 0，用时 2m04s
- grok：grok 1.0.46 (2765805b9442)；会话 `ea97dac5-2d2e-4659-9c6b-847e38816186`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s12..grok/s12-docs
git diff -M --stat session/s12..grok/s12-docs
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`README.md`、`framework/README.md`、`framework/AGENTS.md`、`framework/surprise/ARCHITECTURE.md`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `README.md` |  |
| M | `framework/AGENTS.md` |  |
| M | `framework/README.md` |  |
| A | `framework/surprise/ARCHITECTURE.md` |  |

提交：

- cdf1786 Junke: docs(s12): README, AGENTS.md, and surprise architecture for the new framework
- 285977e Junke: docs(s12): fix AGENTS example, metrics/acceptance, pure_llm note

## 2. diff 统计

```text
 README.md                          |  24 +++---
 framework/AGENTS.md                |  40 ++++++---
 framework/README.md                | 147 +++++++++++++++++++++----------
 framework/surprise/ARCHITECTURE.md | 172 +++++++++++++++++++++++++++++++++++++
 4 files changed, 312 insertions(+), 71 deletions(-)
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
- 日志 `.orch/logs/s12-docs.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 新增 `refs/heads/grok/s12-move` @ 938aee0ac409
- 移动 `refs/heads/session/s12` 174c8a2cb81a → 938aee0ac409

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s12-docs.jsonl`：2156 条事件（available_commands 53，end 2，orch.exit 2，orch.start 2，plan 4，text 661，thought 695，tool_call 119，tool_call_update 584，usage 34）；各轮合计 34 个模型回合，grok 上报花费 0.9351 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "docs(s12): fix AGENTS example, metrics/acceptance, pure_llm note\n\nAddress review-1: the DeepSeek exam…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "# 报告 · s12-docs\n\n## 改了哪些文件\n- `framework/surprise/ARCHITECTURE.md`：新增，惊讶驱动框架的架构文档（数据流、十个子包、不变式、与旧系统的关系、文档索引）。\n- `frame…
thought: 已提交三个修改文件，根目录的 README.md 未作变更。
tool_call run_terminal_command: {"command": "git add framework/AGENTS.md framework/README.md framework/surprise/ARCHITECTURE.md; git commit -F .orch/tmp/msg.txt; git status; git log -2 --oneline; Remove-Item .or…
tool_update [in_progress]: 
tool_update [in_progress]: warning: in the working copy of 'framework/README.md', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/surprise/ARCHITECTURE.md…
tool_update [in_progress]: warning: in the working copy of 'framework/README.md', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/surprise/ARCHITECTURE.md…
tool_update [in_progress]: warning: in the working copy of 'framework/README.md', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/surprise/ARCHITECTURE.md…
tool_update [completed]: exit: 0 warning: in the working copy of 'framework/README.md', LF will be replaced by CRLF the next time Git touches it warning: in the working copy of 'framework/surprise/ARCHITE…
text: 审查意见四处都已改完，提交在 `grok/s12-docs`（`285977e`）。 - `framework/AGENTS.md`：示例命令改成 `python main.py --engine duckdb --mode full --iterations 3 --queries-per-iter 10`。 - `framework/surprise/…
end: stopReason=end_turn turns=8 cost_usd=0.32166652
orch.exit: {"pkg": "s12-docs", "run": 2, "at": "2026-10-16T15:23:25+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s12-docs

## 改了哪些文件
- `framework/AGENTS.md`：DeepSeek 示例命令改为 `python main.py --engine duckdb --mode full --iterations 3 --queries-per-iter 10`（`main.py` 真实有的参数）；后半句转发说明保留。
- `framework/surprise/ARCHITECTURE.md`：`surprise/metrics/` 一节按代码改准 CIAO / RQ6 / dups / rundata；`surprise/theory/` 一节补全接受检验顺序。
- `framework/README.md`：`pure_llm` 命令加注释，说明会真的调用 LLM、需要 `DEEPSEEK_API_KEY`，`--llm-offline` 只用缓存。
- `README.md`：本轮未改。

## 跑了哪些命令

### `python -c "print(sum(1 for _ in open(r'surprise/ARCHITECTURE.md', encoding='utf-8')))"`（在 `framework/` 下）
退出码：0
```
172
```

### `python -m surprise.gates.s12 --only docs`（在 `framework/` 下）
退出码：1（预期：docs 组在本 worktree 不全绿）

完整输出：
```
[FAIL] docs: 19 doc problems: ['README.md: names `framework/surprise/baselines/coevodb_v1/`, which does not exist', 'README.md: names `framework/archive/`, which does not exist', 'framework/README.md: names `archive/`, which does not exist', 'framework/README.md: names `archive/coevo/`, which does not exist', 'framework/README.md: names `archive/repair_bench/`, which does not exist', 'framework/README.md: names `surprise/baselines/coevodb_v1/`, which does not exist', 'framework/README.md: names `archive/repair_bench/run_localize.py`, which does not exist', 'framework/AGENTS.md: names `surprise/baselines/coevodb_v1/main.py`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/main.py`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/evolution/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/agents/bug_hunter.py`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/guidelines/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `surprise/baselines/coevodb_v1/coverage/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `archive/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `archive/coevo/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `archive/repair_bench/`, which does not exist', 'framework/surprise/ARCHITECTURE.md: names `archive/README.md`, which does not exist']
S12 GATE [only: docs]: FAIL (0/1 groups passed)
```

逐条归类（与上一轮相同的 19 条；全部属于说明里四个前缀；其余问题为零）：

| # | 文档 | 路径 | 前缀 |
|---|---|---|---|
| 1 | README.md | `framework/surprise/baselines/coevodb_v1/` | `framework/surprise/baselines/coevodb_v1/` |
| 2 | README.md | `framework/archive/` | `framework/archive/` |
| 3 | framework/README.md | `archive/` | `archive/` |
| 4 | framework/README.md | `archive/coevo/` | `archive/` |
| 5 | framework/README.md | `archive/repair_bench/` | `archive/` |
| 6 | framework/README.md | `surprise/baselines/coevodb_v1/` | `surprise/baselines/coevodb_v1/` |
| 7 | framework/README.md | `archive/repair_bench/run_localize.py` | `archive/` |
| 8 | framework/AGENTS.md | `surprise/baselines/coevodb_v1/main.py` | `surprise/baselines/coevodb_v1/` |
| 9 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/` | `surprise/baselines/coevodb_v1/` |
| 10 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/` | `surprise/baselines/coevodb_v1/` |
| 11 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/main.py` | `surprise/baselines/coevodb_v1/` |
| 12 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/evolution/` | `surprise/baselines/coevodb_v1/` |
| 13 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/agents/bug_hunter.py` | `surprise/baselines/coevodb_v1/` |
| 14 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/guidelines/` | `surprise/baselines/coevodb_v1/` |
| 15 | framework/surprise/ARCHITECTURE.md | `surprise/baselines/coevodb_v1/coverage/` | `surprise/baselines/coevodb_v1/` |
| 16 | framework/surprise/ARCHITECTURE.md | `archive/` | `archive/` |
| 17 | framework/surprise/ARCHITECTURE.md | `archive/coevo/` | `archive/` |
| 18 | framework/surprise/ARCHITECTURE.md | `archive/repair_bench/` | `archive/` |
| 19 | framework/surprise/ARCHITECTURE.md | `archive/README.md` | `archive/` |

本轮按审查意见未再跑 pytest。

## 与说明的偏差
无。

## 未决问题
无。docs 组 19 条 "does not exist" 留给编排者在合并 `s12-move` 之后核对。
````

## 8. 结论（编排者填）

合并（返工 1 轮）。理由：只改了允许的四个文件，worktree 之外的变化都是编排者自己的操作，日志与 diff 里没有密钥。逐行读过四个文件：架构文档点名的 36 个函数 / 类 / 常数逐个 grep 过都存在，`surprise.experiments.loop` 的示例命令在主检出区实跑通过（3 条实验），`pure_llm` 与 `main.py` 的参数按 `--help` 核对。第 1 轮返工四处：AGENTS.md 示例命令用了 `main.py` 没有的 `--rounds` 等参数（原文就错）；架构文档把 `partition.py` 说成 CIAO 的配对工具（它是 RQ6 的家族划分一致性），并补上 `boundary.py`、`recall.py`、`dups.py`、`rundata.py`；接受规则补全为 S7 的五步顺序；`pure_llm` 注明会真的调用 LLM。返工后逐条核对（`boundary.classify` 的四个取值属实）。`docs` 组的 19 条"路径不存在"都指向 `s12-move` 交付的路径，合并两个包之后在会话分支上复核；pytest 未复跑（只改文档），会话收尾时全量复跑。
