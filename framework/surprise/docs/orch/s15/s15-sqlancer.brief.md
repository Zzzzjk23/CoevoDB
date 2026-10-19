角色：执行者

# 工作包 s15-sqlancer：真正运行 SQLancer 的对照臂

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s15-sqlancer`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s15`（已合并 `s15-grid`、`s15-llm`、`s15-rundata`）
- 所属会话：S15（实验基础设施），范围见 `framework/surprise/docs/SESSIONS.md` 的 S15 一节："真正运行 SQLancer 的臂：固定 commit，日志里报出的用例转成 `SqlCase`，经同一套 CVE 画像换成同一种身份键"。公平规则见 `framework/surprise/docs/EXPERIMENT.md` §3.1："所有臂的家族都由同一个身份裁判来数"。
- 依赖（已在基线里）：
  - 网格的 `sqlancer` 运行臂（`"run": true`）会这样起格：`python -m surprise.baselines.sqlancer_run --out <格目录> --seed <种子> --engine duckdb --max-minutes <分钟> --oracle NOREC --oracle WHERE --threads <n>`；到期限（预算 + 宽限）还没结束就发中断（Windows `CTRL_BREAK_EVENT`，POSIX `SIGINT`），再过 120 秒杀整棵进程树。
  - `RunData.kind` 在 manifest 的 `baseline` 为 `"sqlancer"` 时是 `"sqlancer"`；`run_metrics` 对这种运行的 `executions` 取 `report.json` 的 `"executions"`。
  - 主循环与纯 LLM 基线的 `main()` 已经把 Windows 的 `SIGBREAK`、POSIX 的 `SIGTERM` 转成 `KeyboardInterrupt`，可以照抄。

## 环境（编排者已装好，不入库）

在主检出区（git common dir 的上一级，worktree 的 `git rev-parse --git-common-dir` 指向它）的 `.orch/` 下：

- `.orch/jdk/jdk-21.0.12.1+1/bin/java.exe`（Linux 服务器上是 `.orch/jdk/<目录>/bin/java`）；
- `.orch/sqlancer/`：`sqlancer-2.0.0.jar`（SQLancer `ab328b756bf5d923b9d93959af3432546efe56fd` 打了一个补丁后构建，补丁在 `framework/surprise/docs/sqlancer/log-each-select.patch`）、`lib/`（依赖，已去掉自带的 `duckdb_jdbc-1.3.0.0.jar`）、`override/duckdb_jdbc-1.5.5.0.jar`、`COMMIT`（一行 commit 哈希）。

编排者实测过的命令（在 `<工作目录>` 下运行，日志写到 `<工作目录>/logs/duckdb/`）：

```
java -cp "<override/*.jar>;<sqlancer-2.0.0.jar>;<lib/*.jar>" sqlancer.Main --random-seed 7 --num-threads 1 --timeout-seconds 90 --num-tries 1000000 --log-each-select false --log-execution-time false duckdb --oracle NOREC
```

- 1.5.5 上约 1000 条查询每秒；stdout 每 5 秒一行 `[时间] Executed 59335 queries (344 queries/s; ...)`。
- `--log-each-select false` 必须配 `--log-execution-time false`（补丁已修好原来的断言）；不关的话每个数据库一份 `-cur.log`，记下每条查询，24 小时几十 GB。
- `--num-tries` 是找到多少个错误后停下，默认 100，要设得很大。
- 发现问题时 SQLancer 写 `logs/duckdb/database<N>.log`。格式见 SQLancer 源码 `Main.java` 的 `logException`、`SQLLoggableFactory`、`common/oracle/NoRECOracle.java`、`TLPWhereOracle.java`（源码在 `.orch/sqlancer-src/`，只读）：第一行 `--<异常类>[: 消息]`，消息与栈的每一行前面加 `--`；然后是 `-- Time:`（常常粘成 `---- Time:`）、`-- Database:`、`-- Database version: v1.5.5`、`-- seed value:` 四行；然后每行一条建库语句（以 `;` 结尾，语句里的换行写成字面的 `\n`）；最后可能有一行以 `-- ` 开头的 oracle 查询（换行同样转义）。门槛的四份样例在 `framework/surprise/gates/s15_data/sqlancer/`：三份是 DuckDB 1.1.3 上的真实日志（都是 SQLancer 自己的问题或意外报错），`norec_mismatch.log` 是编排者照源码格式写的 NoREC 不一致（用例是 S8 长跑在 DuckDB 1.5.5 上找到的真缺陷）。
- 换行：这四份样例在 Windows 的检出里是 CRLF（`core.autocrlf`），在服务器上是 LF；SQLancer 在 Windows 上写的日志也可能是 CRLF。解析两种换行都要认，结果相同。

