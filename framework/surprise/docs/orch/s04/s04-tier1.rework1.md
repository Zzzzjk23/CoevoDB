# 审查意见 · s04-tier1 · 第 1 轮返工

独立复跑：pytest 262 passed / 3 skipped；`gates/s04.py` 的五组本包门槛通过。重跑规则、`cve` 结构、写语句与跨库可比性两条前提、进程隔离、`evaluate_final`、manifest 环境字段都通过了门槛和编排者另做的探测，这些不要动。下面三处要改，另有两点流程上的事。

## 1. ASOF 并列键取错（必须改）

文件：`framework/surprise/harness/cve/premise.py`，`_qualified_columns` 与 `_parse_asof`。

现在把 ON 条件里所有带右表限定名的列都放进 GROUP BY。ON 里多一个只涉及右表的条件时，分组键多出一列，连接键上的并列就查不出来，前提被当成成立。

编排者实测（F3 的数据，`px` 在 `(id, ts)` 上有并列）：

```sql
SELECT r.p FROM ev l ASOF JOIN px r ON l.id = r.id AND l.ts >= r.ts AND r.p > 0 ORDER BY l.id, l.ts, r.p
```

原始 plan variant 判 fail，`certify` 的最终标签是 `fail / wrong_result`，前提 `violations` 为空。应为 `invalid / unspecified_semantics`。这是把一个依赖未指定选择的用例确认成了 bug。

改成：

- ON 条件按顶层 AND 拆成合取项。括号里、字符串里的 AND 不拆。顶层出现 OR：按解析不了处理。
- 一个合取项是连接键比较，当且仅当它是一个比较（`=`、`<`、`<=`、`>`、`>=`），其中一侧至少引用一个右表限定列且不引用别的限定列，另一侧至少引用一个限定列且都不是右表的。并列键取这些比较里的右表列。
- 任何其他形态的合取项，按解析不了处理，也就是违反前提。包括：只引用右表的条件（上面的 `r.p > 0`）、没有比较运算符的、引用了不带限定名的列的、两侧都混着两张表的。
- 方向只有一个：宁可多判 invalid，不可漏判。
- `_read_condition` 在括号深度变成负数时停下（ASOF 连接写在子查询里时，现在会越过子查询的右括号一直扫到语句末尾）。

测试要加：上面这条（有并列是 invalid；把并列行去掉、再用假 runner 造一个差异，不因这条前提 invalid 的那一侧可以是"按解析不了处理"，因为它含 `r.p > 0`）；ON 里含顶层 OR；ON 里有不带限定名的列；连接写在子查询里且右表有并列。原有的 ASOF 测试保持通过。

## 2. 子进程退出码为 0 但没有结果（必须改）

文件：`framework/surprise/harness/cve/isolate.py`，`call_worker`。

子进程正常退出码、标准输出里没有可解析的结果时，现在抛 `RuntimeError`，`execute_isolated` 会把它抛给调用方。说明要求引擎侧的失败不让调用方抛异常，没有交回结果就结束是 `crash`。

改成：这种情况同样返回 `crash`，`exit_code` 记实际的退出码（这里是 0）。`IsolatedResult.exit_code` 的含义相应是"crash 时子进程的退出码"。`certify` 里它走进程崩溃候选的同一条路。

测试要加：一个模块级假 runner 在标记语句上 `os._exit(0)`，`execute_isolated` 返回 `crash` 而不是抛异常。

## 3. `unattributed_crash` 的 tier（小改）

文件：`framework/surprise/harness/cve/certify.py`，`_from_crash`。

这个标签的 `cve["raw"]["y"]` 是 `fail`，`cve["tier"]` 却是 0。有候选就是第 1 档：改成 1，五步仍是 `skipped`、原因仍是 `unattributed_crash`。对应测试里的断言随之更新，这是随需求的更新。

## 4. 流程

- worktree 根的 `.venvs` 目录联接已由编排者删除，不要重建，也不要用别的办法把主检出区的目录接进 worktree。`python -m surprise.gates.s03` 的 `version` 组在这个 worktree 里会以 `FileNotFoundError` 失败：门槛文件把旧解释器的路径写成了相对 worktree 根，这是门槛自己的问题，与你的改动无关。原说明要求"s03 退出码 0"是编排者写错了。这一轮改跑 `python -m surprise.gates.s03 --only registry local cross matrix`。
- `.orch/tmp` 里的文件不要删，包括你自己建的。上一轮删了 `.orch/tmp/msg.txt`；提交信息用 `git commit -m`，或者把文件留在原地。

## 验收

在 worktree 里，`python` 与 `pytest` 用现成的：

```powershell
cd framework
python -m pytest -q testing tests                                                   # 不少于 262，skip 不多于 3
python -m surprise.gates.s01
python -m surprise.gates.s02
python -m surprise.gates.s03 --only registry local cross matrix
python -m surprise.gates.s04 --only contracts isolation tier1 premise environment
```

五条都是退出码 0。范围、禁区、报告格式仍以 `.orch/brief.md` 为准。改完提交到当前分支，更新 `.orch/report.md`（保留第一轮内容，在后面加"第 1 轮返工"一节）。
