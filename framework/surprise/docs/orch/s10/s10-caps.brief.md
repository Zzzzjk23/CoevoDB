角色：执行者

# 工作包 s10-caps：三个角色的 token 上限从 8000 提到 16000

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-caps`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（六个角色都已合并，门槛表 `gates/s10_cases.py` 已经改好）
- 所属会话：S10，范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节

## 问题与目标

编排者用真实调用录 M3 时，迁移翻译者与 oracle 发明者的回复在 `max_tokens=8000` 处被截断，没有 JSON，被网关拒收（`deepseek-flash` 把推理 token 算进 `max_tokens`；S9 的猜想者因此用 16000）。门槛表 `framework/surprise/gates/s10_cases.py` 的 `CONSTANTS` 已经改成：

- `TRANSLATOR_MAX_TOKENS = 16000`
- `VOCAB_MAX_TOKENS = 16000`
- `ORACLE_MAX_TOKENS = 16000`

（`PRIOR_MAX_TOKENS` 仍是 8000；S9 的常数一个都不变。）

把 `framework/surprise/roles/constants.py` 里这三个常数改成上面的值，注释里加一句原因（英文，一行）。别的一个字都不改。

## 允许改动的路径

```allow-paths
framework/surprise/roles/constants.py
```

## 禁止

- 不改任何别的文件（包括测试：测试按常数名引用，不用改；门槛表已经改好）。
- 不做任何 LLM 调用。
- 不靠改测试让测试通过；不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器。shell 是 Windows PowerShell 5.1（没有 `&&`，用 `;`）。

```powershell
cd framework
python -m pytest -q testing tests                 # 全部通过，skip 仍是 3
python -m surprise.gates.s10 --only constants      # 通过
python -m surprise.gates.s09 --only constants      # 通过（S9 常数不变）
```

## 收尾

1. 提交到当前分支；`git status` 干净。
2. 写 `.orch/report.md`（不入库），格式：

```markdown
# 报告 · s10-caps

## 改了哪些文件
## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴）。
## 与说明的偏差
## 未决问题
```
