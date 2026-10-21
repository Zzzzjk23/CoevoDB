# CoevoDB

！！！注意：旧的框架和新的框架以各种方式杂糅在一起，严格按照下面的阅读顺序阅读。下面的**已确认的缺陷复现（31 个家族）**和**运行复现**是旧框架的产物，新框架还没有跑出过完整的实验。

寻找数据库引擎逻辑缺陷的研究代码，以及它确认过的缺陷的复现用例。

- `framework/` 是代码。现在的系统是 `framework/surprise/` 里的惊讶驱动框架：一个可证伪的理论给每个实验预测失败概率，Hunter 按信息价值挑下一个实验，标签只来自七类 oracle 加 CVE（Contract-Verified Evidence）流程，LLM 永远不当缺陷的裁判。原来的 CoevoDB（LLM Hunter/Fixer 共同进化）作为基线臂保留在 `framework/surprise/baselines/coevodb_v1/`。架构见 [framework/surprise/ARCHITECTURE.md](framework/surprise/ARCHITECTURE.md)。
- `duckdb/`、`datafusion/`、`sqlite/`、`tidb/`、`postgres/`、`mariadb/`、`mysql/` 是缺陷复现，`docs/` 是它们的证据（见文末"已确认的缺陷复现"一节）。

## 项目进展

工作按编号的会话推进，每个会话一个交付物、一个门槛（`framework/surprise/docs/SESSIONS.md`）。S0–S12 把旧系统改造成惊讶驱动框架；S13 起是正式实验（`framework/surprise/docs/EXPERIMENT.md` 里的 E1–E7），在专用的实验服务器上跑。

截至 2026-10-22：S0–S15 已完成。S16（把 PostgreSQL 16.15 接成目标引擎）的本机代码已全部合并，收尾前暂停。S19（E1，DuckDB 主对比）在服务器上做预实验，正式网格等项目负责人说了再跑。**实时状态、未决问题与下一步见 [framework/surprise/docs/HANDOFF.md](framework/surprise/docs/HANDOFF.md)**，它总比本文件新。

git 约定：每个会话在分支 session/sNN 上做，结束时打 tag `sNN-done`（验收后的修订打 `sNN-done-r2`）；工作包在分支 grok/&lt;包号&gt; 上做；`sNN-deploy-N` 标记部署到服务器的版本。`main` 落后于会话分支（最后一次合并是 S15）。

## 阅读顺序

1. `CLAUDE.md`：每个会话都要守的规则，人和 agent 都一样。
2. [framework/surprise/ARCHITECTURE.md](framework/surprise/ARCHITECTURE.md)：框架由哪些部分组成。
3. [PLAN.md](framework/surprise/docs/PLAN.md)：总规划。只读，只随项目负责人的决定改（§9 列出这些决定）。
4. [SESSIONS.md](framework/surprise/docs/SESSIONS.md)：每个会话的范围、交付物与门槛。
5. [EXPERIMENT.md](framework/surprise/docs/EXPERIMENT.md)：正式实验协议。
6. [HANDOFF.md](framework/surprise/docs/HANDOFF.md)：当前状态与未决问题。
7. [DECISIONS.md](framework/surprise/docs/DECISIONS.md)：决策日志，只追加。
8. [SERVER.md](framework/surprise/docs/SERVER.md)：实验服务器的环境、部署与运行手册。
9. [ORCHESTRATION.md](framework/surprise/docs/ORCHESTRATION.md)：会话怎么推进——编排者先写门槛，执行者在各自的 worktree 里实现每个工作包（`tools/orch/grok_worker.py`），编排者审查后合并。
10. [framework/README.md](framework/README.md) 与 [framework/AGENTS.md](framework/AGENTS.md)：命令、环境变量、PostgreSQL 注意事项。

## 规则

完整的列表在 `CLAUDE.md`，下面是最容易踩到的几条。

- 密钥只从环境变量来（`DEEPSEEK_API_KEY`、`PUSHPLUS_TOKEN`）：不打印，不写进代码、配置、日志、提交或聊天。每人用自己的密钥。
- LLM 永不打标签：标签只来自七类 oracle 加 CVE。
- `framework/surprise/harness/` 与 manifest 里的常数是冻结的（门槛核对哈希）。S16 为 PostgreSQL 解冻过一次并重新冻结；再要改，先问项目负责人。
- 只做当前会话的范围，范围外的问题记进 HANDOFF.md 的未决问题。每个门槛（`framework/surprise/gates/`）都在它检查的工作开始前写好，以前的门槛保持全绿。
- 同一条会话分支同一时间只有一个编排者。
- 实验服务器只由一个人部署和起实验；不动正在跑的网格；服务器上的工作目录只检出 tag。

