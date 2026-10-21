角色：执行者

# 工作包 s16-core：每格 PostgreSQL 实例与 harness 的 PG 目标 runner

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-core`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（门槛 `framework/surprise/gates/s16.py` 已写好）
- 所属会话：S16（PostgreSQL 目标，解冻 harness 第一批），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节
- 依赖：无。环境已备好：公共检出（git common dir 的上一级，本机是 `D:\CoevoDB`）下有 `.orch/pg16/binaries/pgsql`（EDB 16.15）与 `.orch/pg15/binaries/pgsql`（EDB 15.19）；服务器上的布局是 `.orch/pg16/pgsql`、`.orch/pg15/pgsql`（自编）。

## 目标

把 PostgreSQL 16.15 接成 harness 的目标引擎的最底层：每个运行自己起的 PG 实例，以及 harness 里执行目标 SQL 的 runner。用户已同意分批解冻 harness（SESSIONS S16），本包只碰下面列出的两个 harness 文件。

### 1. `framework/surprise/experiments/pg_instance.py`（新）

模块常数（门槛逐个核对）：

```python
KINDS = ("target", "old")
VERSIONS = {"target": "16.15", "old": "15.19"}          # 启动后 SHOW server_version 必须等于它，否则抛错
BIN_ENV = {"target": "COEVO_PG_BIN", "old": "COEVO_PG_OLD_BIN"}
TARGET_ROLE = "coevo_target"
# DSN 环境变量名从 harness 导入：from surprise.harness.oracles.pg_target import TARGET_DSN_ENV, OLD_DSN_ENV
```

- `bin_dir(kind) -> Path`：设了 `BIN_ENV[kind]` 就用它；否则在公共检出根（用 `git rev-parse --path-format=absolute --git-common-dir` 的上一级，与 `harness/manifest.py` 找 `.venvs` 的做法相同）下依次找 `.orch/pg16/pgsql/bin`、`.orch/pg16/binaries/pgsql/bin`（old 用 `pg15`）。目录里没有 `postgres` 可执行文件（Windows 是 `postgres.exe`）就抛 `FileNotFoundError`，包括环境变量指向的目录。
- `class PgInstance(directory, kind="target")`：一个实例占一个目录 `directory`，里面放 `data/`（PGDATA）、`server.log`、`pgpass`、`instance.json`。
  - `start() -> PgInstance`：`data/` 不存在就 initdb：`-U coevo --encoding=UTF8 --locale=C --auth=scram-sha-256 --pwfile=<临时文件>`（超级用户口令随机生成，临时文件用完删掉）。在 `postgresql.conf` 末尾追加（取值照抄，门槛核对）：
    ```
    listen_addresses = '127.0.0.1'
    port = <空闲端口>
    unix_socket_directories = ''
    fsync = off
    synchronous_commit = off
    full_page_writes = off
    autovacuum = off
    max_connections = 50
    timezone = 'Australia/Sydney'
    log_timezone = 'Australia/Sydney'
    datestyle = 'iso, mdy'
    default_text_search_config = 'pg_catalog.english'
    lc_messages = 'C'
    ```
    时区、datestyle、全文检索配置、编码与排序与 Cross-DBMS 参照实例相同（`SERVER.md` §2）；空闲端口在 127.0.0.1 上绑 0 端口取得，起不来（端口被占）换一个再试，最多 3 次。服务器进程直接用 `bin/postgres -D data` 起（`subprocess.Popen`，输出写 `server.log`；Windows 加 `CREATE_NEW_PROCESS_GROUP`；POSIX 上**不要** `start_new_session`，让它留在调用者的进程组里，网格强杀格的进程组时会一起结束），不经 `pg_ctl start`。等到能连上为止（超时 60 秒抛错）。第一次启动后建角色：`CREATE ROLE coevo_target LOGIN NOSUPERUSER NOCREATEROLE CREATEDB PASSWORD '<随机>'`，`GRANT CREATE ON DATABASE postgres TO coevo_target`。两个口令写进 `pgpass`（libpq passfile 格式，`127.0.0.1:<port>:*:<user>:<password>` 两行，POSIX 上权限 0600）。写 `instance.json`：只含 `kind`、`version`、`port`、`pid`、`data_dir`、`bin_dir`、`log` 这些键（不能有口令）。
  - `stop()`：`pg_ctl -D data stop -m fast -w -t 60`，不成再 `-m immediate`，进程还在就杀掉；可重复调用。
  - `remove()`：`stop()` 后删掉 `data/` 与 `pgpass`（保留 `server.log` 与 `instance.json`）。
  - 属性：`running`（服务器进程在且能连上）、`port`、`pid`、`version`（`server_version`）、`dsn`（目标角色）、`admin_dsn`（超级用户）。DSN 形如 `host=127.0.0.1 port=<port> user=coevo_target dbname=postgres passfile=<pgpass 的绝对路径> connect_timeout=10`：只带 passfile 路径，**不带口令**。
- `running(directory, *, old=True, keep=False)`（上下文管理器）：在 `directory/target`（与 `directory/old`）各起一个实例，把 `TARGET_DSN_ENV`（与 `OLD_DSN_ENV`）写进 `os.environ`，yield `{"target": dsn, "old": dsn}`（`old=False` 时只有 target）。退出时（包括异常）把这两个环境变量恢复成进入前的值（原来没有就删掉），然后停掉实例；`keep=False` 时 `remove()`。
- `ensure(directory, *, old=True)`（上下文管理器）：需要的 DSN 环境变量都已经有值时什么都不起，yield 现有的值；否则等同 `running(directory, old=old)`。主循环、pure_llm、SQLancer 臂以后用它（不在本包）。
- `stop_all(directory) -> list[Path]`：找出 `directory` 下所有 `postmaster.pid` 指向的、还在运行的服务器，用 `pg_ctl stop -m immediate` 停掉（不成就杀进程），返回它们的数据目录。网格以后用它清理强杀之后的残留（不在本包）。
- 命令行 `python -m surprise.experiments.pg_instance check`：在临时目录里起 target 与 old，打印两行 `target 16.15 port=<n>`、`old 15.19 port=<n>`（ASCII），停掉并删除，退出码 0；任何一步失败退出码 1 并打印原因。

### 2. `framework/surprise/harness/oracles/pg_target.py`（新，harness 文件）

```python
TARGET_DSN_ENV = "COEVO_TARGET_PG_DSN"
OLD_DSN_ENV = "COEVO_OLD_PG_DSN"
class PostgresTargetRunner:
    def __init__(self, dsn: str | None = None, *, env: str = TARGET_DSN_ENV) -> None