## 目标

### 1. 新模块 `framework/surprise/baselines/sqlancer_run.py`

命令行：`python -m surprise.baselines.sqlancer_run --out DIR --seed N --engine duckdb [--max-minutes M] [--oracle NOREC|WHERE]... [--threads N] [--replay-logs DIR] [--run-id ID]`。`--oracle` 缺省为 `NOREC`、`WHERE`；`--threads` 缺省 1；`--engine` 现在只接受 `duckdb`。不带 `--replay-logs` 时 `--max-minutes` 必填。返回码：0 正常，2 参数错，1 运行出错，130 被中断（与主循环相同）。

**找工具**：环境变量 `COEVO_JAVA`（java 可执行文件）与 `COEVO_SQLANCER_HOME` 优先；否则主检出区的 `.orch/jdk/*/bin/java[.exe]`（恰好一个）与 `.orch/sqlancer`。类路径：`override/` 里的全部 jar 在最前，然后 `sqlancer-*.jar`，然后 `lib/*.jar`，但跳过与某个 override jar 同名（去掉 `-<版本>.jar` 后相同）的 lib jar；分隔符用 `os.pathsep`。

**输出目录**（与纯 LLM 基线同一种布局，`--out` 必须不存在或为空）：
- `config.json`：`kind`（`"sqlancer"`）、`engine`、`seed`、`oracles`、`threads`、`max_minutes`、`replay`（bool）。
- `ledger.sqlite`：用 harness 的 `Ledger`；manifest 用 `build_manifest(run_id)`，加 `"baseline": "sqlancer"` 与一节 `"sqlancer"`（commit、jar 的 SHA256、JDBC jar 名单、oracles、threads）。
- `progress.jsonl`：每条评判过的用例一行：`seq`、`record_id`、`oracle`、`y`、`kind`（fail_kind 或 invalid_reason）、`log`（日志文件名）、`elapsed_s`（自开始的秒数，两位小数）。
- `report.json`：`run_id`、`seed`、`engine`、`status`（正常到预算是 `"budget_minutes"`，回放模式是 `"replayed"`，中断 `"interrupted"`，出错 `"error"`）、`executions`（SQLancer 执行的查询数：stdout 里最后一个 `Executed N queries` 的 N；回放模式为 `null`）、`started_at`、`finished_at`、`wall_s`、`labels`（各 y 的条数），以及一节 `"sqlancer"`：`commit`（`COMMIT` 文件）、`jar_sha256`、`jdbc`（类路径上文件名含 `jdbc` 的 jar 名，排序）、`java`（`java -version` 的第一行）、`command`（java 的 argv）、`oracles`、`threads`、`reports`（日志总数）、`kinds`（三类各几份）、`converted`、`judged`、`unjudged`（转换成用例但没来得及评判的）、`pid`（java 进程号；回放模式 `null`）。
- `sqlancer/`：SQLancer 的工作目录（`logs/`、`stdout.txt`），以及 `sqlancer/reports.jsonl`：每份日志一行，`log`、`kind`、`sqlancer_oracle`（`"NOREC"`/`"WHERE"`/`null`）、`database_version`、`seed`、`oracle`（`"norec"`/`"tlp"`/`null`）、`converted`（bool）、`reason`（没转换的原因，否则 `null`）、`record_id`（评判后的记录号，否则 `null`）。
- 出错时照纯 LLM 基线写 `error.txt`。

