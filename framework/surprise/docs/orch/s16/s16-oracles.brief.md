角色：执行者

# 工作包 s16-oracles：PG 上的 Index presence（原生）、Version differential（15.19）、CVE 与 manifest

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-oracles`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（`s16-core` 已合并：`surprise/experiments/pg_instance.py`、`surprise/harness/oracles/pg_target.py`、registry 认 `postgres` 为目标）
- 所属会话：S16（PostgreSQL 目标，解冻 harness 第一批），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节；七类 oracle 的判定规则见 `PLAN.md` 第 3 节"七类 oracle 逐项"
- 依赖：`s16-core`。测试与门槛用 `pg_instance.running(...)` 起 16.15 目标与 15.19 旧版，DSN 在环境变量 `COEVO_TARGET_PG_DSN` / `COEVO_OLD_PG_DSN` 里。

## 目标

用户已同意分批解冻 harness（SESSIONS S16）。本包只改下面五个 harness 文件，DuckDB 与 DataFusion 的判定、标签与 CVE 结果逐字不变（门槛 S04、S06–S10 与 S16 的 `replay` 组会核对）。

1. `framework/surprise/harness/oracles/index_presence.py`：PostgreSQL 走**原生**索引（PLAN 表："Index presence … 仅 PostgreSQL；命中即 true_bug；不变"）。用旧 `oracles/index_variant.py` 的状态变体：`IndexVariantOracle().variants_for(list(case.setup))`（btree 每列、covering + `VACUUM ANALYZE`、partial、表达式、BRIN、GIN、HOT 更新、`ANALYZE`，上限 12 个），比较规则照旧 `IndexVariantOracle.check`：基线先跑；每个变体执行它的 setup（任何一条失败就跳过这个变体），再看 `EXPLAIN <query>` 的行里有没有 `Index` 或 `Bitmap`（没有就算"没走索引"，跳过），再跑查询，最后无论如何执行 teardown；变体超时跳过；内部错误判 crash；变体报非值依赖错误而基线成功判 error_mismatch；结果多重集不同判 wrong_result。可以在 adapter 里照旧逻辑自己写这个循环（像 DuckDB 那一支一样），以便记下每个变体的去向；不要改 `oracles/index_variant.py`。标签：
   - fail：`fail_label`，`switches=(变体名,)`（旧代码的 `表名.变体`），wrong_result 的 behavior 是基线对变体的 `multiset_difference`；
   - pass：至少一个变体比较过、都一致；
   - invalid：基线超时 `timeout`、基线值依赖错误 `value_dependent_error`、基线其他错误 `query_error`；setup 失败 `setup_error`；不是只读查询 `not_applicable`（`applicability: not_select`）；解析不出表 `not_applicable`（`no_base_table`）；没有一个变体走了索引 `not_applicable`（`no_index_path`）。
   - `detail` 里加 `index_variants_compared`（比较过的变体名列表，按执行次序）与 `index_variants_skipped`（`[{"variant": 名, "reason": "setup_failed" | "no_index_path" | "timeout" | "value_error"}]`）。DuckDB 那一支（ART 索引）一个字符都不动；DataFusion 仍是 `not_applicable`。
2. `framework/surprise/harness/oracles/version_differential.py`：PostgreSQL 的旧版不是 venv 子进程，而是 15.19 实例：
   - `case.engine == "postgres"` 时，`COEVO_OLD_PG_DSN` 没设判 `invalid / harness_error`（error 写 `"old server is missing"`，与"old interpreter is missing"同一做法）；设了就用 `PostgresTargetRunner(env=OLD_DSN_ENV)` 在进程内执行 setup 与查询，结果装成同样的 `_OldResult`（`version` = 旧服务器的 `server_version`，行用 `normalize_rows`，setup 第一条错误 → `setup_error`，查询错误 → `error`，超时 → 与 venv 一支相同的 `timeout`）。`options.old_python` 对 postgres 不适用，忽略。
   - `_version_of("postgres", runner)` 用 `runner.engine_version`。
   - 之后的判定（`_same_outcome`、`_value_dependent_split`、方向：参照多数与 TLP / NoREC / plan variant / index presence 的见证）一行不改；PostgreSQL 的参照是 DuckDB、DataFusion、SQLite（`default_reference_factories("postgres")`），index presence 现在对 PG 适用，会参与见证。
   - DuckDB、DataFusion 两支不动。
3. `framework/surprise/harness/cve/certify.py`：`_SINGLE_THREAD` 加 `"postgres": ["parallel"]`（`diagnosis/bisect.py` 里 `parallel` 的前置语句是 `SET max_parallel_workers_per_gather = 0`）。别的不动。
4. `framework/surprise/harness/cve/tier3.py`：`_version_ladder` 给 postgres 一支：没有 `COEVO_OLD_PG_DSN` 返回 `"unavailable"`；有就用第 2 条里同一个旧服务器查询函数（放在 `version_differential.py`，从这里导入，不要复制），然后照现有规则：协议或 setup 错误 `"unknown"`；查询报错时错误里有解析器标志（`_PARSER_MARKERS`，含 `syntax error`）`"unknown"`、否则 `"recent"`；行的 `loose_bag` 与本地相同 `"longstanding"`，否则 `"recent"`。DuckDB、DataFusion 不动。
5. `framework/surprise/harness/manifest.py`：只在设了 `COEVO_TARGET_PG_DSN` 时，`environment.engines` 多一个键 `"postgres"`（目标服务器的 `server_version`，连不上记 None）；只在设了 `COEVO_OLD_PG_DSN` 时，`environment.old_engines` 多一个键 `"postgres"`（旧服务器版本）。没设时 manifest 与现在逐键相同——`gates/s04.py` 的 `environment` 组与 `tests/test_surprise_manifest.py` 都要求这样。DSN 不进 manifest。`HASHED_PATHS` 不改（`pg_target.py` 已在 `surprise/harness/**` 里）。

测试：新文件 `framework/tests/test_surprise_s16_oracles.py`，真实的 16.15 与 15.19 实例（`pg_instance.running`），覆盖上面每一条：index presence 在可走索引的查询上 pass 且比较过若干变体、无表时 `not_applicable`、注入的错误结果（写一个只在建了索引之后才丢行的 runner 子类）判 fail 并带变体名；version differential 两版一致 pass 且 `old_version == "15.19"`、`'1_000'::int`（15 报错、16 返回 1000）判 `value_dependent_error`、`current_setting('server_version_num')` 判 `direction_unknown`、旧 DSN 缺失判 `harness_error`；`_single_thread_prelude("postgres")`；`_version_ladder` 三种结果；manifest 设与不设环境变量两种情况。

## 背景

- 门槛 `s16.py` 的 `oracles`、`cve`、`m1` 三组是本包的验收；用例与期望在 `gates/s16_cases.py`（编排者在派发前用原型 runner 对现有 oracle 跑过一遍）。PG-F（`postgres/PG-F_memoize_param.sql` 加 `ANALYZE`）经 CVE 第 3 档的期望身份：开关 `no_memoize`、fix set `["enable_memoize"]`、计划差异含 `MEMOIZE`、版本梯 `longstanding`（15.19 同样错）。`m1` 组用 `gates/s16_fixtures.py` 的注入 runner（子类化 `PostgresTargetRunner`）在新进程里认证，所以你的代码要在 CVE 子进程里也能工作（子进程从环境变量拿 DSN）。
- `version_differential` 的见证会以同一个 factory 调用 index presence；PG 上它会真的跑索引变体，注意耗时（每个变体若干语句）。
- `oracles/index_variant.py` 的变体里有 `ALTER TABLE ... DISABLE TRIGGER ALL`，非超级用户在有外键的表上会被拒——这时那个变体跳过，不是错误。

## 允许改动的路径

```allow-paths
framework/surprise/harness/oracles/index_presence.py
framework/surprise/harness/oracles/version_differential.py
framework/surprise/harness/cve/certify.py
framework/surprise/harness/cve/tier3.py
framework/surprise/harness/manifest.py
framework/tests/test_surprise_s16_oracles.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`。harness 里只改上面五个文件，其中每个文件只加 PostgreSQL 一支，不改别的引擎的行为。
- 不改 `framework/oracles/`、`framework/targets/`、`framework/diagnosis/` 等旧代码。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 标签路径上不调用 LLM；本包不需要任何 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 测试与门槛起的 PG 实例都在临时目录里，结束时停掉；不要停、不要改端口 55432 的参照实例与 `.orch/pg16/data`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                                              # 基线通过数上只增不减，skip 不增加
python -m surprise.gates.s16 --only instances runner registry oracles cve m1 seeds   # PASS (7/7)
python -m surprise.gates.s04                                         # 只允许 freeze 一组失败
python -m surprise.gates.s03                                         # PASS
python -m surprise.gates.s07                                         # PASS
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组本来就过不了；S06 的冻结一组、S10 的 `frozen`、S19 的 `scope` 会因为本会话改了 harness 而失败，这是已知的，编排者处理（重新冻结由编排者做）。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-oracles

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
