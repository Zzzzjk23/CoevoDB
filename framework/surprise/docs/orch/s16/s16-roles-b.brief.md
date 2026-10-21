角色：执行者

# 工作包 s16-roles-b：LLM 角色读可选的 PostgreSQL 16.15 源码检出、认 PostgreSQL 方言

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-roles-b`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（门槛 `framework/surprise/gates/s16.py` 的 `roles` 组已按本说明写好）
- 所属会话：S16（PostgreSQL 目标），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节；E2（PG 上的 `full` 臂）要用这些角色
- 依赖：无。编排者已把 PostgreSQL 源码 `REL_16_15` 浅克隆到公共检出的 `.src/postgresql-16.15`（与 `.src/duckdb-v1.5.5`、`.src/datafusion-54.0.0` 并列；`roles/source.py` 经 git common dir 找到这个父目录，`SURPRISE_SOURCE_ROOT` 可覆盖），HEAD 是 `7d3e000c5961a544302072058a1184e9a588837b`。
- 前一个包 `s16-roles` 的说明要求改 `roles/constants.py` 的 `SOURCE_DIRS`，执行者发现这会让现有测试 `tests/test_surprise_roles_source.py` 与 S09 门槛失败，如实停下了（做得对）。本说明改了设计：**`roles/constants.py` 与 `open_sources()` 一律不动**，PostgreSQL 的检出另走一条可选的路。

## 目标

现在六个 LLM 角色只认 DuckDB 与 DataFusion 的源码检出。PG 目标的运行里 prior 拿不到证据、conjecturer 拿不到源码片段、implementer 没有方言提示。本包补上 PostgreSQL 这几处；DuckDB 与 DataFusion 的运行（包括它们的 manifest）逐字不变。

1. `framework/surprise/roles/sources_map.py`：
   - `EXTRA_SOURCE_DIRS = {"postgres": "postgresql-16.15"}`、`EXTRA_SOURCE_COMMITS = {"postgres": "7d3e000c5961a544302072058a1184e9a588837b"}`（门槛逐字核对）。
   - `POSTGRES_GUC_FILES`：`diagnosis/bisect.py` 的 `POSTGRES_GUC_INTERVENTIONS` 里每个 16.15 有的干预名 → PG 源码里实现它的文件（相对检出根、在 `REL_16_15` 里真实存在；例：`enable_memoize` → `src/backend/executor/nodeMemoize.c`；一个干预可对应多个文件，比如 `enable_hashjoin` → `src/backend/executor/nodeHashjoin.c` 与 `src/backend/optimizer/path/joinpath.c`）。16.15 没有的 `enable_self_join_elimination`、`enable_distinct_reordering`、`enable_group_by_reordering` 不进表（前一个执行者已在 `guc_tables.c` 里核对过；`enable_presorted_aggregate`、`enable_async_append` 有，要进表）。
   - `POSTGRES_SOURCE_RULES`：φ 特征前缀 → (正则, 目录)，覆盖与 `DATAFUSION_SOURCE_RULES` 相同的前缀（集合运算、连接、子查询、窗口、聚合、分组、排序），目录在 `src/backend/` 下。
2. `framework/surprise/roles/source.py`：
   - `open_extra_sources(engines, *, verify=True) -> dict[str, SourceReader]`：对 `engines` 里出现在 `EXTRA_SOURCE_DIRS` 的引擎，在与 `source_roots()` 相同的父目录（同样认 `SURPRISE_SOURCE_ROOT`）下打开检出，`verify` 时核对 `EXTRA_SOURCE_COMMITS`。检出不存在或 commit 不对：**不抛错**，这个引擎不进结果，往 stderr 写一行 ASCII 说明。`engines` 里没有需要额外检出的引擎时返回 `{}`。
   - `readers_for(engines) -> dict[str, SourceReader]`：`open_sources()`（抛 `SourceError` 时当作 `{}`，与 runtime 现在的做法相同）合并 `open_extra_sources(engines)`。
   - `open_sources()`、`source_roots()` 不改。
3. `framework/surprise/roles/runtime.py`：把现在的 `try: readers = open_sources() except SourceError: readers = {}` 换成 `readers = readers_for(engines)`（`engines` 就是 `build_roles` 已有的参数）。别的不动。这样只有引擎含 `postgres` 的运行才多一个 reader，DuckDB / DataFusion 运行的 `manifest()["sources"]` 与现在相同。
4. `framework/surprise/roles/prior.py`：`_ENGINE_SEARCH` 给 postgres 一项，证据**只**取 16.x 的发布说明 `doc/src/sgml/release-16.sgml`（16.1–16.15 修过的缺陷都列在里面，相当于 DuckDB 的 `test/issues` 与 DataFusion 的 changelog）。证据行格式照旧：`EVIDENCE postgres doc/src/sgml/release-16.sgml:<行号> <文本>`。`SourceReader.grep` 的 `under` 必须是目录，按需要用 `under="doc/src/sgml"` 加只匹配这一个文件的过滤（看 `grep` 的 `suffixes` 怎么比），或在 prior 里自己过滤路径；不要扫到别的 sgml 文档。同样输入两次结果相同。
5. `framework/surprise/roles/conjecturer.py`：`select_sources` 加 postgres 分支：假设有 fix set（`interventions` 非空）时走 `POSTGRES_GUC_FILES`（与 DuckDB 分支同样的做法：按表的次序取、每个文件分到同样的行数预算、从第 1 行起）；没有时走 `POSTGRES_SOURCE_RULES`（与 DataFusion 分支同样的做法）。DuckDB、DataFusion 两个分支一个字符都不动。
6. `framework/surprise/roles/implementer.py`：`_DIALECT` 加 postgres，一句话说明 PostgreSQL 16 方言（写出 `PostgreSQL` 这个词；可提 `::` 转换、`generate_series`、`LATERAL`、`FILTER`、`DISTINCT ON`、`EXCEPT ALL`），并说明不能写事务控制语句（`BEGIN`/`COMMIT`/`SAVEPOINT`）、不能改 `search_path` 或角色（目标 runner 会拒绝，见 `s16-core`），只能用非超级用户可做的事。

测试：新文件 `framework/tests/test_surprise_s16_roles.py`，用真实的 `.src/postgresql-16.15`：`open_extra_sources` 的三种情况（有 postgres、引擎里没有 postgres、`SURPRISE_SOURCE_ROOT` 指向空目录时缺失）；`readers_for` 对 `("postgres",)` 与 `("duckdb",)`；PG 单元的 prior 证据非空、全部来自发布说明、两次相同；`enable_memoize` 的假设拿到 `nodeMemoize.c` 的片段；两张表里每个路径都存在；`open_sources()` 仍然只有两个；DuckDB 与 DataFusion 的 `select_sources` / `prior_evidence` 在几个固定输入上的结果与改动前相同（在测试里写死改动前算出的值）。不改已有测试。

## 背景

- 门槛 `s16.py --only roles` 逐项核对：`roles/constants.py` 与基线 tag 相比一个常数都没变；`EXTRA_SOURCE_DIRS`/`EXTRA_SOURCE_COMMITS` 的值；`open_sources()` 只有 duckdb、datafusion；`open_extra_sources(("postgres",))` 给出 commit 核对过的 reader，`open_extra_sources(("duckdb",))` 为空，`SURPRISE_SOURCE_ROOT` 指向空目录时为空；`readers_for` 两种情况；`prior_evidence(["postgres|plan_variant|join|unknown|unknown", "postgres|tlp|aggregate|unknown|unknown"], readers)` 非空且每行以 `EVIDENCE postgres doc/src/sgml/release-16.sgml:` 开头；`select_sources("postgres", <interventions=("enable_memoize",)>, None, readers)` 的片段路径含 `src/backend/executor/nodeMemoize.c`；`select_sources("postgres", <interventions=()>, {"features": ["ast:join:inner", "ast:agg"]}, readers)` 非空且路径都以 `src/` 开头；`_DIALECT["postgres"]` 含 `PostgreSQL`；`runtime.py` 里用的是 `readers_for(`。
- prior 不得读项目自己的缺陷账本（`docs/manual_findings.jsonl`、`recall_repros*.json`、仓库根的 `postgres/` 目录等）：那些是召回的真值，读了就泄漏（S10 的规则）。
- 为什么 PG 检出是可选的：`open_sources()` 缺任何一个检出就整体失败，三个引擎都拿不到源码；服务器上 PG 检出要到部署 S16 时才克隆，不能让它连累 E1 的 DuckDB 运行。

## 允许改动的路径

```allow-paths
framework/surprise/roles/sources_map.py
framework/surprise/roles/source.py
framework/surprise/roles/runtime.py
framework/surprise/roles/prior.py
framework/surprise/roles/conjecturer.py
framework/surprise/roles/implementer.py
framework/tests/test_surprise_s16_roles.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`（冻结）、`framework/surprise/roles/constants.py`。
- 不改 `.src/` 下的检出（只读）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 本包不做任何真实的 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                     # 1205 passed, 3 skipped 的基线上只增不减，skip 不增加
python -m surprise.gates.s16 --only roles   # S16 GATE [only: roles]: PASS (1/1)
python -m surprise.gates.s09                # PASS（LLM 角色的常数与缓存重放）
python -m surprise.gates.s10                # PASS（四个角色的规则与 M3 重放）
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组本来就过不了；S19 的 `scope` 会因为本会话的改动失败，这是已知的，编排者处理。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-roles-b

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
