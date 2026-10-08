角色：执行者

# 工作包 s01-reorg：仓库整理（纯移动）与 surprise 骨架

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s01-reorg`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s01`（a28532a）
- 所属会话：S1（Phase 0 · 冻结基线与仓库整理），范围见 `framework/surprise/docs/SESSIONS.md` 的 S1 一节
- 依赖：门槛脚本 `framework/surprise/gates/`（`__init__.py`、`all.py`、`s01.py`）已经在基线里，只读，不要改。引擎环境已经装好，不用你装。

## 目标

三件事，都是"只移动、不改逻辑"。基线上 `python -m surprise.gates.all` 是 4/7 通过，做完应当 7/7。

### A. PG 专项脚本移到 `framework/campaigns/`

- 把 `framework/scripts/pg_*.py` 共 41 个文件用 `git mv` 移到 `framework/campaigns/`，文件名不变。`framework/scripts/` 里其余 29 个脚本不动。
- 不要新建 `framework/campaigns/__init__.py`：`scripts/` 也没有，两边都是命名空间包。
- 只允许改两处导入路径，其余 39 个文件必须一个字节都不变（`git diff -M` 里是 R100）：
  - `campaigns/pg_probe_run.py`：`from scripts.pg_recall_check import classify  # noqa: E402` → `from campaigns.pg_recall_check import classify  # noqa: E402`
  - `campaigns/pg_ssi_sibling.py`：`import scripts.pg_txn_fuzz as fuzz  # noqa: E402` → `import campaigns.pg_txn_fuzz as fuzz  # noqa: E402`
- 脚本里 `sys.path.insert(0, …parent.parent)` 的相对定位不用改（`campaigns/` 和 `scripts/` 同一深度）。文档字符串里 `python scripts/pg_xxx.py …` 这类用法说明也不改。

### B. `DuckDBRunner` 移到 `framework/targets/duckdb_runner.py`

- 新建 `framework/targets/duckdb_runner.py`，把基线 `framework/oracles/db_runner.py` 里的 `class DuckDBRunner`（第 65 行到文件末尾）整段原样搬过去，类体一个字符都不改。
- `framework/oracles/db_runner.py` 保留 `QueryResult` 和 `bags_equal`（原样不动），并在这两个定义**之后**（文件末尾）加一行兼容导入：`from targets.duckdb_runner import DuckDBRunner  # noqa: E402,F401`，上面配一两行注释说明原因（见"背景"第 1 条）。
- import 行的处理：
  - 新文件照抄原文件里 `DuckDBRunner` 用得到的 import 行和 `LOGGER = logging.getLogger(__name__)`；路径只改一处，`from .normalize import …` → `from oracles.normalize import …`；另加一行 `from oracles.db_runner import QueryResult`。
  - 旧文件只删掉搬走之后不再使用的 import 行和 `LOGGER`，其余不动。
  - 模块文档字符串：新文件用原来那段；旧文件改成一两句话，说明它现在放共享的 `QueryResult` / `bags_equal`，并兼容导出 `DuckDBRunner`。
- 结果要满足：`oracles.db_runner.DuckDBRunner is targets.duckdb_runner.DuckDBRunner`；`DuckDBRunner.__module__ == "targets.duckdb_runner"`；所有 runner 看到的是同一个 `QueryResult` 类。
- 其他文件一律不改：所有 `from oracles.db_runner import …` 的调用方（约 30 处）、`oracles/__init__.py`、`targets/__init__.py`、其余四个 runner 都保持原样。

### C. `framework/surprise/` 骨架

- 新建 `framework/surprise/__init__.py`，以及九个子包的 `__init__.py`：`harness/`、`features/`、`theory/`、`hunter/`、`diagnoser/`、`roles/`、`metrics/`、`experiments/`、`baselines/`。
- 每个文件只有一行模块文档字符串，说明这一层是什么，措辞依据 `framework/surprise/docs/PLAN.md` 第 4 节（四层：冻结评估器 harness、理论 theory + features、智能体 hunter / diagnoser、LLM 网关 roles；另有 metrics、experiments、baselines）。不写任何代码，不 import 任何东西。
- `gates/` 和 `docs/` 已经存在，不要动。

