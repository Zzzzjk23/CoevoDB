# 审查意见 · s09-roles · 第 1 轮返工

整体做得很好：完整 diff 已读，接口、猜想簿、提议、选源表与门槛都对得上；报告里的真实调用实验（推理 token 吃掉上限、F7/boundary 做不到）很有价值。你在报告里提出的几件事编排者都定了，本轮按下面改。只改列出的地方。

编排者已在主检出区 `session/s09` 改了门槛（提交 04c0da9），**你的 worktree 里的门槛还是旧的**，以本意见为准：

- `IMPLEMENTER_MAX_TOKENS` 2000 → **8000**；`CONJECTURER_MAX_TOKENS` 8000 → **16000**。
- `F7/boundary` 的规格改成 `required = ["ast:expr:interval", "data:type:date"]`、`forbidden = ["ast:expr:date_arith"]`（date_arith 按词表定义必带 INTERVAL，原规格做不到）。

## 要改的

1. **`framework/tests/test_surprise_roles_gateway.py` 第 349 行**（允许路径本轮加入这个文件，只改这一处）：`assert not hasattr(R, "Implementer")` 是网关包在实现器还没导出时写的，现在说明要求导出它，这条断言作废。改成正面的断言：`from surprise.roles.implementer import Implementer as ImplementerClass` 之后 `assert R.Implementer is ImplementerClass`。同一个测试函数里后面的部分（新进程里的隔离探测）原样保留，并确认它跑完、通过。
2. **`framework/surprise/roles/constants.py`**：`IMPLEMENTER_MAX_TOKENS = 8000`、`CONJECTURER_MAX_TOKENS = 16000`，别的不动。（你的 worktree 里 `python -m surprise.gates.s09 --only constants` 与 `test_constants_match_the_gate_table` 会因为旧门槛而失败——**预期如此**，报告里写明，不要去动门槛或放宽测试。）
3. **猜想者的提示自相矛盾**：它同时写了 "Use at most two predictions" 与 "Write at most {CONJECTURER_MAX_PREDICTIONS} predictions"。删掉 "at most two" 那一句，保留 "Write the JSON object first. Do not analyse at length before the JSON."；上限放宽到 16000 后不需要压到两条。仍要求至少一条 fail、一条 pass 的预测。
4. **DuckDB 的选源只取文件开头 100 行**，那里多半是 include 与注释，看不到优化器的逻辑。改成：命中的 k 个文件（最多 `SOURCE_MAX_FILES` 个）每个取第 1 行到第 `SOURCE_MAX_LINES // k` 行（一个文件时就是前 400 行）。删掉 `_DUCKDB_HEAD`。
5. **`ImplementerSource` 只在实现出来的那一次选择里提供候选**：没被选中就再也不会出现（规格已记为做过），猜想的预测因此可能永远不被检验。改成：
   - 新目标的实现照旧只在"一个新 index 的第 1 轮"做，最多 `per_choice` 个；
   - 但**每一次** `candidates` 调用（任何 index、任何轮）都返回到目前为止**全部** `ok` 的尝试各一个 `Candidate`，按尝试的先后排列。已经执行过的用例由 Hunter 自己按"已做过"过滤掉，这里不必管。
   - 相应地补测试：一个没被选中的候选在下一次选择时仍在候选里；执行过之后 Hunter 不再选它。

## 真实调用（本轮）

本轮再做最多 **40 次**真实调用，用来确认上面的改动在真模型上有效：

- 实现器：30 条规格各一次（用门槛里的规格，但 `F7/boundary` 按上面改），**新的缓存目录**（`.orch/tmp/llmcache2`），报告首次与最终通过率、按类别的数字。
- 猜想者：DF-A 一次（新的缓存目录），报告 `registered` 与否、预测条数、`output_tokens`。

## 验收

```powershell
cd framework
python -m pytest -q testing tests       # 只允许 test_constants_match_the_gate_table 失败（旧门槛），其余全过，skip 仍是 3
python -m surprise.gates.s09 --only isolation cache reject cap source implementer conjecturer   # 7/7
python -m surprise.gates.s08 --only no_llm     # 1/1
```

改完提交，在 `.orch/report.md` 末尾追加"第 1 轮返工"一节：改了什么、命令与输出末 20 行、真实调用的次数与结果。