## 准备一台机器

下面这些都不在 git 里（被 gitignore），放在仓库根下，Windows 与服务器上布局相同。确切版本见 SERVER.md §2，机读清单见 SERVER.md §7。

| 路径 | 内容 |
|---|---|
| `.venv` | 主环境，Python 3.13.9：DuckDB 1.5.5、DataFusion 54.0.0、psycopg2-binary 2.9.13、sqlglot 30.21.0、pytest、matplotlib、scipy |
| `.venvs/duckdb-1.1.3` | DuckDB 1.1.3 加 psycopg2-binary（Version differential 的子进程） |
| `.venvs/duckdb-1.1.3-full` | 在 DuckDB 1.1.3 上跑整个框架（S8 召回、E4） |
| `.venvs/datafusion-50.0.0` | DataFusion 50.0.0 与 pyarrow（Version differential 的子进程） |
| `.src/duckdb-v1.5.5`、`.src/datafusion-54.0.0`、`.src/postgresql-16.15` | LLM 角色读的引擎源码，提交号是钉死的（见 `framework/surprise/roles/constants.py`、`framework/surprise/roles/sources_map.py`） |
| `.orch/pg16` | PostgreSQL 16.15：参照服务器（127.0.0.1:55432，用户 `coevo`），以及每个运行自起目标实例用的二进制 |
| `.orch/pg15` | PostgreSQL 15.19 的二进制（PostgreSQL 上的 Version differential） |
| `.orch/jdk`、`.orch/sqlancer` | JDK 21 与打过补丁的 SQLancer 构建（SERVER.md §8） |
| `framework/results/s08/` | S8 钉住的四个产物目录（`pre`、`longrun`、`old_no_llm`、`recall113`）；门槛核对它们的字节，只能拷贝，不能重新生成 |

仓库根下还有 `duckdb/`、`datafusion/` 两个复现目录，所以在仓库根执行 `import duckdb` 不装包也会"成功"；核对环境要看 `__version__`。机器相关的路径都能用环境变量覆盖，表在 [framework/README.md](framework/README.md) 的"机器相关的路径"一节。

## 测试与门槛

在 `framework/` 下用主环境的解释器执行（Linux 上是 `.venv/bin/python`）。不要直接敲 `pytest`：设置了密钥时 `framework/test_api.py` 会真的调用 DeepSeek API。

```bash
cd framework
../.venv/Scripts/python.exe -m pytest -q testing tests   # 约 10 分钟
../.venv/Scripts/python.exe -m surprise.gates.all        # 约一小时；退出码 0 = 全部门槛通过
```

有些门槛要和会话 tag 比对，所以克隆时要带上 tag。更多命令（Hunter 循环、网格、报告、基线、提醒、归档）见 [framework/README.md](framework/README.md)。

## 已确认的缺陷复现（31 个家族）

早先几轮测试（多 oracle 差分 + plan variant + 蜕变测试）确认的逻辑缺陷。每个目录里是自包含的复现：每个缺陷家族一个带注释的 `.sql` 文件（版本、期望与实际结果、上游链接），有的另附独立的验证脚本。

