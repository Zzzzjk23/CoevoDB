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