**运行**：在 `<out>/sqlancer` 下起 java（上面的参数，`--timeout-seconds` 取预算秒数，`--random-seed` 取 `--seed`，`--num-threads` 取 `--threads`，DBMS 后面每个 oracle 一个 `--oracle`）。Windows 上用 `CREATE_NEW_PROCESS_GROUP` 起 java（网格的 `CTRL_BREAK_EVENT` 只发给驱动；java 收到它会打线程转储而不退出）；POSIX 上 java 留在驱动的进程组里（网格的硬杀会连它一起杀）。驱动单线程轮询：每两秒看一次 `logs/duckdb/` 里新的 `database*.log`（不含 `-cur.log`），两次轮询之间大小没变或 java 已退出才算写完；写完的日志当场解析、转换、评判。到预算（自开始 `--max-minutes` 分钟）就停：java 还在就结束它，没评判的计入 `unjudged`，还没解析的日志在结束前全部解析（解析很快）以便计数。任何退出路径（正常、出错、`KeyboardInterrupt`）都要先结束 java（terminate，等 10 秒，再 kill；Windows 上再 `taskkill /PID <pid> /T /F`），再写报告。

**分类**（对每份日志）：
- `mismatch`：`AssertionError`，消息以 `the counts mismatch` 开头（NoREC），或是 TLP 的结果集不一致（`The size of the result sets mismatch`、`The content of the result sets mismatch`）；
- `unexpected_error`：其它 `AssertionError`（SQLancer 遇到预期外的报错）；
- `tool_error`：别的异常类（`SQLException`、`UnsupportedOperationException` 等：SQLancer 或驱动自己的问题）。
- `sqlancer_oracle`：消息或栈里出现 `NoRECOracle` → `NOREC`，出现 `TLPWhereOracle` → `WHERE`，否则 `null`。

**转换成 `SqlCase`**（形状与纯 LLM 基线的提示里写的规则相同：tlp 与 norec 要求 `query` 恰好是 `SELECT <列> FROM <表或连接>`，`predicate` 是不带 WHERE 的布尔表达式）：
- 建库语句：信息四行之后、不以 `--` 开头的行，去掉结尾的 `;`。
- NoREC 不一致：取消息里的第一条查询（`SELECT COUNT(*) FROM <from> WHERE <p>` 或 `SELECT <列> FROM <from> WHERE <p>`），用 sqlglot（duckdb 方言）找到顶层的 FROM 与 WHERE，但输出**原文**的片段：`query = "SELECT * FROM " + <from 原文>`，`predicate = <p 原文>`；oracle 为 `norec`。
- TLP 不一致：原查询（消息或查询行里的第一条）给出列与 FROM，第一条分区查询顶层 WHERE 的 `<p>` 给出谓词：`query = "SELECT " + <列原文> + " FROM " + <from 原文>`，`predicate = <p 原文>`；oracle 为 `tlp`。
- 顶层有 GROUP BY、HAVING、ORDER BY、LIMIT、DISTINCT、窗口或集合运算，就不转换（`reason = "unsupported_shape"`）。
- `unexpected_error`：出错的语句若是能照上面拆开的 SELECT，就照 `sqlancer_oracle` 对应的 oracle 转换；否则不转换（`reason = "not_a_query"`）。`tool_error` 一律不转换（`reason = "tool_error"`）。
- 门槛对 `norec_mismatch.log` 的期望：`SqlCase(engine="duckdb", setup=[4 条，不带分号], query="SELECT * FROM t1 a", predicate="NOT EXISTS (SELECT 1 FROM t1 b WHERE b.ch = a.ch AND b.id <> a.id)")`，见 `framework/surprise/gates/s15_cases.py` 的 `NOREC_CASE`。

