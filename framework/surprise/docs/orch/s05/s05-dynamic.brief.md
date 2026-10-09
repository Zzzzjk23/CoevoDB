角色：执行者

# 工作包 s05-dynamic：φ 的计划层与数据层、组合入口、隔离提取、命令行与语料分布报告

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s05-dynamic`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s05`（`s05-vocab`、`s05-ast` 已合并）
- 所属会话：S5（Phase 2：共同语言 φ），范围见 `framework/surprise/docs/SESSIONS.md` 的 S5 一节
- 依赖：`surprise.features` 里已有词表与注册表、φ 容器（`make_phi`）、规格核对、单元投影（`unit_parts`、`unit_of`）、语句层 `extract_ast`。先把 `framework/surprise/features/` 读一遍，沿用它的写法。harness（已冻结，只读）提供 `SqlCase`、`surprise.harness.oracles.forms.full_query`、`surprise.harness.oracles.registry.runner_factory_for`
- 这是 S5 的最后一个包：合并后九组门槛应当全部通过

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 5 节 Phase 2（各引擎计划算子、在库上算的数据性质）与第 7 节"数据性质特征成本"一条。交付：

```python
extract(case, *, layers=("ast", "plan", "data"), runner_factory=None, registry=None) -> Phi
extract_isolated(case, *, layers=("ast", "plan", "data"), timeout_s=None, registry_path=None) -> Phi
```

以及命令行 `python -m surprise.features phi` 与 `python -m surprise.features corpus`。验收以 `framework/surprise/gates/s05.py` 的五组 `dynamic stable distinguish specs corpus` 为准，前四组 `vocab spec units ast` 必须保持通过。数据层每个特征的含义以 `framework/surprise/gates/s05_cases.py` 为准：`CORE_VOCAB` 里 `data:` 开头的条目是定义，`DATA_PROBES` 是例子，`PLAN_FEATURES`、`UNITS`、`SPEC_PAIRS`、`CORPUS` 是实测出来的期望。先把这个文件读完。特征包不许 import `surprise.gates`。

### 1. `extract`（`features/extract.py`）

φ 描述的语句是 `full_query(case)`。流程：

1. `layers` 必须包含 `"ast"`，只能取这三个名字，否则 `ValueError`。没点名的层状态为 `skipped`。
2. 语句层：`extract_ast(full_query(case), case.engine, registry)`，状态照它返回的填。
3. 要算 `plan` 或 `data` 时需要 runner：`runner_factory` 为 `None` 时用 `runner_factory_for(case.engine)`；该引擎没有 runner（比如 `postgres`）且没传工厂，抛 `ValueError`。只要 `ast` 层时不建 runner，任何引擎名都可以。
4. 新建一个 runner，`runner.setup(list(case.setup))`。有任何一条 setup 语句报错（或 setup 抛异常）：要算的 `plan`、`data` 两层都记 `unavailable`，不输出它们的特征。用完关闭 runner。
5. **不执行被测语句本身。** 只跑 EXPLAIN、取表、查列类型和集合运算的输入。MERGE、DELETE 这类写语句同样只取计划。
6. 三层的特征合起来交给 `make_phi(case.engine, features, layers, registry)`。

### 2. 计划层（`features/plan.py`）

- DuckDB：复用旧工具 `diagnosis.bisect.plan_op_names(runner, query, "duckdb")`，它跑 `EXPLAIN (FORMAT JSON)` 并返回算子名的计数。每个算子名一个特征 `plan:<算子名>`，名字照引擎给的写（`plan:HASH_JOIN`）。
- DataFusion：`runner.run("EXPLAIN " + query)`，取第一列是 `physical_plan` 的那一行，每一行开头的标识符就是算子名（`plan:HashJoinExec`、`plan:DataSourceExec`）。
- 一个算子都取不到（EXPLAIN 报错、超时、输出解析不了）：这一层 `unavailable`。算子名里有字母、数字、下划线以外的字符的，跳过那一个。

### 3. 数据层（`features/data.py`）

性质一律在库上算，而且不靠第二条聚合 SQL：把行取回来在 Python 里数（同一个引擎缺陷可能把用来验证的聚合也算错）。

