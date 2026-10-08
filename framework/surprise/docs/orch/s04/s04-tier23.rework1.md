# 审查意见 · s04-tier23 · 第 1 轮返工

独立复跑：S04 八组门槛通过；pytest 272 passed、1 failed、3 skipped，失败的就是你在"未决问题"里报告的那一条。你没有去改允许路径之外的测试、而是停下报告，做得对：那是编排者在说明里漏掉的。

门槛之外的探测也都通过了：十二组假设的归属结果与预期一致；九个确认用例最小化后的用例拿去做原始判定仍是同一类 fail；进程隔离下第 2、3 档调用方进程执行的语句数为 0；两次判定完全相同；不构造 agent 和 HTTP 客户端；会杀进程的候选进第 3 档不挂起。归属测试、最小化的两段、画像各字段、降级规则都不要动。

下面四处要改。这是冻结前最后一次改 harness，改动控制在这四处之内。

## 1. 常数快照的断言（编排者漏放的路径）

文件：`framework/tests/test_surprise_contracts.py`，`test_constants_collect_public_uppercase_names`。

本轮允许改这一处，别的不动：期望集合加上 `CVE_MINIMIZE_MAX_EXECUTIONS`、`CVE_BISECT_MAX_EXECUTIONS`、`CVE_ATTRIBUTION_WALL_TIMEOUT_S`、`CVE_PROFILE_WALL_TIMEOUT_S`，仍然是精确集合；照已有三个 `CVE_` 常数的写法各加一句取值断言。

## 2. 第 1 档被拒之后的跳过原因写错了

文件：`framework/surprise/harness/cve/certify.py`。

候选在第 1 档被降级（前提不成立、重跑不稳定、`unattributed_crash`）时，`attribution`、`minimize`、`profile` 现在记的原因是 `"not_requested"`，即使调用方给了 `hypothesis` 或 `diagnose=True`。`Label.cve` 要如实记各档跳过的原因。

改成：

- 调用方给了 `hypothesis`、而候选在第 1 档被降级：`attribution` 的原因记 `"tier1_rejected"`。
- 调用方要求了第 3 档（`diagnose=True`，或给了 `hypothesis`）、而候选在第 1 档被降级：`minimize`、`profile` 的原因记 `"tier1_rejected"`。
- 调用方没有要求的，仍是 `"not_requested"`。原始判定不是候选的，仍是 `"not_a_candidate"`。`harness_error`、`timeout` 两种标签不变。

你自己的测试里断言了旧原因的地方（`test_tier1_downgrade_does_not_run_tier3` 等）随之更新。

## 3. 干预名单问了两遍

文件：`framework/surprise/harness/cve/certify.py`（`prepare_hypothesis`、`_intervention_names`），`framework/surprise/harness/evaluate.py`。

带 `hypothesis` 调一次 `evaluate_final`，现在要为"这个引擎有哪些干预名"起两个子进程：`evaluate_final` 校验一次，`certify` 又校验一次。S6 之后每个落在已有假设里的实验都走这条路。

改成：名单按引擎在调用方进程里缓存。只在 `runner_factory` 为 `None`（用引擎默认工厂）时缓存；给了自定义工厂时照旧每次去问，因为假 runner 可以有自己的名单。缓存的是子进程返回的名单，调用方进程仍然不执行目标 SQL。

测试要加：默认工厂下连续两次带假设的 `certify`，`interventions` 这个 op 只发给子进程一次（可以包一层 `call_worker` 来数）。

## 4. 最小化之后的再验证改用原始判定

文件：`framework/surprise/harness/cve/tier3.py`，`diagnose_case` 里 `still = checker.reproduces(...)` 那一步。

现在最小化结束后的再验证用的还是"两种形式不一致"这条判据。它对 plan variant 把"一侧成功、一侧报值依赖错误或超时"也算不一致，所以理论上可以把用例缩成另一种现象（比如原来是结果不同，缩完变成一侧溢出报错），再验证照样通过，画像就建在了错的现象上。

改成：最小化结束后（无论删没删东西），对最小化后的用例做一次原始判定（`session.run_judge`，同样的 oracle 与 options，不带 prelude）。标签是 `fail` 且 `fail_kind` 与候选相同才算复现，`minimize.reproduced` 记这个结果；否则按现有路径记 `not_reproduced_minimized`。最小化过程中、二分过程中的判据不变。

测试要加：一个假 runner，完整数据下两种形式结果不同；数据被删掉之后，一侧改为报值依赖错误（错误文本里带 `overflow` 即可）而另一侧成功。期望最终标签 `invalid / not_reproduced_minimized`，`profile` 为 `skipped`。原有的"最小化途中丢失"测试保持通过。

## 流程

- `.orch/tmp` 里的文件不要删；不建指向 worktree 之外的链接。这一轮你都做到了，保持。

## 验收

在 worktree 里，`python` 与 `pytest` 用现成的：

```powershell
cd framework
python -m pytest -q testing tests                                                   # 0 failed，不少于 273 passed，skip 不多于 3
python -m surprise.gates.s01
python -m surprise.gates.s02
python -m surprise.gates.s03
python -m surprise.gates.s04 --only contracts isolation tier1 premise environment tier2 tier3 m1
```

五条都是退出码 0。范围、禁区、报告格式仍以 `.orch/brief.md` 为准，本轮额外允许改 `framework/tests/test_surprise_contracts.py` 里第 1 条写明的那一处。改完提交到当前分支，更新 `.orch/report.md`（保留第一轮内容，在后面加"第 1 轮返工"一节）。
