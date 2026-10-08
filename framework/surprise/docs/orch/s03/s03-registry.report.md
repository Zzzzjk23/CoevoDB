# 报告 · s03-registry（第1轮返工）

## 改了哪些文件
- `framework/tests/test_surprise_s03_registry.py`：`test_missing_later_module_is_not_a_pass` 与 `test_evaluate_accounts_datafusion_and_missing_handler` 改为用 pytest `monkeypatch` 复制 `_HANDLERS` / `_LAZY_MODULES`。先在复制表里塞假的 pass handler，再从复制的 handler 表去掉 later ID，把 lazy 模块改成 `surprise.harness.oracles._s03_registry_absent_*`。退出时 monkeypatch 恢复。ImportError、evaluate 的 `invalid/harness_error`、LIMIT 的 `nondeterministic` 断言全部保留。

实现代码未改。未创建后三包文件。

提交：`a7cce8b`（`grok/s03-registry`；其上为 `c9c4da5`）

## 跑了哪些命令

命令：`python -m pytest -q testing tests`（在 `framework/`）
退出码：0

```
........................ss..................................s........... [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
165 passed, 3 skipped in 6.59s
```

命令：`python -m surprise.gates.s03 --only registry`（在 `framework/`）
退出码：0

```
[PASS] registry: 3 existing oracles x 2 engines pass; registry and invalid sources checked
S03 GATE: PASS (1/1 groups passed)
```

命令：`python -m surprise.gates.s02`（在 `framework/`）
退出码：0

```
[PASS] contracts: 10 objects round-trip, 10 invalid ones rejected
[PASS] ledger: 5 records in 2 runs: written, filtered, reopened; 4 bad writes rejected
[PASS] manifest: 32 files hashed (567be298985e); verify catches 3 kinds of change
[PASS] oracles: 60 judgements stable and as expected (6 fail, 35 invalid); crash, error mismatch and timeout paths ok
[PASS] evaluate: 11 executions, 11 ledger records (4 pass, 3 fail, 4 invalid)
S02 GATE: PASS (5/5 groups passed)
```

## 与说明的偏差
无。审查要求只修测试长期有效性：缺模块路径不再依赖仓库里 later 文件是否存在；假 pass handler 被隔离后仍走 ImportError，不伪装成通过。

## 未决问题
- S3 的 local / cross / version / matrix 门槛组此时缺后续包，预期红，本包未改门槛。