- **被引用的基表**：用 sqlglot 解析 `full_query(case)`（方言对应与语句层相同），取所有表引用，去掉 CTE 的名字，按名字去重。sqlglot 解析不了这条语句：这一层 `unavailable`。方言映射和"恰好一条语句"的解析已经在 `features/ast.py` 里（`_dialect`、`_parse_one`），同一个包内直接 import 它们来用，不要再抄一份，也不要改 `ast.py`。表函数（`range(10)`、`generate_series(...)`、`unnest(...)`）不是基表。
- **取行**：每张表 `SELECT * FROM <表> LIMIT <上限 + 1>`，经 runner 执行。取不到（表不存在等）或行数超过上限：这一层 `unavailable`。上限与单条探测语句的超时写成 `features/` 里的常数（上限 10000 行）。runner 返回的行已经是归一化过的列表，直接用。
- **表的形状**：`data:table:empty`、`single_row`、`dup_rows`（有两行完全相同）、`has_null`，对任何一张被引用的表成立就输出。
- **边角值**：`zero`（数值等于 0，布尔值不算数）、`negative`、`extreme_number`（绝对值不小于 2**31）、`empty_string`、`non_finite`（NaN 或无穷；DuckDB 的 runner 把它们归一成字符串 `float:nan`、`float:+inf`、`float:-inf`，DataFusion 给的是 Python 浮点数，两种都要认）。
- **列类型**：`DESCRIBE <表>` 在两个引擎上都能用，第二列是类型名。按名字归到 `data:type:integer / float / decimal / string / boolean / date / timestamp / other`（DuckDB 是 `INTEGER`、`VARCHAR`、`DECIMAL(10,2)` 这样的名字，DataFusion 是 `Int32`、`Utf8View`、`Decimal128(10, 2)`、`Date32`、`Float64` 这样的名字）。
- **集合运算的输入**：语句里每一个集合运算节点，左输入与右输入各自生成 SQL（语句有 WITH 时把 WITH 带上）作为查询执行，取回的行里有两行完全相同就输出 `data:setop:left_has_dups`（右边同理），有 NULL 就输出 `left_has_null`（右边同理）。某个输入单独跑不起来（比如它引用了外层的列）：不输出它的特征，这一层仍是 `ok`。这些特征说的是输入的性质，不是表的性质：`SELECT v FROM t WHERE v = 1 EXCEPT ALL …` 的左输入没有重复行，哪怕 `t` 里有。
- 语句没有引用任何基表（`SELECT 1`）：这一层 `ok`，没有表的特征。

### 4. `extract_isolated` 与命令行（`features/__main__.py`）

- `python -m surprise.features phi`：从标准输入读一个 JSON 对象 `{"case": <SqlCase.to_dict()>, "layers": [...], "registry": <发明特征文件路径>}`（后两个键可省），在标准输出打印一行规范 JSON：`json.dumps(phi.to_dict(), sort_keys=True, separators=(",", ":"))`。输入不合法时退出码 2，原因写到标准错误。
- `extract_isolated`：起一个子进程跑上面这条命令（工作目录为 `framework/`，环境变量去掉 `DEEPSEEK_API_KEY`），解析它的输出。子进程崩溃、超时（超时后在 Windows 上要把整棵进程树杀掉，做法可以照 `harness/cve/isolate.py` 的 `_kill`，但不要 import harness 的私有函数）、或者输出解析不了：语句层在调用方进程里照算，`plan`、`data` 记 `unavailable`。超时默认值写成常数。对无害的用例，它的结果必须与 `extract` 相等。
- `python -m surprise.features corpus --corpus <路径> [--out <路径>] [--limit N]`：对语料里每条种子（`setup_sqls`、`query`、`engine`）算 φ。有 runner 的引擎算三层，没有的（`postgres`）只算语句层。输出一份报告，JSON 的键：
  - `total`、`by_engine`；
  - `layers`：`{"ast": {"ok": n, "fallback": n}, "plan": {"ok": n, "unavailable": n, "skipped": n}, "data": {…}}`，没出现的状态可以不写；
  - `units`：`{"引擎|主构造|计划算子类|数据性质类": 条数}`（用 `unit_parts`，不含 oracle），`distinct_units`；
  - `constructs`、`plan_classes`、`data_classes`：三维各自的分布；
  - `vocab`：词表摘要。
  
  报告里不放时间戳和耗时：同一份语料两次运行的报告必须完全相同。给了 `--out` 就写成排序键的 JSON 文件；标准输出打印几行 ASCII 摘要（总数、各层状态、条数最多的十个单元）。`vocab` 子命令保持原样。
- `surprise.features` 再导出 `extract`、`extract_isolated`。

### 5. 测试

