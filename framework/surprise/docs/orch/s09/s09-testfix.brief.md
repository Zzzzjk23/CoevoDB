角色：执行者

# 工作包 s09-testfix：让一条测试不依赖执行次序

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s09-testfix`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s09`（`s09-gateway`、`s09-wire`、`s09-roles` 都已合并）
- 所属会话：S9

## 问题

`framework/tests/test_surprise_s09_wire.py` 的 `test_roles_off_matches_s8_files`（第 409 行起）断言 `"surprise.roles.runtime" not in sys.modules`，用来证明"角色全关时主循环不导入角色"。单独跑它通过；全量跑时，排在它前面的 `tests/test_surprise_roles_runtime.py` 已经在同一进程里导入了 `surprise.roles.runtime`，它就失败：

```powershell
cd framework
python -m pytest -q tests/test_surprise_roles_runtime.py tests/test_surprise_s09_wire.py -k "roles_off_matches or runtime"   # 1 failed
```

断言的意图是对的，错在它看的是整个进程的状态。

## 要改的

只改这个测试函数：在跑短 run 之前，用 `monkeypatch.delitem(sys.modules, name, raising=False)` 把当前 `sys.modules` 里所有 `surprise.roles` 与 `surprise.roles.*` 的模块都拿掉（monkeypatch 会在测试结束后放回去，不影响别的测试）；跑完之后断言 `sys.modules` 里没有任何 `surprise.roles` 或 `surprise.roles.*` 的模块（比原来只查 `runtime` 一个更严）。函数里其余断言一字不改。不改别的测试、别的文件。

## 允许改动的路径

```allow-paths
framework/tests/test_surprise_s09_wire.py
```

## 禁止

- 不改 `framework/surprise/` 下的任何文件（包括 `gates/`、`docs/`），不改 `CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不靠改测试让测试通过的那些做法（skip / xfail、删断言、放宽断言、宽泛的 try/except、改 conftest）一律不许；本包是把一条断言改得更严、并去掉它对执行次序的依赖。
- 不调用任何 LLM；不打 tag，不合并，不 rebase，不 push，不切换或删除分支；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不要清理 `.orch/tmp`；临时文件只放 pytest 的 `tmp_path`。

## 验收命令

`python` 和 `pytest` 已经指向项目解释器。PowerShell 5.1：没有 `&&`，用 `;`。

```powershell
cd framework
python -m pytest -q tests/test_surprise_roles_runtime.py tests/test_surprise_s09_wire.py   # 全过
python -m pytest -q testing tests       # 全过（不少于 692 passed），skip 仍是 3
```

## 收尾

1. 提交到当前分支；`git status` 干净。
2. 写 `.orch/report.md`（不入库）：改了哪些文件、跑了哪些命令及输出末 20 行、与说明的偏差、未决问题。
