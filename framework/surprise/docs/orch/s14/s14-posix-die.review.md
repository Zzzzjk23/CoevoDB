# 审查包 · s14-posix-die

- 生成时间：2026-10-19T03:21:31+11:00
- 基线：`session/s14`（71c020b41f09）
- 分支：`grok/s14-posix-die` @ 8b9a14b05cf4，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 6m40s
- grok：grok 1.0.46 (2765805b9442)；会话 `6454f0de-1ba0-49ed-8c3c-542839fa8998`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s14..grok/s14-posix-die
git diff -M --stat session/s14..grok/s14-posix-die
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/tests/test_surprise_s04_runners.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/tests/test_surprise_s04_runners.py` |  |

提交：

- 8b9a14b Junke: test(s14): POSIX die() uses os._exit so the wait status is code

## 2. diff 统计

```text
 framework/tests/test_surprise_s04_runners.py | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)
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
- 日志 `.orch/logs/s14-posix-die.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 无

主检出区当前未提交的改动（`git status --porcelain`）：

```text
 M framework/surprise/docs/HANDOFF.md
 M framework/surprise/docs/SERVER.md
```

## 6. 执行日志摘要

`.orch/logs/s14-posix-die.jsonl`：775 条事件（available_commands 22，end 1，orch.exit 1，orch.start 1，text 330，thought 47，tool_call 17，tool_call_update 345，usage 11）；各轮合计 11 个模型回合，grok 上报花费 0.0827 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
tool_update [in_progress]: [grok/s14-posix-die 8b9a14b] test(s14): POSIX die() uses os._exit so the wait status is code 1 file changed, 10 insertions(+), 2 deletions(-)
tool_update [completed]: exit: 0 [grok/s14-posix-die 8b9a14b] test(s14): POSIX die() uses os._exit so the wait status is code 1 file changed, 10 insertions(+), 2 deletions(-) On branch grok/s14-posix-die …
thought: 提交已成功。接下来继续完成工作包。 正在编写 `.orch/report.md`，逐条提取各命令的输出内容。 已提取命令2的全部输出（935 passed, 3 skipped）。正在处理命令3的 git diff。 正在重新运行 git diff 以获取提交后的精确输出。同时准备记录提交后的 git status。 已确认 git diff 的输出无需重…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s14-posix-die\\.orch\\report.md", "content": "# 报告 · s14-posix-die\n\n## 改了哪些文件\n- `framework/tests/test_surprise_s04_runners.py`：修改。POSIX …
tool_call run_terminal_command: {"command": "Remove-Item \".orch\\tmp\\msg.txt\"", "description": "Delete scratch commit message file"}
tool_update [in_progress]: 
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s14-posix-die\n\n## 改了哪些文件\n- `framework/tests/test_surprise_s04_runners.py`：修改。POSIX `die(code)…
tool_update [completed]: exit: 0
thought: 工作包已按 .orch/brief.md 的说明完成。
text: 工作包 `s14-posix-die` 已完成，提交在 `grok/s14-posix-die`（`8b9a14b`）。 改动只在 `framework/tests/test_surprise_s04_runners.py`： - POSIX `die(code)` 改为 `os._exit(code)` - 删除未再使用的 `signal` 导入 - 给…
end: stopReason=end_turn turns=11 cost_usd=0.08272608
orch.exit: {"pkg": "s14-posix-die", "run": 1, "at": "2026-10-19T03:21:02+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s14-posix-die

## 改了哪些文件
- `framework/tests/test_surprise_s04_runners.py`：修改。POSIX `die(code)` 从 `os.kill(..., SIGKILL)` 改为 `os._exit(code)`；删除未再使用的 `signal` 导入；给 `die()` 加 docstring。Windows `TerminateProcess` 分支未改。

## 跑了哪些命令

### `cd framework; python -m pytest -q tests/test_surprise_s04_pipeline.py`
退出码：0

```
................                                                         [100%]
16 passed in 16.20s
```

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 30%]
........................................................................ [ 38%]
........................................................................ [ 46%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 92%]
........................................................................ [ 99%]
..                                                                       [100%]
935 passed, 3 skipped in 265.09s (0:04:25)
```

### `cd framework; git diff session/s14 -- tests/test_surprise_s04_runners.py`
退出码：0

```
diff --git a/framework/tests/test_surprise_s04_runners.py b/framework/tests/test_surprise_s04_runners.py
index 666ef2d..ac7ce41 100644
--- a/framework/tests/test_surprise_s04_runners.py
+++ b/framework/tests/test_surprise_s04_runners.py
@@ -8,7 +8,6 @@ from __future__ import annotations
 
 import ctypes
 import os
-import signal
 import time
 from typing import Any
 
@@ -22,6 +21,15 @@ EXIT_CODE = 77
 
 
 def die(code: int) -> None:
+    """End the process immediately with exit code ``code``.
+
+    Windows uses ``TerminateProcess`` because ``os._exit`` can race DuckDB
+    worker threads; about 0.5% of those children then exit with access
+    violation 0xC0000005 instead of ``code``. POSIX uses ``os._exit``, which
+    is ``exit_group``: every thread stops at once, without atexit, destructors,
+    or unloading libraries, so the wait status is ``code``. SIGKILL would
+    make the wait status -9 on Linux regardless of ``code``.
+    """
     if os.name == "nt":
         kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
         kernel32.GetCurrentProcess.restype = ctypes.c_void_p
@@ -29,7 +37,7 @@ def die(code: int) -> None:
         kernel32.TerminateProcess.restype = ctypes.c_int
         kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
     else:
-        os.kill(os.getpid(), signal.SIGKILL)
+        os._exit(code)
     os._exit(code)
 
 
```

### `git add framework/tests/test_surprise_s04_runners.py; git commit -F ".orch/tmp/msg.txt"; git status`
退出码：0

```
[grok/s14-posix-die 8b9a14b] test(s14): POSIX die() uses os._exit so the wait status is code
 1 file changed, 10 insertions(+), 2 deletions(-)
On branch grok/s14-posix-die
nothing to commit, working tree clean
```

## 与说明的偏差
无。

## 未决问题
无。Linux 上 `exit_code == 0` / `exit_code == 77` 的验证由编排者在服务器上做。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

## 编排者结论（2026-10-19）

合并。diff 只有 `die()` 的 POSIX 分支（`os.kill(SIGKILL)` → `os._exit(code)`）、删掉不再用的 `signal` 导入、一段 docstring；Windows 分支逐字未动，没有改任何断言。轻量审查（`--skip-tests`）：执行者在 worktree 里跑了全量 pytest（935 passed, 3 skipped）；编排者合并后在会话分支上复跑 Windows，并部署到服务器上复跑 Linux（这个包要修的就是 Linux 上那两个测试，本机验证不了）。日志里没有疑似密钥，没有被 deny 拦下的调用。
