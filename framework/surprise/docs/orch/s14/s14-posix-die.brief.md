角色：执行者

# 工作包 s14-posix-die：S4 测试夹具在 Linux 上按给定的退出码结束进程

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s14-posix-die`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s14`
- 所属会话：S14（服务器部署与双平台门槛），范围见 `framework/surprise/docs/SESSIONS.md` 的 S14 一节："平台差异逐条记录；需要改的代码交给 grok 在本机 worktree 里改，两个平台都要绿"
- 依赖：无

## 目标

`framework/tests/test_surprise_s04_runners.py` 的 `die(code)` 在 POSIX 上改为用 `os._exit(code)` 结束进程，使进程的退出码就是 `code`。Windows 分支（`TerminateProcess`）一个字节都不改。

只改这一个函数的 POSIX 分支和它附近必要的导入整理（`signal` 不再使用就删掉这个导入）；可以给函数加一段 docstring，说明为什么两个平台写法不同（见"背景"）。

## 背景

- 这个函数是 S5 加的（DECISIONS 2026-10-09 S5 一条）：Windows 上 `os._exit(77)` 退出时 DuckDB 的工作线程还在跑，约 0.5% 的子进程以访问冲突 0xC0000005 而不是 77 结束，所以 Windows 上改成 `TerminateProcess(当前进程, code)`，立即结束且退出码确定。当时 POSIX 分支写成了 `os.kill(os.getpid(), signal.SIGKILL)`。
- 在 Linux 上，SIGKILL 让进程的退出码恒为 -9，而不是 `code`。用这个夹具的两个测试断言了退出码：
  - `tests/test_surprise_s04_pipeline.py::test_execute_isolated_statuses_and_prelude` 断言 `ZeroExitRunner` 的子进程 `exit_code == 0`；
  - `tests/test_surprise_s04_pipeline.py::test_process_isolation_pass_crash_hang_and_reference` 断言 `ExitingRunner` 的子进程 `exit_code == 77`。
  
  在实验服务器（Ubuntu 24.04，Python 3.13.9）上这两个测试因此失败（实测得到 -9），Windows 上一直通过。harness 如实报告了 crash 与退出码，没有问题；错的是夹具在 POSIX 上没有按 `code` 结束。
- Linux 上 `os._exit` 走 `exit_group` 系统调用：立即结束所有线程，不跑 atexit、不析构、不卸载动态库，不会有 Windows 上那种卸载库时撞上工作线程的问题。所以 POSIX 上直接 `os._exit(code)` 就是"立即结束、退出码确定"。
- 门槛 `framework/surprise/gates/s04_fixtures.py` 里有同名同写法的函数，归编排者，不要改。

## 允许改动的路径

```allow-paths
framework/tests/test_surprise_s04_runners.py
```

## 禁止

- 不改测试的断言，不改 `tests/test_surprise_s04_pipeline.py`，不加 skip / xfail，不按平台跳过测试。
- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`framework/surprise/harness/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不登录、不连接任何远程服务器（不用 ssh、scp、rsync）。本包不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。

## 验收命令

在 worktree 里执行。`python` 已经指向项目解释器。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。这台机器是 Windows，所以你只能验证 Windows 分支没有变；Linux 上的验证由编排者在服务器上做。

```powershell
cd framework
python -m pytest -q tests/test_surprise_s04_pipeline.py      # 全部通过
python -m pytest -q testing tests                            # 935 passed, 3 skipped（与基线相同）
git diff session/s14 -- tests/test_surprise_s04_runners.py   # 贴进报告：只有 die() 的 POSIX 分支、导入与 docstring
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s14-posix-die

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
