角色：执行者

# 工作包 s16-testfix：两个旧测试跟上"PostgreSQL 是第三个目标引擎"

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-testfix`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（S16 的六个包都已合并：PostgreSQL 16.15 已是 harness 的第三个目标引擎）
- 所属会话：S16（PostgreSQL 目标），见 `framework/surprise/docs/SESSIONS.md`
- **用户的决定（2026-10-22，"全部照你的建议改"）**：`framework/tests/test_surprise_s03_registry.py` 里两个写死"目标只有 DuckDB 与 DataFusion"的测试，按下面的方式修改。这是本包唯一允许修改既有测试的地方，CLAUDE.md"执行者模式"里"不改基线测试"的规则对这两处由用户的决定放开，对其余一切照旧。

## 目标

只改 `framework/tests/test_surprise_s03_registry.py` 里的两个测试，别的测试、断言一个字符都不动：

1. `test_implemented_is_the_seven_plan_ids`：`assert TARGET_ENGINES == ("duckdb", "datafusion")` 改成 `assert TARGET_ENGINES == ("duckdb", "datafusion", "postgres")`。这个测试里的其余断言不动。
2. `test_sound_oracles_pass_on_both_target_engines`：现在遍历 `TARGET_ENGINES`，遇到 postgres 时没有 PG 实例（没配 `COEVO_TARGET_PG_DSN` 时 `runner_factory_for("postgres")` 按设计抛 `ValueError`）。改成只遍历两个嵌入式引擎 `("duckdb", "datafusion")`（写成测试里的显式元组，并加一行注释：PostgreSQL 的同类检查在 `tests/test_surprise_s16_target.py` / `test_surprise_s16_oracles.py` 与 S16 门槛里，要每个运行自己的实例）。循环体里的每条断言保持原样。函数名可以保留。

不要为了让 PG 也跑这个测试去起实例（那是 S16 新测试的事），也不要改 registry 或别的生产代码。

## 允许改动的路径

```allow-paths
framework/tests/test_surprise_s03_registry.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/` 与任何生产代码。
- 除上面两处之外不改任何测试：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。本包不需要任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行（用 `python -m pytest`；直接敲 `pytest` 在这台机器上可能找不到 `surprise` 包）。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。

```powershell
cd framework
python -m pytest -q tests/test_surprise_s03_registry.py   # 全部通过
python -m pytest -q testing tests                          # 全部通过（0 failed），skip 仍是 3
python -m surprise.gates.s03                               # PASS
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：改了哪些文件；跑了哪些命令（命令、退出码、输出最后 20 行原样）；与说明的偏差；未决问题。
3. 说明有矛盾或做不完：写进报告，停下。
