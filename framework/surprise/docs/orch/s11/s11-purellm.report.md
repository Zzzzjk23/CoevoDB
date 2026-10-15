# 报告 · s11-purellm

提交 `92bec5b`，分支 `grok/s11-purellm`。工作区干净。

## 改了哪些文件
- `framework/surprise/baselines/pure_llm.py`：新增。纯 LLM 对照组，模型写 SQL，同一套 oracle 与 CVE 打标签。
- `framework/tests/test_surprise_s11_pure_llm.py`：新增。覆盖门槛 `pure_llm_script` 的要点，以及离线缓存缺失、`max_minutes`、用法错误。

## 跑了哪些命令

### `cd framework ; python -m pytest -q tests/test_surprise_s11_pure_llm.py --tb=line`
退出码 0。

```
..............                                                           [100%]
14 passed in 13.75s
EXIT:0
```

### `cd framework ; python -m pytest -q testing tests`
退出码 0。

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 45%]
........................................................................ [ 54%]
........................................................................ [ 63%]
........................................................................ [ 72%]
........................................................................ [ 81%]
........................................................................ [ 91%]
.......................................................................  [100%]
788 passed, 3 skipped in 192.76s (0:03:12)
```

### `cd framework ; python -m surprise.gates.s11 --only pure_llm_script`
退出码 0。

```
[PASS] pure_llm_script: 4 cases executed from 3 calls (1 reply rejected, 2 bad cases skipped); prompts deterministic; budget holds (5s)
S11 GATE [only: pure_llm_script]: PASS (1/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s11 --only constants`
退出码 1。预期失败。失败行：

```
[FAIL] constants: ModuleNotFoundError: No module named 'surprise.metrics.constants'
S11 GATE [only: constants]: FAIL (0/1 groups passed)
```

### `cd framework ; python -m surprise.gates.s11 --only pure_llm`
退出码 1。预期失败。失败行：

```
[FAIL] pure_llm: gates/s11_llm/pure_llm is missing: the orchestrator records it with real calls after the merge
S11 GATE [only: pure_llm]: FAIL (0/1 groups passed)
```

## 与说明的偏差
- `llm/pure_llm.jsonl` 不记录使运行停下的那一次 `blocked` 或 `miss`。说明把这两种状态列进了该行的 `status`。门槛 `pure_llm_script` 要求这个文件的 status 恰好是 `ok`、`rejected`、`ok`。停下来的那一次在 `llm/calls.jsonl` 里，`report["status"]` 为 `llm_exhausted`，`report["calls"]` 把它算进去。影响：合并后若有人按说明去对 jsonl 的最后一行，会看不到这次拒绝；网关账本里有。
- 引擎名不是 `duckdb` 或 `datafusion` 时，`run` 在建目录之前抛 `UsageError`。harness 只有这两个目标引擎。影响：命令行传入别的名字得到退出码 2，而不是跑起来再失败。
- 命令行在运行中抛出异常时退出码 1，键盘中断时 130，与 `experiments/loop.py` 相同。说明只点名了正常 0 和用法错误 2。
- `status` 为 `error` 时，`report.json` 在说明列出的字段之外多一个 `error` 对象（`type`、`message`）。traceback 在 `error.txt`。
- `max_minutes` 用 `>=` 与已用墙钟比较，与 loop 相同。预算为 0 时在第一次模型调用之前停下。

## 未决问题
- `constants` 组在导入 `surprise.metrics.constants` 时就失败，没有执行到 `REQUEST_DEADLINE_S`。该名字目前也不在 `roles/constants.py` 里，属于并行的 `s11-fixes`。本包没有改这些文件。
- `pure_llm` 组缺少 `gates/s11_llm/pure_llm` 的真实调用录制。按说明由编排者在合并后录。本包的离线重放测试用的是测试自己写下的缓存。
