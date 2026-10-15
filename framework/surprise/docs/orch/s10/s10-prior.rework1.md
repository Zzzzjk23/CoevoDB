# 返工意见 · s10-prior · 第 1 轮

只改一处，其余都不动（实现与测试其余部分都已审过，没有问题）。

## 1. 回复里非字符串的 `unit` 会让整次运行崩掉

`framework/surprise/roles/prior.py` 的 `_ingest`：

```python
unit = item.get("unit")
if unit not in batch_set or unit in seen:
```

模型的回复是不可信的输入。`unit` 是列表或字典时（例如 `{"unit": ["a"], "p_fail": 0.1}`），`unit not in batch_set` 抛 `TypeError: unhashable type`，异常一路冒到主循环，整次 run 以 error 结束。

改成：`unit` 不是 `str` 就跳过这一项（与"没问过的单元"同样处理：不定价，问过的单元照旧记 `unpriced`）。

## 2. 测试

在 `framework/tests/test_surprise_s10_prior.py` 里加一条：回复里同时有一个 `unit` 为列表、一个为字典、一个为数字的项，再加一个合法项；断言不抛异常、合法项定上价、其余问过的单元记 `unpriced`。已有测试一条都不改。

## 3. 不要动的

- 不改别的文件；不改已有测试。
- `tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on` 在你的 worktree 里仍会失败（它假定四个角色模块都不存在）：这是预期的，编排者另派了一个包修它。不要碰这个文件，在报告里注明即可。

## 验收命令

```powershell
cd framework
python -m pytest -q tests/test_surprise_s10_prior.py
python -m pytest -q testing tests       # 只允许上面那一条 frame 测试失败
python -m surprise.gates.s10 --only constants frozen library frame prior    # 5/5
```

完成后提交，并更新 `.orch/report.md`（追加"第 1 轮返工"一节：改了什么、命令与输出末 20 行）。
