# 返工意见 · s02-oracles · 第 1 轮

整体通过了审查：范围、复跑、读过的全部代码都没有问题，另外用种子语料做了 588 组（用例 × oracle）的差分核对，和旧 oracle 的结论零出入。只有一处要改，而且根子在任务说明漏写了，不是你理解错了。

## 要改什么

`framework/surprise/harness/evaluate.py` 的 `evaluate()`：

现在 `purpose`、`p_t`、`spec`、`phi`、`theory_version` 是在 `judge` 跑完之后、构造 `ExperimentRecord` 时才被校验的。参数不合法时（比如 `purpose=""`、`p_t=1.5`、`spec` 里有不能转成 JSON 的值），用例已经执行过了，接着抛 `ValueError`，账本里却没有这次执行的记录。这违背了"每次执行都留账"。

改成：**凡是会让记录构造失败的参数，都要在执行任何东西之前拒绝掉**。也就是在调用 `judge` 之前，这些参数就已经按 `ExperimentRecord` 的规则校验过；不合法就抛 `ValueError`，此时 `runner_factory` 一次都没被调用过，账本里也没有新记录。

建议的做法（不强制）：在 `judge` 之前先用一个占位的 pass 标签把 `ExperimentRecord` 构造一遍，让它自己的校验把不合法的参数挡下来；`judge` 之后再用真实的标签构造要写入的那一条。这样校验规则只有契约里那一份，不用在 `evaluate` 里重写。

原有的三项检查（`oracle`、引擎、`run_id`）保持在最前面，行为不变。

## 测试

在 `framework/tests/test_surprise_evaluate.py` 里加用例：上面三种不合法的参数各一例，断言抛 `ValueError`、计数用的 `runner_factory` 调用次数为 0、`ledger.count()` 不变。

## 不要动

- `framework/surprise/harness/oracles/` 下的文件和 `framework/tests/test_surprise_oracles.py`：都没有问题，不要改。
- 其余和任务说明一样：不改门槛、文档、旧代码，不清理 `.orch/tmp`。

## 验收

和任务说明里的一组命令相同：

```powershell
cd framework
python -m pytest -q testing tests
python -m surprise.gates.s02 --only contracts ledger oracles evaluate
python -m surprise.gates.s01
cd ..
git status --short
```

说明一点：编排者已经在会话分支上给门槛的 evaluate 组补了这项检查（用一个计数的 `runner_factory`，传 `purpose=""`、`p_t=1.5`、`spec={"weights": {1, 2}}` 三组参数，要求抛 `ValueError`、没有 runner 被打开、账本没有新记录）。你 worktree 里的门槛文件还是旧的，跑不到这一项，这是正常的；合并之后编排者会用新门槛复核。

改完提交到当前分支，更新 `.orch/report.md`（在原报告后面加一节"第 1 轮返工"，写改了什么、跑了哪些命令及输出）。
