角色：执行者

# 工作包 s03-cross：独立 PostgreSQL 参照与 Cross-DBMS 法定数

基线为派发时 session/s03（registry 已合并），只做 S3 Cross-DBMS，不做版本差分/CVE。依据 PLAN 第3节逐项表和决策11：至少三个成功执行的独立引擎，且目标唯一异类才 fail。

```allow-paths
framework/surprise/harness/oracles/cross_dbms.py
framework/surprise/harness/oracles/pg_reference.py
framework/tests/test_surprise_s03_cross.py
```

## 公共接口（供 version 包复用）

- cross_dbms.judge_case(case, *, factory, timeout_s, options) -> Label；模块末尾调用 registry.register('cross_dbms', judge_case)，registry懒导入，不改公共文件。
- cross_dbms.default_reference_factories(target_engine) -> dict[str, callable]，包含其余独立引擎duckdb/datafusion/sqlite/postgres；用户传的options.reference_factories替代默认映射，None才默认，空dict就是没参照。
- cross_dbms.collect_reference_results(case, reference_factories, *, timeout_s) -> dict[str, QueryResult]；每个工厂新runner、按case.setup执行、检查setup错误、执行 forms.full_query(case)、finally close；失败参照也返回对应错误 QueryResult。只收参照，不收目标。未知ID/目标ID/版本别名拒绝ValueError。version包复用这个函数取得旧版方向的独立支持。
- 每个 oracle handler 从factory创建目标runner，公共judge已筛查，但自己的执行仍要检查setup。结果统一旧normalize.loose_bag，SQL解析/类型/方言错误不得算投票。

## PostgreSQL 参照

编排者已准备EDB PostgreSQL16.15，监听127.0.0.1:55432，数据库postgres、用户coevo、本机trust，无服务。通过已装psycopg2连接。你无需也禁止安装/启动/停止服务器、改worktree外任何文件。公共环境可从主检出区用，但你不得修改。

pg_reference.PostgresReferenceRunner(dsn=None)：dsn参数优先，其次COEVO_REFERENCE_PG_DSN，默认host=127.0.0.1 port=55432 user=coevo dbname=postgres connect_timeout=5。不得打印DSN（覆盖值可能含密码）。接口setup/run/close/engine_version兼容旧QueryResult；engine_version取真实SHOW server_version（本机16.15）。不调用旧PostgresRunner/pgserver，不改旧代码。

每个runner用独立连接、独立随机schema与事务隔离测试数据；不commit，close回滚并关闭，不留下表/schema、不影响其他用例。setup重复调用要重置。所有错误和statement_timeout正确映射；别让失败事务污染下一用例。动态schema名字不进入标签证据，标签须稳定。可用psycopg2.sql.Identifier，不能直接拼不可信标识符。非SELECT/状态变更查询按契约拒绝不适用；这不是PG目标引擎支持。

## Cross-DBMS 判定和输出

调用旧scripts.cross_engine.classify_divergence，但在其plurality基础上落实更严格的“目标唯一异类”。成功投票引擎只能按引擎ID计一次；版本不是独立引擎。目标查询普通/值依赖错误判invalid；内部错误依旧crash子类型。参照错误排除，三名成功投票者不足则invalid/insufficient_engines；足数且全同pass；足数且目标唯一异类fail/wrong_result；平票、多异类、异类是别的引擎，则invalid/non_unique_outlier（不得直接把plurality当fail）。

detail至少：voters为成功的引擎ID列表，outliers为异类ID列表（DF-A/B为['datafusion']），participants是各引擎执行结果/错误/版本的结构化记录。错结果identity.behavior带missing/extra计数（多数参照相对目标）；不能只有一句“引擎不同”。列表顺序与bag序列化确定性，不能把随机schema或耗时进标签。options可能是registry.OracleOptions。

## 已实测

setup：t=(1,1,2,2,2,NULL)，u=(1,2,NULL)。
EXCEPT ALL：DuckDB/PG均为bag[1,2,2]，DF=[]，SQLite语法错误。
INTERSECT ALL：DuckDB/PG均为bag[1,2,NULL]，DF=[1,1,2,2,2,NULL]，SQLite语法错误。仓库DF-B SQL注释漏NULL，不改旧文件。
不能把SQLite错误算成功，也不能降低法定数来满足门槛。

## 验收与收尾

```powershell
cd framework
python -m pytest -q testing tests
python -m surprise.gates.s03 --only cross
python -m surprise.gates.s02
```

测试不少于149、skip不增加。新增quorum/tie/multiple-outlier/target-in-majority/参照setup错误、PG隔离与错误后复用测试。门槛与全部真实引擎结果必须通过，不用mock替换门槛真实证据。其他S3组缺并行包时预期红，不改门槛。
不改conftest/公共文件/旧代码/gates/docs/CLAUDE.md/tools/orch/，不用LLM打标签，无DeepSeek调用。不要清理.orch/tmp，不碰worktree外文件。被拒操作不绕过。提交当前分支，写.orch/report.md（文件、命令退出码和末20行、偏差、未决问题），不tag/merge/rebase/push/switch/删分支。缺前置就报告停下。