## 背景

1. 为什么不能把 `db_runner.py` 整个搬走、只留一行 re-export：`targets/__init__.py` 会导入 `targets/postgres_runner.py`，后者又 `from oracles.db_runner import QueryResult`；`oracles/__init__.py` 也会导入 `oracles/db_runner.py`。整体搬走之后两个包在导入时互相等对方，报 `ImportError: cannot import name 'QueryResult' from partially initialized module 'oracles.db_runner'`（编排者已实测）。所以 `QueryResult` 必须留在 `oracles/db_runner.py`，并且 `DuckDBRunner` 的兼容导入必须放在 `QueryResult` 定义之后。这个做法编排者已在临时副本里验证能通过门槛的六种导入顺序。
2. `targets/__init__.py` 会导入 `psycopg2`，它已经装在项目解释器里。不要为了任何原因去改 `targets/__init__.py` 或 `oracles/__init__.py`。
3. 两个脚本本来就不能用 `--help`，移动前后都一样，门槛只查它们的语法，不要修：`pg_repack_mvcc.py`（没有 argparse，导入即执行，不要运行它）；`pg_upgrade_mxact.py`（模块顶层有一个旧的 TypeError）。
4. 本机没有 PostgreSQL。campaign 脚本只允许用 `--help` 试，不要真的跑。
5. `*.md` 文档（`framework/AGENTS.md` 等）和 `framework/seeds/pg_transform_probes*.py` 的文档字符串里还写着 `scripts/pg_*.py` 的旧路径：不要改，那是 S12 的事。
6. 命令都在 `framework/` 目录下执行。worktree 根有 `duckdb/`、`datafusion/` 两个放 SQL 的目录，在根目录 `import duckdb` 会假成功。
7. 只改指定的行：不要重排 import、不要格式化、不要改行尾或编码。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/campaigns/**
framework/scripts/pg_*.py
framework/targets/duckdb_runner.py
framework/oracles/db_runner.py
framework/surprise/__init__.py
framework/surprise/harness/__init__.py
framework/surprise/features/__init__.py
framework/surprise/theory/__init__.py
framework/surprise/hunter/__init__.py
framework/surprise/diagnoser/__init__.py
framework/surprise/roles/__init__.py
framework/surprise/metrics/__init__.py
framework/surprise/experiments/__init__.py
framework/surprise/baselines/__init__.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 旧代码（`framework/surprise/` 以外）只移动、不改逻辑，移动时只允许改上面写明的导入路径。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。本包不需要改任何测试文件。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。本包不需要任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不改 `framework/targets/__init__.py`、`framework/oracles/__init__.py`、其余 runner、`framework/main.py`；不新建 `framework/campaigns/__init__.py`。
- 发现的任何 bug 都不修，写进报告的"未决问题"。
- 不装、不卸任何 Python 包，不碰 worktree 之外的任何文件。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 期望 64 passed, 3 skipped，退出码 0
python -m surprise.gates.all            # 退出码 0，最后一行是 GATES: PASS (1/1 passed)
python main.py --help                   # 退出码 0
cd ..
git diff -M --name-status a28532a..HEAD # 期望见下
git status --short                      # 期望为空
```

`git diff -M --name-status a28532a..HEAD` 应当正好是 53 行：

- 39 行 `R100  framework/scripts/pg_*.py → framework/campaigns/pg_*.py`
- 2 行相似度略低于 100 的重命名：`pg_probe_run.py`、`pg_ssi_sibling.py`（各只差一行 import）
- `M  framework/oracles/db_runner.py`
- `A  framework/targets/duckdb_runner.py`
- 10 行 `A  framework/surprise/**/__init__.py`

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s01-reorg

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