**评判**：与纯 LLM 基线（`baselines/pure_llm.py` 的 `_execute`）完全相同的一套：`evaluate_final(case, oracle, ledger=..., run_id=..., purpose="sqlancer", spec={"log": ..., "sqlancer_oracle": ..., "kind": ...}, phi=PhiExtractor().extract(case).to_dict(), theory_version=None, p_t=None, diagnose=True)`。**标签只来自 harness**；SQLancer 说它是缺陷不算数。门槛要求那份 NoREC 样例被判 `fail`，家族键（`metrics.rq.label_key`）等于主循环对同一用例给的 `fix|duckdb|deliminator,filter_pushdown`。

**回放模式** `--replay-logs DIR`：不起 java，把 DIR 里全部 `*.log`（不含 `-cur.log`，按文件名排序）照上面解析、转换、评判，`status` 为 `"replayed"`，`executions` 为 `null`，`pid` 为 `null`。

### 2. 报告 `framework/surprise/metrics/report.py`

运行模式的 `sqlancer` 臂（网格配置里有 `run`）和别的臂一样按格读：`_iter_cells` 不再跳过它，`_metrics_for("sqlancer", ...)` 走 `run_metrics`，汇入各 RQ 表时当作一个普通的、有格的臂（门槛要求 `report["arms"]["sqlancer"]["cells"] == ["sqlancer/s7-r0"]`，`report["rq1"]["arms"]["sqlancer"]["families_per_hour"]["n"] == 1`）。只读汇总的 `sqlancer` 臂与 `report["external"]` 照旧。

### 3. 测试与测试数据

`framework/tests/test_surprise_s15_sqlancer.py`，数据放 `framework/tests/data/sqlancer/`（可以复制门槛的四份样例，再照源码格式补 TLP 不一致、带 JOIN 的 NoREC、SELECT 上的意外报错各一份）。覆盖：分类、`sqlancer_oracle`、转换的原文片段、不转换的各种原因、类路径的 override 规则、环境变量找工具、回放模式端到端（NoREC 样例判 fail、家族键）、报告接入（造一个只有 SQLancer 运行臂的网格目录）、一次 60 秒的真实运行（java、SQLancer 都在主检出区 `.orch/`）、中断（子进程跑 `--max-minutes 5`，20 秒后发中断，返回 130、报告 `interrupted`、java 进程已不在）。测试总时长控制在 5 分钟以内。

## 背景

- 门槛 `framework/surprise/gates/s15.py` 的 `sqlancer` 组与 `interrupt` 组的 SQLancer 部分是验收标准，请完整读它们（只读，不改）。`sqlancer` 组会通过网格真跑 10 分钟。
- 在 DuckDB 1.5.5 上 SQLancer 几分钟内多半什么也找不到，这是正常的；`kinds` 等计数为 0 也要写出来。
- SQLancer 的日志与 stdout 可能很大：只保留 `logs/` 下的缺陷日志与 `stdout.txt`，不要再复制。

## 允许改动的路径

```allow-paths
framework/surprise/baselines/sqlancer_run.py
framework/surprise/metrics/report.py
framework/tests/test_surprise_s15_sqlancer.py
framework/tests/data/sqlancer/**
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`；不改 `framework/surprise/harness/`（已冻结）与 `HASHED_PATHS` 里的旧文件；不改 `baselines/pure_llm.py`、`baselines/sqlancer.py`、`experiments/`、`metrics/rq.py`、`metrics/rundata.py`。
- 不改 `.orch/` 下的任何东西（只读地用 java 和 SQLancer）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 本包不需要 LLM 调用、不需要密钥；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                         # 0 failed，通过数不少于基线
python -m surprise.gates.s15 --only sqlancer interrupt                    # 全部 PASS（约 15 分钟）
python -m surprise.gates.s11 --only grid sqlancer runmetrics              # 全部 PASS
python -m surprise.gates.s14 --only smoke                                 # PASS
```

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下；写明 10 分钟真实运行的查询数与报告数。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s15-sqlancer

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
