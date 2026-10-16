# 返工意见 · s12-docs · 第 1 轮

整体很好：四个文件的结构、口吻和事实大多准确；架构文档里点名的函数与模块我逐个核对过都存在，文档里的 loop 命令我实跑过能用。下面四处要改，只改这些，其余不要动。

1. `framework/AGENTS.md`，DeepSeek 一节的示例命令：
   `python main.py --engine duckdb --mode full --rounds 3 --population-size 5 --queries-per-test 10`
   里的 `--rounds`、`--population-size`、`--queries-per-test` 三个参数 `main.py` 根本没有（原文就错，`python main.py --help` 可查；旧主循环的参数是 `--iterations`、`--queries-per-iter`、`--seed-mutations-per-iter`）。既然这次更新了这一行，就改成能跑的写法，例如
   `python main.py --engine duckdb --mode full --iterations 3 --queries-per-iter 10`。
   后半句"That command is the old main loop (now at ...; main.py forwards)"保留。

2. `framework/surprise/ARCHITECTURE.md`，`surprise/metrics/` 一节："CIAO: `surprise/metrics/rq.py` reads the theory store; pairing helpers live in `surprise/metrics/partition.py`" 不对：
   - CIAO 是 `surprise/metrics/rq.py` 的 `ciao(wb)`（按代快照的理论 × 按代的记录批次），与 `partition.py` 无关；
   - `surprise/metrics/partition.py` 的 `pair_agreement(pred, truth)` 是 RQ6 的**家族划分**与人工判定的成对一致性；
   - 同属 RQ6 的还有 `surprise/metrics/boundary.py`（假设边界与上游修复范围的吻合度：吻合 / 过宽 / 过窄 / 交错，修复条件表在 `surprise/metrics/data/fix_conditions.json`）和 `surprise/metrics/recall.py`（已知缺陷召回）；重复率与家族计数在 `surprise/metrics/dups.py`；单次运行的读取在 `surprise/metrics/rundata.py`（`RunData`）。
   按这些事实把这一节改准（每条一行即可）。写之前自己打开这几个文件核对名字。

3. 同一文件 `surprise/theory/` 一节的接受规则写漏了两条。按 `framework/surprise/docs/HANDOFF.md` S7 一节"规则"里的"接受检验"改成完整的顺序：指纹在负记忆里就拒；没有押注就拒；触发记录上的惊讶之和上升就拒；留出记录上的惊讶之和上升就拒；（触发变化 + 留出变化 + 长度变化）不是严格为负就拒；否则接受。被拒于触发或留出的编辑进负记忆。押注落空时回滚（这一句原文已有，保留）。

4. `framework/README.md` 的 "Baseline arms" 里 `python -m surprise.baselines.pure_llm --out DIR --seed 0`：加一句注释说明它会真的调用 LLM、需要 `DEEPSEEK_API_KEY`（`--llm-offline` 只用缓存回复）。

验收照旧：`python -m surprise.gates.s12 --only docs` 只剩那 19 条（或改动后相应的）指向移动后路径的 "does not exist"，其余为零；报告里更新"跑了哪些命令"一节（不需要再跑 pytest，只改了文档）。提交到同一分支，写 `.orch/report.md`（覆盖上一轮的）。
