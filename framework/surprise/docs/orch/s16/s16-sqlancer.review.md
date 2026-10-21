# 审查包 · s16-sqlancer

- 生成时间：2026-10-22T01:07:04+11:00
- 基线：`session/s16`（6191a06f349a）
- 分支：`grok/s16-sqlancer` @ 47029d9fe595，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 16m57s
- 执行者：codex codex-cli 0.163.0；会话 `01a15eb9-81e3-7ca0-8afe-b2643a37bbd8`

## 红旗汇总

- 本次审查包没有复跑测试（--skip-tests）
- 派发以来有 1 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s16..grok/s16-sqlancer
git diff -M --stat session/s16..grok/s16-sqlancer
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/baselines/sqlancer_run.py`、`framework/tests/test_surprise_s16_sqlancer.py`、`framework/tests/data/s16/**`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/baselines/sqlancer_run.py` |  |
| A | `framework/tests/data/s16/duckdb_sqlancer_before.json` |  |
| A | `framework/tests/data/s16/sqlancer/pg_norec_mismatch.log` |  |
| A | `framework/tests/data/s16/sqlancer/pg_tlp_mismatch.log` |  |
| A | `framework/tests/data/s16/sqlancer/pg_tool_error.log` |  |
| A | `framework/tests/data/s16/sqlancer/pg_unexpected_error.log` |  |
| A | `framework/tests/test_surprise_s16_sqlancer.py` |  |

提交：

- 47029d9 Junke: Add PostgreSQL support to the SQLancer baseline

## 2. diff 统计

```text
 framework/surprise/baselines/sqlancer_run.py       | 149 +++++++++++++----
 .../tests/data/s16/duckdb_sqlancer_before.json     | 134 +++++++++++++++
 .../tests/data/s16/sqlancer/pg_norec_mismatch.log  |  29 ++++
 .../tests/data/s16/sqlancer/pg_tlp_mismatch.log    |  26 +++
 .../tests/data/s16/sqlancer/pg_tool_error.log      |  14 ++
 .../data/s16/sqlancer/pg_unexpected_error.log      |  26 +++
 framework/tests/test_surprise_s16_sqlancer.py      | 185 +++++++++++++++++++++
 7 files changed, 533 insertions(+), 30 deletions(-)
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
- 日志 `.orch/logs/s16-sqlancer.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s16-oracles` 6191a06f349a → 34a7cc32a5c0
- 删除 `refs/heads/grok/s16-replay`（原 8bf6292d7b87）
- 移动 `refs/heads/session/s16` 6191a06f349a → cc5b6a7e15c6

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s16-sqlancer.jsonl`：105 条事件（item.completed 57，item.started 43，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 4653248 token（其中缓存 4539776），输出 23038（其中推理 8890），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@' from pathlib import Path root = Path('.orch') def output(name): raw = (root / name).read_bytes() valu…
exec [exit 0]: Report command results written.
file_change [completed]: update D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-sqlancer\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git status --short; git log -1 --format=\"%h %s\"; Select-String -Path .orch/report.md -Pattern '<"'!--|…
exec [exit 0]: 47029d9 Add PostgreSQL support to the SQLancer baseline .orch\report.md:113:<!-- OPEN_ISSUES -->
file_change [completed]: update D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-sqlancer\.orch\report.md
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git status --short; @' from pathlib import Path p = Path('.orch/report.md') s = p.read_text(encoding='ut…
exec [exit 0]: report.md complete; worktree status above is clean
file_change [completed]: update D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-sqlancer\.orch\report.md
text: 已提交 `47029d9`，工作区干净。 - 新增测试：14 项通过。 - S15 SQLancer 门槛：通过。 - 全量测试：1289 通过、3 跳过、2 项基线测试失败。 - S16：回放通过；网格实跑待 `s16-loop` 合并。 详情见 [.orch/report.md](D:/CoevoDB/.claude/worktrees/s16/.wo…
end: tokens in=4653248 cached=4539776 out=23038 reasoning=8890
orch.exit: {"pkg": "s16-sqlancer", "run": 1, "at": "2026-10-22T01:06:35+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
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
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
