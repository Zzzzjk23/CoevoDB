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
