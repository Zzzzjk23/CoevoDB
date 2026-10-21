# 报告 · s16-replay

## 改了哪些文件

- `framework/surprise/metrics/replay.py`：新增两遍流式分层抽样、最大余数分配与每层至少一条约束、spawn 子进程回放、CVE/身份比较、ASCII JSON 报告及 CLI 退出码。
- `framework/tests/test_surprise_s16_replay.py`：新增 25 项测试，用关闭 LLM 的 DuckDB 主循环运行作素材，覆盖抽样、worker 一致性、复制账本后篡改检测、放宽规则、归属计数、CVE/身份字段、异常与路径格式。

提交：`8bf6292`，当前分支 `grok/s16-replay`。只提交上述两个允许的路径；本报告不入库。

## 跑了哪些命令

测试与 CLI 命令的工作目录为 `framework/`；git 命令在 worktree 根执行。以下保留验收及提交命令的原始输出；读取文件和定位实现的只读查询不列入验收记录。

### `pytest -q tests/test_surprise_s16_replay.py`

退出码：1。输出最后 20 行：

```text

=================================== ERRORS ====================================
_____________ ERROR collecting tests/test_surprise_s16_replay.py ______________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-replay\framework\tests\test_surprise_s16_replay.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_replay.py:17: in <module>
    from surprise.experiments.loop import run
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ============================
ERROR tests/test_surprise_s16_replay.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
```

### `$env:PYTHONPATH = (Get-Location).Path; pytest -q tests/test_surprise_s16_replay.py`

退出码：0。输出最后 20 行：

```text
.........................                                                [100%]
25 passed in 15.96s
```

### `$env:PYTHONPATH = (Get-Location).Path; pytest -q testing tests`

退出码：0。输出最后 20 行：

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 35%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 70%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 93%]
........................................................................ [ 99%]
.........                                                                [100%]
1230 passed, 3 skipped in 555.80s (0:09:15)
```

### `python -m surprise.metrics.replay --help`

退出码：0。输出最后 20 行：

```text
usage: replay.py [-h] --sample SAMPLE --seed SEED --out OUT
                 [--workers WORKERS]
                 run_dir

Stratified replay of an old ledger against the current frozen harness.

positional arguments:
  run_dir

options:
  -h, --help         show this help message and exit
  --sample SAMPLE
  --seed SEED
  --out OUT
  --workers WORKERS
```

### `git diff --cached --check`

退出码：0。无输出。

### `git commit -m "feat(metrics): add stratified harness replay and evidence checks"`

退出码：0。输出最后 20 行：

```text
[grok/s16-replay 8bf6292] feat(metrics): add stratified harness replay and evidence checks
 2 files changed, 488 insertions(+)
 create mode 100644 framework/surprise/metrics/replay.py
 create mode 100644 framework/tests/test_surprise_s16_replay.py
```

### `git status --short`

退出码：0。无输出，工作区干净。

## 与说明的偏差

功能与修改范围无偏差。首次直接运行 `pytest` 时，入口未将当前 `framework/` 加入模块搜索路径，收集阶段报 `ModuleNotFoundError: No module named 'surprise'`。后续只为测试进程设置 `PYTHONPATH` 为当前 `framework/`，继续使用说明指定的 `pytest` 和项目解释器；未修改 conftest、基线测试或环境安装。

边界输入约定：当 `--sample` 小于非空层数时，无法同时满足每层至少一条与固定总数，作为用法错误返回 2。最大余数并列按层键排序，保证可重复。

按说明未运行 `python -m surprise.gates.all`，也未连接实验服务器、修改冻结 harness 或结果产物、打 tag、合并、rebase、push 或切换分支。新增测试全部通过且无 skip/xfail；完整测试集为 1230 passed、3 skipped。

## 未决问题

无。本 worktree 缺少说明中列出的 S8 旧账本与门槛产物；现场旧账本回放及全部门槛由编排者合并后在主检出区运行。

