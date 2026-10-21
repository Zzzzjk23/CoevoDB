角色：执行者

# 工作包 s16-sqlancer：SQLancer 臂的 PostgreSQL 模式

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-sqlancer`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（已合并 `s16-core`：`surprise/experiments/pg_instance.py` 与 harness 的 PG 目标 runner；`s16-oracles`——PG 的 Index presence、Version differential 与 CVE 版本梯——与本包并行开发，你的回放样例用不到它）
- 所属会话：S16（PostgreSQL 目标），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节。E2（S20，不改代码）有 `sqlancer` 臂，EXPERIMENT §3.1 写明 SQLancer 在 PG 上跑。S15 写的 SQLancer 臂（`baselines/sqlancer_run.py`）现在只认 DuckDB。
- 依赖：`s16-core`。没有配置 PG 实例时 `runner_factory_for("postgres")` 抛 `ValueError`，所以 PG 模式的认证必须在 `pg_instance.ensure(...)` 里做。之后的 `s16-loop` 会把网格的 `_SQLANCER_RUN_ENGINES` 放行到 postgres（`experiments/grid.py` 是它的文件，本包不碰）。
- 环境：SQLancer 2.0.0（`.orch/sqlancer`，commit 见 `COMMIT`）带 `postgresql-42.5.1.jar`；JDK 在 `.orch/jdk`；都经 git common dir 找到，worktree 里能用。编排者实测：SQLancer 的 PG 模式先连一个叫 `test` 的入口库（没有就报 `FATAL: database "test" does not exist`），之后自己 `CREATE DATABASE databaseN`；单线程约 200 条查询每秒。

## 目标

`framework/surprise/baselines/sqlancer_run.py`：

1. `run(..., engine=...)` 接受 `"duckdb"` 与 `"postgres"`；命令行 `--engine` 的选项同样两个。DuckDB 的行为、命令行、输出逐字不变（S15 门槛的 `sqlancer` 组核对）。
2. postgres 时，整个运行包在 `pg_instance.ensure(<out>/pg, old=True)` 里（旧版实例给转换出来的用例做 CVE 的版本梯与 Version differential）。实例起来后，用目标角色连上 `postgres` 库，`CREATE DATABASE test`（目标角色有 CREATEDB；已存在就跳过）。
3. SQLancer 的命令：全局选项里加 `--host 127.0.0.1 --port <目标实例端口> --username coevo_target --password <口令>`，子命令是 `postgres`，oracle 照旧（`NOREC`、`WHERE`）。口令从 DSN 里 `passfile=` 指向的文件读（`coevo_target` 那一行）。**口令不能落地**：`stats["command"]`、`report.json`、manifest、`stdout.txt` 以及任何日志里，`--password` 后面一律写 `<hidden>`；不要把口令放进环境变量以外的任何地方。（命令行参数在本机进程列表里看得见；这是非超级用户、只活一格时间的实例口令，编排者接受这一点，记在 DECISIONS。）
4. 日志解析：`_top_tokens`、`_parts` 等里写死的 `"duckdb"` 方言改成跟随引擎（postgres 用 sqlglot 的 `postgres` 方言）；`parse_log` 产出的 `SqlCase(engine=<运行的引擎>, ...)`。日志目录照旧是 `<work>/logs/<engine>`（SQLancer 的 PG 模式写到 `logs/postgres`）。PG 模式的日志在 `-- seed value:` 之后先有 SQLancer 自己的库操作：psql 元命令 `\c test;`、`\c databaseN;`，以及 `DROP DATABASE ...`、`CREATE DATABASE ...`（编排者实跑见过，样例见 `framework/surprise/gates/s16_data/sqlancer/`）。转换时从 setup 里去掉以 `\` 开头的行和 `CREATE DATABASE` / `DROP DATABASE` 语句（用例在目标 runner 的私有 schema 里跑，不建库）；其余语句照日志原样保留（目标 runner 会拒绝的 `DISCARD`、`RESET ALL`、事务控制等由 harness 判 `setup_error`，不在这里删）。DuckDB 的转换不变。
5. 转换出的用例照旧经同一条 CVE 流水线认证、写进账本；运行 manifest 在实例起来之后建，所以记得下 PG 的两个版本。
6. 统计里的 `jdbc` 列出用到的 JDBC 驱动（PG 时含 `postgresql-42.5.1.jar`）。

测试：新文件 `framework/tests/test_surprise_s16_sqlancer.py`，样例日志放 `framework/tests/data/s16/sqlancer/`。可以在本机对一个临时 PG 实例实跑 SQLancer 几分钟取真实日志（`--log-each-select false` 时只有出报告才有 `database*.log`；跑不出报告就照 PG 模式的真实格式手写，至少一条 NoREC 不一致、一条 TLP、一条 unexpected error、一条 tool error）。覆盖：PG 日志的分类与转换（用例引擎是 postgres、谓词切对）、`--replay-logs` 回放在 PG 实例下认证转换出的用例、命令里没有口令、`test` 库的创建、DuckDB 回放的输出与改动前相同。

## 背景

- 门槛 `s16.py --only sqlancer`（编排者会在派发前写好并提交，若你的基线里还没有，就以本说明为准）会：用编排者入库的 PG 样例日志跑 `--engine postgres --replay-logs`，核对各条的分类与转换、转换出的用例是 PG 用例且被认证（不是 `harness_error`）；再经网格实跑一个 SQLancer PG 格几分钟（要 `s16-loop` 合并后才能在网格里跑），核对状态 `budget_minutes`、执行数、JDBC 驱动、命令里 `--password` 后面是 `<hidden>`、格目录下没有残留的 PG 服务器、报告能读这个格。
- S15 的 DuckDB 做法与分类规则见 `gates/s15.py` 的 `check_sqlancer` 与 `gates/s15_data/sqlancer/`。

## 允许改动的路径

```allow-paths
framework/surprise/baselines/sqlancer_run.py
framework/tests/test_surprise_s16_sqlancer.py
framework/tests/data/s16/**
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`、`framework/surprise/experiments/`（含 `grid.py`、`pg_instance.py`）。
- 不改 `.orch/sqlancer`、`.orch/jdk`、SQLancer 的补丁与源码。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 本包不做任何真实的 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。PG 实例口令同样不进提交、报告与日志。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 测试与门槛起的 PG 实例都在临时目录里，结束时停掉；不要停、不要改端口 55432 的参照实例与 `.orch/pg16/data`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                        # 基线通过数上只增不减，skip 不增加
pytest -q tests/test_surprise_s16_sqlancer.py  # 全部通过
python -m surprise.gates.s15 --only sqlancer   # PASS（DuckDB 的 SQLancer 臂不变；要 10 分钟实跑）
python -m surprise.gates.s16 --only sqlancer   # 回放部分应通过；网格实跑部分要等 s16-loop 合并，失败时在报告里注明原因
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/`，S08、S11、S15 的几组本来就过不了；S10 的 `frozen`、S19 的 `scope` 会因为本会话的改动失败，这是已知的，编排者处理。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-sqlancer

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
