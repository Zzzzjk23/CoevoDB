# 报告 · s15-archive

## 改了哪些文件
- `framework/surprise/experiments/archive.py`：新增标准库归档 CLI，实现 gzip tar 打包、SHA-256 清单与流式校验、校验后精简；拒绝覆盖已有输出、链接、特殊文件、异常归档成员，并统计删除的文件数和字节数。
- `framework/tests/test_surprise_s15_archive.py`：新增 27 项测试，覆盖清单与成员顺序、逐文件解包还原、损坏/篡改/异常成员、校验失败不删除、精确保留摘要与报告、重复精简、覆盖与内部目标拒绝、条件式符号链接检查、分块读取、写入失败清理及 CLI 退出码。

提交：`5381600`（`grok/s15-archive`）。仅提交上述两个获准文件，工作区干净。本报告位于忽略目录，未入库。

## 跑了哪些命令

Python 验收命令均在 `framework/` 执行，使用已配置的 `python`；Git 命令在 worktree 根执行。临时目录由现有环境指向本 worktree 的 `.orch/tmp`，未清理该目录。以下逐项保留命令的退出码和输出末 20 行（不足 20 行则全部保留）。

### 基线（修改前）

命令：`python -m pytest -q testing tests`

退出码：`0`

```text
........................ss..................................s........... [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 75%]
........................................................................ [ 82%]
........................................................................ [ 90%]
........................................................................ [ 97%]
........................                                                 [100%]
957 passed, 3 skipped in 286.40s (0:04:46)
```

### 归档专项测试

命令：`python -m pytest -q tests/test_surprise_s15_archive.py`

退出码：`0`

```text
...........................                                              [100%]
27 passed in 5.58s
```

### 完整回归（修改后）

命令：`python -m pytest -q testing tests`

退出码：`0`

```text
........................ss..................................s........... [  7%]
........................................................................ [ 14%]
........................................................................ [ 21%]
........................................................................ [ 29%]
........................................................................ [ 36%]
........................................................................ [ 43%]
........................................................................ [ 51%]
........................................................................ [ 58%]
........................................................................ [ 65%]
........................................................................ [ 72%]
........................................................................ [ 80%]
........................................................................ [ 87%]
........................................................................ [ 94%]
...................................................                      [100%]
984 passed, 3 skipped in 281.38s (0:04:41)
```

### 归档门槛

命令：`python -m surprise.gates.s15 --only archive`

退出码：`0`

```text
a/s1-r0 done
b/s1-r0 done
a/s2-r0 done
b/s2-r0 done
[PASS] archive: 30 files packed and verified; corruption detected; prune refuses a mismatch and keeps the summaries (1s)
S15 GATE [only: archive]: PASS (1/1 groups passed)
```

### CLI 帮助

命令：`python -m surprise.experiments.archive --help`

退出码：`0`

```text
usage: archive.py [-h] {pack,verify,prune} ...

Pack, verify or prune an experiment grid

positional arguments:
  {pack,verify,prune}
    pack               archive an entire grid with a SHA-256 manifest
    verify             verify an archive and optionally the local grid
    prune              verify, then retain only reports and summaries

options:
  -h, --help           show this help message and exit
```

### 暂存改动空白检查

命令：`git diff --cached --check`

退出码：`0`

输出为空。

### 提交

命令：`git commit -m "feat(s15): add verified grid archive and pruning commands"`

退出码：`0`

```text
[grok/s15-archive 5381600] feat(s15): add verified grid archive and pruning commands
 2 files changed, 591 insertions(+)
 create mode 100644 framework/surprise/experiments/archive.py
 create mode 100644 framework/tests/test_surprise_s15_archive.py
```

### 最终状态

命令：`git status --short --branch; git log -1 --format="%h %s"; git show --format= --name-only HEAD`

退出码：`0`

```text
## grok/s15-archive
5381600 feat(s15): add verified grid archive and pruning commands
framework/surprise/experiments/archive.py
framework/tests/test_surprise_s15_archive.py
```

基线：957 passed、3 skipped。最终：984 passed、3 skipped，增加 27 个通过用例，跳过数量未变；本工作包未新增 skip/xfail。归档专项测试耗时 5.58 秒，低于 1 分钟；S15 archive 组 PASS（1/1）。

## 与说明的偏差
无。

## 未决问题
无。

