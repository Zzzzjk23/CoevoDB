# 报告 · s16-sqlancer

提交：`47029d9 Add PostgreSQL support to the SQLancer baseline`。当前分支 `grok/s16-sqlancer`，工作区干净。

## 改了哪些文件

- `framework/surprise/baselines/sqlancer_run.py`（修改）：支持 PostgreSQL 运行与回放；在 `pg_instance.ensure(out/pg, old=True)` 中创建入口库、构建 manifest、认证用例；记录两个 PG 版本及 PG JDBC；隐藏命令、stdout 和异常中的口令；按引擎解析日志并只移除 PG 切库/建库操作。
- `framework/tests/test_surprise_s16_sqlancer.py`（新增）：14 项测试，覆盖分类、换行、PG 方言和谓词边界、setup 保留、CLI 回放与认证、真实 PG SQLancer 实跑、入口库创建/已存在、口令隐藏、异常清理及 DuckDB 快照。
- `framework/tests/data/s16/duckdb_sqlancer_before.json`（新增）：修改前七份 DuckDB 日志的完整解析结果快照。
- `framework/tests/data/s16/sqlancer/pg_norec_mismatch.log`（新增）：PG NoREC 样例，源自编排者的 S16 门槛样例。
- `framework/tests/data/s16/sqlancer/pg_tlp_mismatch.log`（新增）：PG TLP 样例，源自编排者的 S16 门槛样例。
- `framework/tests/data/s16/sqlancer/pg_unexpected_error.log`（新增）：PG unexpected error 样例，源自编排者的 S16 门槛样例。
- `framework/tests/data/s16/sqlancer/pg_tool_error.log`（新增）：按 SQLancer PG 格式手写的最小 tool error 样例。

## 跑了哪些命令

以下测试和门槛均从 `framework/` 执行。完整输出保存在本 worktree 的 `.orch/check-*.txt`（不入库）；每条下方列退出码和原始输出末 20 行。

`python -m pytest -q testing tests`

Exit code: `1`

```text
            from targets.datafusion_runner import DataFusionRunner
    
            return DataFusionRunner
        if engine == "postgres":
            import os
    
            from surprise.harness.oracles.pg_target import PostgresTargetRunner, TARGET_DSN_ENV
    
            if not os.environ.get(TARGET_DSN_ENV):
>               raise ValueError(
                    f"postgres: set {TARGET_DSN_ENV} using surprise.experiments.pg_instance "
                    "before requesting a default runner"
                )
E               ValueError: postgres: set COEVO_TARGET_PG_DSN using surprise.experiments.pg_instance before requesting a default runner

surprise\harness\oracles\registry.py:97: ValueError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s03_registry.py::test_implemented_is_the_seven_plan_ids
FAILED tests/test_surprise_s03_registry.py::test_sound_oracles_pass_on_both_target_engines
2 failed, 1289 passed, 3 skipped in 732.86s (0:12:12)
```

`python -m pytest -q tests/test_surprise_s16_sqlancer.py`

Exit code: `0`

```text
..............                                                           [100%]
14 passed in 91.04s (0:01:31)
```

`python -m surprise.gates.s15 --only sqlancer`

Exit code: `0`

```text
[PASS] sqlancer: 4 fixtures classified, the NoREC one judged fail with the loop's key fix|duckdb|deliminator,filter_pushdown; live run: 508273 queries, 7 reports, 0 judged, 3.6 MB of logs (609s)
S15 GATE [only: sqlancer]: PASS (1/1 groups passed)
```

`python -m surprise.gates.s16 --only sqlancer`

Exit code: `1`

```text
[FAIL] sqlancer: live SQLancer grid on postgres exited 2: error: arms[0].engine: expected one of duckdb, got 'postgres'

S16 GATE [only: sqlancer]: FAIL (0/1 groups passed)
```

`python -m pytest -q tests/test_surprise_s16_sqlancer.py  # first full run, before the final error-path test`

Exit code: `0`

```text
.............                                                            [100%]
13 passed in 89.81s (0:01:29)
```

`python -m pytest -q tests/test_surprise_s16_sqlancer.py -k 'startup or stdout or dialect or unchanged'`

Exit code: `0`

```text
....                                                                     [100%]
4 passed, 10 deselected in 1.37s
```