```

- 构造时 `dsn` 为 None 就读 `os.environ[env]`；没有值抛 `ConnectionError`，消息里写出环境变量名，不能有 DSN 内容。`__repr__` 不显示 DSN。连接惰性建立也可以，但缺 DSN 必须在构造时就报。
- 与 `targets/duckdb_runner.py` 同一个接口：`setup(statements) -> list[(statement, error_or_None)]`、`run(sql, timeout_s=10.0) -> QueryResult`（`oracles.db_runner.QueryResult`）、`close()`、`engine_version`（属性，`server_version`，如 `"16.15"`）、`explain_plan(sql)`（`EXPLAIN (FORMAT JSON)` 的解析结果，失败返回 None）。另加属性 `backend_pid`（当前连接的 `pg_backend_pid()`，没有连接时 None）。
- **autocommit + 私有 schema**：每次 `setup()` 先丢掉上一个私有 schema（若有），新建 `coevo_t_<32 位十六进制>`，`SET search_path TO` 它，再按顺序执行语句。没调用过 `setup()` 就 `run()` 时同样先建 schema。`close()` 执行 `DROP SCHEMA ... CASCADE` 并关连接，可重复调用；连接已断时先重连再删。不要像参照 runner（`pg_reference.py`）那样把整段包进事务：旧的 PG Index presence 变体里有 `VACUUM`，事务块里跑不了。
- **拒绝执行的语句**（不发给服务器，返回的 error 以 `NotApplicable:` 开头；`setup` 里同样处理，记进 outcomes）：一个字符串里有多条语句；事务控制（`BEGIN`、`START`、`COMMIT`、`END`、`ROLLBACK`、`ABORT`、`SAVEPOINT`、`RELEASE`、`PREPARE TRANSACTION`、`COMMIT PREPARED`、`ROLLBACK PREPARED`）；会让会话跑出私有 schema 或换身份的：`SET`/`RESET` 的 `search_path`、`SET ROLE`、`RESET ROLE`、`SET SESSION AUTHORIZATION`、`RESET SESSION AUTHORIZATION`、`RESET ALL`、`DISCARD`。拆语句与跳过注释、引号、美元引号复用 `pg_reference.py` 里的扫描函数（导入，不要复制一份）。
- **setup 里的会话级 SET 成为会话默认值**：`setup()` 中成功执行的 `SET [SESSION] <name> {=|TO} <value>`（不含 `LOCAL`、`TO DEFAULT` 与上面拒绝的几种）按顺序记下；全部语句执行完后，若记下了 SET、并且 setup 没有建会话级对象（`TEMP`/`TEMPORARY` 表、视图、序列，`PREPARE`，`DECLARE`，`LISTEN`），就用 libpq 的 `options`（`-c name=value`，按 libpq 规则转义空格与反斜杠）重新连接、再 `SET search_path`。这样旧 `PlanVariantOracle` 每个变体之后的 `RESET` 回到 setup 设的值，而不是服务器默认值（编排者实测：PG-F 照原样执行时 fail 被归到 `no_nestloop`，改成会话默认值后归到 `no_memoize`）。建了会话级对象时不重连（照原样）。下一次 `setup()` 从服务器默认值重新开始（不带上一次的 options）。
- **超时**：每条语句执行前 `SET statement_timeout` 为 `timeout_s` 毫秒（setup 用 10 秒）；另在工作线程里执行，墙钟等到 `timeout_s + 5` 秒还没回来就 `cancel()`。超时的结果 `timed_out=True`、error 以 `TimeoutError:` 或服务器的 statement timeout 消息开头；之后 runner 照常可用。
- **连接丢失**：错误里有连接丢失的标志（服务器关闭连接、`terminating connection` 等，可参照 `pg_reference.py` 的 `_CONNECTION_LOST`）时 `is_internal_error=True`；下一次 `run()` 自动重连，带上同样的 options 与 search_path（schema 已提交，还在）。其余错误按 `oracles.normalize.is_internal_error` 判。
- **错误文本**：`f"{type(exc).__name__}: {exc}"`，其中私有 schema 名替换成 `coevo_t`，口令、DSN 不出现。同一条失败语句在两个 runner 里的错误文本必须逐字相同（标签要可复现）。
- 结果行用 `oracles.normalize.normalize_rows`，列名取 `cursor.description`。
- 工厂：`PostgresTargetRunner` 本身就是目标工厂（无参调用连目标）；旧版用 `PostgresTargetRunner(env=OLD_DSN_ENV)`（给 s16-oracles 用）。

### 3. `framework/surprise/harness/oracles/registry.py`（harness 文件，只改两处）

- `TARGET_ENGINES = ("duckdb", "datafusion", "postgres")`；`REFERENCE_ENGINES` 不变。
- `runner_factory_for("postgres")` 返回 `PostgresTargetRunner`（在函数里导入）。其余不动。

### 4. 测试

新文件 `framework/tests/test_surprise_s16_instance.py`、`framework/tests/test_surprise_s16_target.py`：用模块级 fixture 经 `pg_instance.running(tmp_path_factory 的目录)` 起实例（真实 PG，不 mock）；覆盖上面每一条（拒绝的语句、非超级用户拿不到 `COPY ... PROGRAM` / `ALTER SYSTEM` / `pg_read_file`、两个 runner 互不可见、超时后可用、`pg_terminate_backend` 之后报内部错误再自动恢复、setup 的 SET 经 `RESET` 回到 setup 值、带 TEMP 表时不重连、close 删 schema、环境变量的写入与恢复、`stop_all`）。不改已有测试与 conftest。

## 背景

- 旧的 `targets/postgres_runner.py` 依赖没装的 `pgserver` 包、`targets/pg_local_server.py` 用 unix socket 与 `/tmp`，两者在 Windows 上都用不了，也都在冻结清单里；本包不碰它们，新写。
- `harness/oracles/pg_reference.py` 是 DuckDB / DataFusion 的 Cross-DBMS 参照（端口 55432，超级用户，事务回滚），不是目标；本包不改它，只导入它的扫描函数。
- 目标 runner 用非超级用户角色：LLM 生成的 SQL 会在目标上执行，超级用户能借 `COPY ... PROGRAM` 在机器上执行命令（服务器是多人共用的）。
- 实例配置要与参照一致，否则 PG 目标的标签在两个平台上不同；`lc_messages = 'C'` 让错误消息是英文，`oracles/errors.py` 的值依赖错误分类靠它。
- 服务器上没有 trust 认证（多人共用），所以一律 scram + passfile。

## 允许改动的路径

```allow-paths
framework/surprise/experiments/pg_instance.py
framework/surprise/harness/oracles/pg_target.py
framework/surprise/harness/oracles/registry.py
framework/tests/test_surprise_s16_instance.py
framework/tests/test_surprise_s16_target.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`。harness 里只改上面列出的两个文件（`pg_target.py` 新建、`registry.py` 两处）。
- 不改 `framework/oracles/`、`framework/targets/`、`framework/diagnosis/` 等旧代码。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 标签路径上不调用 LLM；本包不需要任何 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不往仓库里写任何口令；测试与门槛起的实例都在临时目录里，结束时停掉并删除，不要留下还在运行的 `postgres` 进程（交付前用任务管理器或 `Get-Process postgres` 确认，只应剩下编排者端口 55432 的参照实例与它的子进程）。不要停、不要改端口 55432 的参照实例与 `.orch/pg16/data`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                                         # 1205 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s16 --only instances runner registry   # S16 GATE [only: ...]: PASS (3/3)
python -m surprise.gates.s04                                    # 只允许 freeze 一组失败（冻结清单等编排者重写）
python -m surprise.experiments.pg_instance check                # 退出码 0
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组本来就过不了；S10 的 `frozen`、S19 的 `scope` 会因为本会话改了 harness 而失败，这是已知的，编排者处理。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-core

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
