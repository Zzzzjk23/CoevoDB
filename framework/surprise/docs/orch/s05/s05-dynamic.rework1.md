# 审查意见 · s05-dynamic · 第 1 轮返工

独立复跑通过：pytest 363 passed / 3 skipped，GATES PASS 5/5，S05 九组全过（语料 1092 条落在 76 个单元、10 种主构造，计划层 480 条、数据层 483 条可用）。编排者另做的探测（六种语句都不执行被测语句、不发聚合探测、runner 只 setup 一次并关闭；层参数；超上限的表；CTE 遮蔽；边角值；两种引擎的计划；隔离提取与超时退化；`phi` 与 `corpus` 命令）也都通过。计划层、命令行、语料报告不要动。

报告里提的 DataFusion runner 遇到 NaN / Inf 报错那一条属实，是旧代码的问题，本会话不修，已记入交接。

下面三处要改，都在 `extract.py` 与 `data.py` 里。

## 1. `extract_isolated` 把调用方的错误吞掉了

文件：`framework/surprise/features/extract.py`。

现状：

- `registry_path` 指向读不了的文件：`_load_registry` 返回 `None`，子进程以退出码 2 结束，于是返回一个用**默认词表**、`plan` 与 `data` 为 `unavailable` 的 φ。调用方以为用的是自己的词表，拿到的 `vocab` 却是默认的。
- 没有 runner 的引擎（`postgres`）要求算 `plan` 或 `data`：`extract` 抛 `ValueError`，`extract_isolated` 却返回 `unavailable`。

改成：调用方的错误在父进程里、起子进程之前就抛出，和 `extract` 一致；只有子进程崩溃、超时、或输出解析不了时才退化成"语句层照算，`plan`、`data` 为 `unavailable`"。

- `registry_path` 给了但读不了或内容不合格：抛 `Registry.load` 本来会抛的异常（`OSError` 或 `ValueError`），不要接住。
- 要算 `plan` 或 `data` 而该引擎没有 runner：抛 `ValueError`。只要 `ast` 层时任何引擎名都可以，这一点保持。
- 子进程以退出码 2 结束（它认为输入不合法）：抛 `ValueError`，带上它写到标准错误的原因，不退化。

必须成立：

- `extract_isolated(case, registry_path="no/such/registry.json")` 抛 `OSError`（`FileNotFoundError`）。
- `extract_isolated(SqlCase(engine="postgres", setup=(), query="SELECT 1"))` 抛 `ValueError`；加上 `layers=("ast",)` 则正常返回，`plan`、`data` 为 `skipped`。
- 子进程超时（`timeout_s=0.01`）仍然退化，不抛异常（现状如此，保持）。

## 2. 基表的引用带上了名字以外的东西

文件：`framework/surprise/features/data.py`，`_base_tables`。

现状：引用是把整个 `Table` 节点去掉别名后写回 SQL。节点上还挂着别的东西时探测语句就坏了，一张读得了的表被记成 `unavailable`：

- `SELECT i FROM s TABLESAMPLE BERNOULLI (1 PERCENT)`：采样子句跟着进了 `SELECT * FROM ... LIMIT`。
- `SELECT * FROM (a JOIN b ON a.x = b.x)`：括号里的连接挂在第一张表的节点上，引用成了 `a JOIN b ON ...`。

改成：引用只由 catalog、schema、表名三段组成（原文带引号的保留引号），别的一概不带。数据层描述的是整张表，不是它的一个样本。另外，现在某张表的引用生成失败时（第 116 行的 `except Exception: continue`）是悄悄跳过这张表、这一层照样 `ok`：改成这一层 `unavailable`，不要少看一张表还说看全了。

必须成立（DuckDB）：

- setup `CREATE TABLE s AS SELECT range AS i, range % 7 AS k FROM range(2000)`，语句 `SELECT i FROM s TABLESAMPLE BERNOULLI (1 PERCENT)`：`data` 层 `ok`，有 `data:value:zero`、`data:type:integer`；连续提取多次结果相同。
- setup `CREATE TABLE a(x INT)`、`INSERT INTO a VALUES (1)`、`CREATE TABLE b(x INT)`、`INSERT INTO b VALUES (1), (1)`：`SELECT * FROM (a JOIN b ON a.x = b.x)` 与 `SELECT * FROM a JOIN b ON a.x = b.x` 的数据特征相同（`data:table:dup_rows`、`data:table:single_row`、`data:type:integer`），`data` 层都是 `ok`。

## 3. 集合运算的输入超过行数上限

文件：`framework/surprise/features/data.py`，`_setop_input`。

现状：某个输入跑得起来但行数超过上限时，不输出它的特征，这一层仍是 `ok`。φ 里没有 `data:setop:left_has_dups` 会被读成"左输入没有重复行"，而实际是没看全、不知道。

改成：输入跑得起来但超过上限，和表超过上限一样处理：整个数据层 `unavailable`，不输出数据特征。输入单独跑不起来（比如引用了外层的列）仍按说明原样：不输出它的特征，这一层仍是 `ok`。把 `limits.py` 里那条注释一并改对。

必须成立（DuckDB）：

- setup `CREATE TABLE p AS SELECT range % 3 AS i FROM range(150)`、`CREATE TABLE q(i INT)`、`INSERT INTO q VALUES (1)`，语句 `SELECT x.i FROM p x, p y EXCEPT ALL SELECT i FROM q`（左输入 22500 行）：`data` 层 `unavailable`，没有任何 `data:` 特征；`plan` 层仍是 `ok`。
- 同样的 setup，`SELECT x.i FROM p x EXCEPT ALL SELECT i FROM q`：`data` 层 `ok`，有 `data:setop:left_has_dups`。

## 测试

上面每一条"必须成立"在 `framework/tests/test_surprise_s05_dynamic*.py` 里都要有断言。已有的测试不许删、不许放宽；如果某条已有测试的期望与上面的规则冲突（比如钉死了"超上限的输入不影响层状态"），把那条测试的期望按新规则改过来，并在报告里逐条列出改了哪条、从什么改成什么。

## 验收

在 worktree 里，`python` 与 `pytest` 用现成的：

```powershell
cd framework
python -m pytest -q testing tests        # 0 failed，不少于 363 passed，skip 不多于 3
python -m surprise.gates.s01
python -m surprise.gates.s02
python -m surprise.gates.s03
python -m surprise.gates.s04
python -m surprise.gates.s05             # 九组全过
```

都是退出码 0。范围、禁区、报告格式仍以 `.orch/brief.md` 为准：只改 `features/extract.py`、`data.py`、`limits.py` 与你的测试文件，不改门槛，不改前两个包的文件，不执行被测语句本身，不用聚合 SQL 算数据性质。`.orch/tmp` 里的文件不要删。改完提交到当前分支，更新 `.orch/report.md`（保留第一轮内容，在后面加"第 1 轮返工"一节）。