| 引擎 | 版本 | 家族 | 表现 | 状态 |
|---|---|---|---|---|
| DuckDB | 1.5.5 | [F1](duckdb/F1_correlated_exists_delim.sql) | 相关 EXISTS 自连接丢行（deliminator + filter_pushdown） | main `d8cdaa3` 上仍存在 |
| DuckDB | 1.5.5 | [F2](duckdb/F2_window_dup_partition.sql) | `PARTITION BY a,a` 里重复的键被错误合并 | main 上已修复 |
| DuckDB | 1.5.5 | [F5](duckdb/F5_parallel_cte_offset.sql) | CTE+OFFSET 并行时丢行（不稳定复现） | 1.5.5 比 1.1.3 更严重 |
| DuckDB | 1.5.5 | [F6](duckdb/F6_null_exists_notin.sql) | NULL/EXISTS（NOT IN 形状）结果错误 | 长期存在 |
| DuckDB | 1.5.5 | [F7](duckdb/F7_interval_cse.sql) | interval 的相等不是同余关系（CSE 替换出错） | main `d8cdaa3` 上仍存在 |
| DuckDB | 1.5.5 | [F10](duckdb/F10_window_frame_underflow.sql) | 窗口帧边界下溢：SIGFPE、INTERNAL 错误与静默的错误结果 | 最小形状已在 main 上修复 |
| DuckDB | 1.5.5 | [F11](duckdb/F11_merge_nmbs_rowid.sql) | 没有 INSERT 分支的 MERGE -> `Failed to bind rowid` INTERNAL 错误 | 1.5.5 发布版 |
| DataFusion | 54.0.0 | [DF-A](datafusion/DF-A_except_all.sql) | `EXCEPT ALL` 丢掉重数与 NULL 行 | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-B](datafusion/DF-B_intersect_all.sql) | `INTERSECT ALL` 返回左侧的重数，而不是两侧的最小值 | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-D](datafusion/DF-D_generated_column.sql) | `GENERATED ALWAYS AS ... STORED` 静默返回 NULL | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-E](datafusion/DF-E_correlated_cte_alias.sql) | WHERE 之外的相关子查询被拒；递归 CTE 的别名列表被丢弃 | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-F](datafusion/DF-F_using_key_coalesce.sql) | RIGHT/FULL 外连接的行上，USING/NATURAL 合并后的键为 NULL | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-G](datafusion/DF-G_decimal_literal.sql) | 高精度数值字面量静默丢精度 | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-H](datafusion/DF-H_recursive_count.sql) | 递归 CTE 上的 `count(*)` -> 内部错误 / Rust panic | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-I](datafusion/DF-I_all_subquery.sql) | 带未投影列的 `expr op ALL (subquery)` -> 断言失败 | 54.0.0 上确认 |
| DataFusion | 54.0.0 | [DF-J](datafusion/DF-J_lateral_unnest.sql) | lateral `UNNEST` 无法生成计划 | 54.0.0 上确认 |
| SQLite | 3.51.2 | [SQLITE-A](sqlite/SQLITE-A_star_using_rightjoin.sql) | RIGHT/FULL + USING 合并列上的 `SELECT *` -> 误报列名有歧义 | 确定复现 10/10 |
| SQLite | 3.51.2 | [SQLITE-B](sqlite/SQLITE-B_using_ambiguity.sql) | USING/NATURAL 的歧义检查方向不对称 | 确定复现 10/10 |
| SQLite | 3.51.2 | [SQLITE-C](sqlite/SQLITE-C_unistr.sql) | `unistr()` 输出畸形的 UTF-8（代理项不配对） | 确定复现 10/10 |
| TiDB | v8.5.8 | [TIDB-A](tidb/TIDB-A_time_overflow.sql) | TiDB 层不检查 TIME 溢出（对照 MySQL 9.7.1） | 上游 pingcap/tidb#56865 仍未关闭 |
| TiDB | v8.5.8 | [TIDB-B](tidb/TIDB-B_decimal_division.sql) | decimal 除法在内部多出精度（兼容性差异） | 低严重度 |
| PostgreSQL | 17.11/18.6/master | [PG-A](postgres/PG-A_excl_spgist_ndcoll.sql) | `EXCLUDE USING spgist` + 非确定性排序规则 -> 约束静默失效 | 新发现（BUG #19641 只涉及查询路径） |
| PostgreSQL | 17.11/18.6/master | [PG-B](postgres/PG-B_interval_out_reparse.sql) | `interval_out` 输出 `interval_in` 不接受的字面量 -> pg_dump 的文件无法恢复 | 新发现 |
| PostgreSQL | 17.11/18.6/master | [PG-C](postgres/PG-C_time_interval_overflow.sql) | `time_mi`/`timetz_pl`/`timetz_mi` 的 int64 回绕 -> 静默得出错误的时间 | 扩展 BUG #19670（4 处中只报了 1 处） |
| PostgreSQL | 17.11/18.6 | [PG-D](postgres/PG-D_ssi_arbiter_probe.sql) | `ON CONFLICT` 的仲裁探测不加 SIREAD 锁 -> 全部提交的 G2-item 异常 | 已知（Yandex 的讨论）；master 已修，未向后移植 |
| PostgreSQL | 17.11/18.6/master | [PG-E](postgres/PG-E_ssi_doom_swallow.sql) | 在 SXACT_FLAG_DOOMED 之前抛出 40001 -> SAVEPOINT/plpgsql 吞掉它，事务照样提交 | 已知（CF 6904）；独立复现 + plpgsql 路径 + A/B 验证 |
| PostgreSQL | 16.2..master | [PG-F](postgres/PG-F_memoize_param.sql) | Memoize 的键漏了连接参数 -> 缓存过期，计数错误 | 已知（CF 7175/ee2bbec）；A/B 验证过 |
| PostgreSQL | 18.6/master | [PG-G](postgres/PG-G_bit_input_diag.sql) | 对 `bit` 类型，`pg_input_error_info` 与实际转换给出的 SQLSTATE 不一致 | 新发现，低严重度（只影响诊断信息） |
| MariaDB | 11.8.9 | [MDB-A](mariadb/MDB-A_quantified_doubleneg.sql) | `NOT(NOT(x <op> ANY/ALL))` 返回补集；`<>` 是新受影响的 | 上游 #121079/MDEV-40443 未关闭 |
| MariaDB | 11.8.9 | [MDB-B](mariadb/MDB-B_mergeview_window_quantified.sql) | 合并的数据源 × 窗口/聚合 × 量化比较 -> 空集；派生表/CTE 也受影响 | 扩展 MDEV-40557/40780（12 种新形状） |
| MySQL | 8.4.2 | [MYSQL-A](mysql/MYSQL-A_quantified_doubleneg.sql) | 8.4 LTS 上 `NOT(NOT(quantified))` 结果错误 | 上游 #121079（只在 9.7 修复） |