新增 `framework/tests/test_surprise_s05_dynamic*.py`。覆盖：两种引擎的计划特征；数据层每个特征的正例与反例；只算被引用的表；输入性质与表性质的区别；setup 失败；只要语句层；没有 runner 的引擎；`extract` 两次结果相同；`extract_isolated` 与 `extract` 相等、子进程被杀时的退化；`phi` 命令的规范输出与坏输入；`corpus` 命令在一份小语料上的报告与两次运行相同。测试里的 SQL 与小语料自己写，不要 import `surprise.gates`，不要在测试里跑完整的 `seeds/corpus.json`。

## 背景

编排者派发前实测（DuckDB 1.5.5、DataFusion 54.0.0、sqlglot 30.21.0）：

- 各族默认计划的算子：F1 与 F6 有 `LEFT_DELIM_JOIN`、`HASH_JOIN`、`DELIM_SCAN`；F2 是 `HASH_JOIN` 加 `PERFECT_HASH_GROUP_BY`，没有 `WINDOW`（窗口被优化器改写掉了）；F3 是 `STREAMING_WINDOW` 加 `NESTED_LOOP_JOIN`，没有名字里带 ASOF 的算子；F8 有 `UNION`；F9、F10 有 `WINDOW`；F11 的 MERGE 能取到计划（`HASH_JOIN`、`MERGE_INTO`）；DF-A、DF-B 都是 `HashJoinExec` 加 `DataSourceExec`。门槛里各族的单元照这些算出来。
- `EXPLAIN` 不执行语句：`duckdb/F10_window_frame_underflow.sql` 那两条直接执行会杀死进程的语句，取计划是安全的。
- DataFusion 不认 `EXPLAIN (FORMAT JSON)`，普通 `EXPLAIN` 返回 `logical_plan` 与 `physical_plan` 两行文本。
- 种子语料 `framework/seeds/corpus.json` 共 1092 条：DuckDB 784 条，其中 setup 全部成功的 532 条，其余 252 条有语句被 DuckDB 1.5.5 拒绝；PostgreSQL 308 条（这里没有 runner，只算语句层）。编排者用一个复用的 `DuckDBRunner` 对 784 条逐条 setup 加 EXPLAIN，进程内总共约 10 秒。
- `DuckDBRunner.setup` 每次都会新建连接，所以一个 runner 对象可以在种子之间复用；`DuckDBRunner.run` 有语句超时参数，DataFusion 的 runner 没有超时。
- DF-A 与 DF-B 的 φ 只差集合运算那一个叶子：计划算子、数据性质完全相同，把 `ast:set_op:except_all` 换成它的同类 `ast:set_op:intersect_all` 就从一个得到另一个。门槛会按这个等式检查。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/features/extract.py
framework/surprise/features/plan.py
framework/surprise/features/data.py
framework/surprise/features/limits.py
framework/surprise/features/__main__.py
framework/surprise/features/__init__.py
framework/tests/test_surprise_s05_dynamic*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不改 `framework/surprise/harness/`（已冻结）与 `framework/surprise/theory/`。
- `features/` 里前两个包的文件，除了 `__init__.py` 加导出、`__main__.py` 加子命令之外不动；发现它们有错，写进报告的"未决问题"，停下。
- 旧代码（`framework/surprise/` 以外）本包不碰：只调用 `diagnosis.bisect.plan_op_names`，不改它。
- 不执行被测语句本身；不用聚合 SQL 去算数据性质。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个已有测试确实该改，写进报告的"未决问题"，停下。
- 不按 SQL 文本、表名或族号硬编码结果。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不安装、不升级任何依赖，不动 `.venv`、`.venvs/`、`.orch/pg16/`。
- 不清理 `.orch/tmp`：临时文件留着不管，包括你自己建的（提交信息用 `git commit -m`）。不建任何指向 worktree 之外的链接或目录联接。被权限规则拒绝的操作不要换写法重试。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不做理论 T、版本空间、Hunter、LLM 角色。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。PostgreSQL 参照已在 127.0.0.1:55432 运行，不要启停它。

```powershell
cd framework
python -m pytest -q testing tests        # 0 failed，通过数不少于 323，skip 不多于 3
python -m surprise.gates.s01             # 退出码 0
python -m surprise.gates.s02             # 退出码 0
python -m surprise.gates.s03             # 退出码 0
python -m surprise.gates.s04             # 退出码 0，约 4 分钟
python -m surprise.gates.s05             # 退出码 0，九组全过
```

不要直接跑不带路径的 `pytest`。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。认为门槛或契约表的某个期望不对，写明是哪一行、你实测到什么，停下。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s05-dynamic

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
