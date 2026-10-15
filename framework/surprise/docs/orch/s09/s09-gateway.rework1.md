# 审查意见 · s09-gateway · 第 1 轮返工

实现照说明写得很好：网关、缓存、解析、读源码工具与传输都核对过，门槛之外的探测（目录联接逃逸、密钥不进报错、缓存不留临时文件、非 ASCII 往返）也都通过。这一轮只改两处，都不是你的错：

1. **模型名变了。** 编排者在你派发之后用 `GET /models` 核对了 DeepSeek 的模型列表，现在只有 `deepseek-flash` 与 `deepseek-v4-pro`。门槛已经改了：`framework/surprise/gates/s09_cases.py` 的 `TIERS` 现在是 `{"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}`（主检出区 `session/s09` 的提交 a2c5cc7；你的 worktree 里的门槛还是旧的，以本意见为准）。
   - `framework/surprise/roles/constants.py`：`TIERS = {"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}`。
   - `framework/tests/test_surprise_roles_gateway.py` 第 105 行 `assert constants.TIERS["fast"] == "deepseek-chat"` 改成 `"deepseek-flash"`；文件里其余写死旧模型名的地方（若有）同样只改字符串。
   - 你的 worktree 里的 `gates/s09_cases.py` 不要改（禁区）。所以改完之后，在你的 worktree 里 `python -m surprise.gates.s09 --only constants` 会因为门槛还是旧值而失败，`test_constants_match_the_gate_table` 也会因为比较对象是旧门槛而失败。**这两处失败是预期的**，在报告里写明即可；不要为了让它们通过去动门槛或放宽测试。
2. **`IMPLEMENTER_PER_CHOICE` 的注释写错了含义。** 它不是"每次尝试要几个补全"，而是"Hunter 每做一次选择，实现器来源最多为几个新目标调用实现器"。把注释改成：`# New targets the implementer source may implement per Hunter choice.` 取值不变。

不要动别的文件、别的行。改完提交，更新 `.orch/report.md`（追加"第 1 轮返工"一节：改了什么、重跑了哪些命令及输出末 20 行）。

验收：

```powershell
cd framework
python -m pytest -q tests/test_surprise_roles_gateway.py tests/test_surprise_roles_source.py   # 只允许 test_constants_match_the_gate_table 失败（原因如上）
python -m surprise.gates.s09 --only cache cap source      # 3/3
```