运行产物（`results/`、`framework/archive/repair_bench/runs/`）被 gitignore；上面公布的缺陷是约 20 万次执行的精选结果。

### 运行复现

每个 `.sql` 文件都是自包含的：开头的注释写明版本、期望与实际输出、上游链接。

- **DuckDB**：`python -c "import duckdb; ..."` 或 `duckdb` 命令行，例如 `duckdb -c ".read duckdb/F7_interval_cse.sql"`（在 `duckdb==1.5.5` 上验证过）。
- **DataFusion**：`pip install datafusion==54.0.0`，把每条语句交给 `SessionContext().sql(...)`。
- **SQLite**：任意 3.51 及以上的 `sqlite3`（`unistr()` 的用例要 3.51+）。另附一个独立的验证脚本：`python sqlite/sqlite_unistr_hunt.py`。
- **TiDB**：在 127.0.0.1:4000 上起 `tiup playground`，再加一个 MySQL 参照（与 MySQL 9.7.1 的差异就是 oracle）。
- **PostgreSQL**：对 17.x/18.x 执行 `psql -f postgres/<file>.sql`（PG-A 要带 ICU 的构建；PG-D/PG-E 是两个会话的时序：在两个 SERIALIZABLE 连接上按顺序执行注释里的步骤）。
- **MariaDB / MySQL**：把每个文件交给 `mariadb`/`mysql` 客户端；oracle 是由引擎自己求值的 `NOT(NOT P) ≡ P`。

### 证据（`docs/`）

- [UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md)：每个家族一份可以直接上报的说明，按可上报程度排序（包括被排除的等级及原因）
- [FAMILY_LEDGER_155.md](docs/FAMILY_LEDGER_155.md)：DuckDB 1.5.5 的完整账本：签名、版本梯、跨引擎裁决
- [FAMILY_CASE_STUDIES.md](docs/FAMILY_CASE_STUDIES.md)：上游"同一家族反复出现"的案例研究，家族模型的动机
- [frame_fuzz_report.md](docs/frame_fuzz_report.md)：F10 的模糊测试（82.8 万种组合，10,670 次命中：1,836 次 SIGFPE + 2,866 次 INTERNAL + 约 2,950 次错误结果）
- [FINAL_REPORT.md](docs/FINAL_REPORT.md)：测试总量与 SQLancer 基线对比
- [manual_findings.jsonl](docs/manual_findings.jsonl)：精选的家族记录；[recall_repros.json](docs/recall_repros.json)：每个家族规范的 setup/query/fix_set

### 范围说明

只收录确认等级的家族。被裁定为未定义语义、调试设置、用户设置或规范观察的情形（F3、F8、F9、F12、F13、DF-C）记在 [docs/UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md) 里，但有意不作为缺陷复现收录。