`git diff --cached --check`

Exit code: `0`

```text
```

`git status --short` (after commit)

Exit code: `0`

```text
```

开发期检查：`pytest -q tests/test_surprise_s16_sqlancer.py -k 'not real_pg'`

退出码：`1`。输出末 20 行（实际不足 20 行）：

```text
=================================== ERRORS ====================================
____________ ERROR collecting tests/test_surprise_s16_sqlancer.py _____________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-sqlancer\framework\tests\test_surprise_s16_sqlancer.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_sqlancer.py:14: in <module>
    from surprise.baselines import sqlancer_run as sq
E   ModuleNotFoundError: No module named 'surprise'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s16_sqlancer.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
```

开发期检查：`python -m pytest -q tests/test_surprise_s16_sqlancer.py -k 'not real_pg'`

退出码：`1`。新增测试误把 `SqlCase.setup` 的 tuple 与 list 比较；已改为比较 tuple，后续 14 项全部通过。输出末 20 行：

```text
        text = (LOGS / "pg_norec_mismatch.log").read_text(encoding="utf-8")
        predicate = "t0.c0::text ~ $$WHERE; FROM UNION$$ AND EXISTS (SELECT 1 WHERE TRUE)"
        text = text.replace("((t0.c0)>(1))", predicate)
        setup = ["DISCARD PLANS", "RESET ALL", "BEGIN", "ROLLBACK", "DROP TABLE other",
                 "INSERT INTO t0 VALUES (4)", "SET LOCAL statement_timeout = 5000"]
        text += "\n" + ";\n".join(setup) + ";\n"
        path = tmp_path / "dialect.log"
        path.write_text(text, encoding="utf-8")
        case = sq.parse_log(path, "postgres").case
        assert case.query == "SELECT * FROM t0"
        assert case.predicate == predicate
>       assert case.setup[4:] == setup
E       AssertionError: assert ('DISCARD PLA...UES (4)', ...) == ['DISCARD PLA...UES (4)', ...]
E         
E         Use -v to get more diff

tests\test_surprise_s16_sqlancer.py:60: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_surprise_s16_sqlancer.py::test_pg_dialect_and_setup_boundaries
1 failed, 11 passed, 1 deselected in 13.44s
```

## 与说明的偏差

- 直接运行 `pytest` 会因模块搜索路径缺少当前 worktree 的 `framework/` 而在导入 `surprise` 时失败；验收改用 `python -m pytest`，仍使用说明指定的项目解释器 `D:/CoevoDB/.venv/Scripts/python.exe`。未改 PATH、conftest 或测试配置。
- S16 的 SQLancer 门槛完成了 PG 样例分类、转换、manifest、两条用例认证及实例清理检查，随后网格实跑被当前 `grid.py` 的 DuckDB 限制拦截。这是说明中已预告的 `s16-loop` 合并依赖；本包未修改网格。

## 未决问题

- 完整测试集结果：`2 failed, 1289 passed, 3 skipped`。失败均为基线里的 `framework/tests/test_surprise_s03_registry.py`，本包未修改此文件及对应 registry：
  - `test_implemented_is_the_seven_plan_ids`（第 68 行）仍断言 `TARGET_ENGINES == ("duckdb", "datafusion")`，与前置 `s16-core` 已加入 `postgres` 的 registry 冲突。
  - `test_sound_oracles_pass_on_both_target_engines`（第 181 行）遍历新增的 `postgres`，但未启动 PG 实例或设置 `COEVO_TARGET_PG_DSN`，触发 registry 的预期 `ValueError`。
  - 依照“不靠改测试让测试通过”规则，记录上述问题并停止代码修改，由编排者在合并阶段处理。
- S16 的 SQLancer 网格实跑要等 `s16-loop` 合并后重跑。当前门槛失败原因是 `arms[0].engine: expected one of duckdb, got 'postgres'`。其前面的回放检查已通过；独立 PG 实跑测试通过，执行 3,148 条查询，状态 `budget_minutes`，无残留实例或口令文件。
- 全量测试在最后补充异常脱敏测试前已收集测试，因此其中包含首轮 13 项新增测试；最后增加的异常路径测试和最终源码已由独立新增测试集 `14 passed` 完整验证。全量运行后未修改源码；未因两项基线失败重跑整套测试。
