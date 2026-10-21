# CoevoDB · 惊讶驱动的数据库缺陷发现

这棵目录的主体是 `surprise/` 里的惊讶驱动框架：一个可证伪的理论给每个实验预测失败概率；Hunter 按信息价值挑下一个用例；标签只来自七类 oracle 加 CVE（Contract-Verified Evidence）流程，LLM **永远不当缺陷的裁判**。原来的 CoevoDB（LLM Hunter/Fixer 共同进化）作为基线臂保留。架构见 [surprise/ARCHITECTURE.md](surprise/ARCHITECTURE.md)。

## 目录

| 路径 | 作用 |
|---|---|
| `surprise/` | 惊讶驱动框架（harness、特征、理论、Hunter、Diagnoser、LLM 角色、实验、指标、基线、门槛） |
| `oracles/`、`targets/`、`diagnosis/`、`seeds/`、`util/` | 共用的 runner、oracle、二分与 σ、种子语料、机器相关的路径 |
| `llm/`、`agents/base_agent.py`、`agents/bug_fixer.py`、`agents/json_utils.py`、`evolution/dce.py` | 共用的底层件（HTTP 客户端、最小化器、DCE 算子、调用账本） |
| `campaigns/` | PostgreSQL 测试脚本（`campaigns/pg_*.py`），S1 从 `scripts/` 挪过来 |
| `scripts/` | 旧系统的实验脚本，以及共用的 `scripts/cross_engine.py` |
| `archive/` | 归档的 `archive/coevo/` 原型与 `archive/repair_bench/` 补丁/定位基准 |
| `tests/`、`testing/` | 惊讶驱动框架的测试与原 CoevoDB 的测试 |

## 运行惊讶驱动框架

下面的命令都在 `framework/` 下执行，用仓库主环境（仓库根下的 `.venv`）的解释器，下文写作 `python`；环境见仓库根的 README。LLM 角色默认全关；`--llm ROLE` 打开一个角色（可重复），需要 `DEEPSEEK_API_KEY`。

目标引擎有 `duckdb`、`datafusion` 与 `postgres`。用 `--engine postgres` 时，运行会自己起 PostgreSQL 16.15 目标实例与 15.19 旧版实例（`surprise/experiments/pg_instance.py`），结束时删掉；只有 `COEVO_TARGET_PG_DSN` 与 `COEVO_OLD_PG_DSN` 都设了，才改用已有的实例。

`--llm-tier` 给所有角色调用选同一个端点：`fast` 与 `strong` 是 DeepSeek；`glm-flash` 是经 OpenRouter 调用的 GLM 5.3 Flash（服务商次序与推理强度在 `surprise/roles/providers.py`），S19 的运行用的就是这一档。每一档都从 `DEEPSEEK_API_KEY` 读密钥，所以跑 `glm-flash` 的机器上这个变量里放的是 OpenRouter 的密钥（服务器就是这样设的，见 `surprise/docs/SERVER.md` §5.2）。

```bash
# 密钥从环境变量读，不要写进 YAML。
export DEEPSEEK_API_KEY=...

# Hunter 循环（角色全关）
python -m surprise.experiments.loop --out DIR --seed 0 --engine duckdb --max-minutes 10

# 同样的循环跑在 PostgreSQL 上，角色都用 GLM 档
python -m surprise.experiments.loop --out DIR --seed 0 --engine postgres --max-minutes 10 \
    --llm prior --llm implementer --llm conjecturer --llm-tier glm-flash

# 实验网格，然后看状态
python -m surprise.experiments.grid run CONFIG --out DIR
python -m surprise.experiments.grid status DIR

# 对跑完的网格生成 RQ1–RQ6 报告与图
python -m surprise.metrics.report GRID_DIR

# 基线臂
# pure_llm 会调用 LLM，需要 DEEPSEEK_API_KEY；加 --llm-offline 则只从缓存回答
python -m surprise.baselines.pure_llm --out DIR --seed 0
python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N
```

`python -m surprise.experiments.loop --help` 列出全部参数（引擎、oracle、冻结、Hunter 策略、理论快照、LLM 缓存与调用上限）。`python -m surprise.baselines.old_no_llm --help` 列出 `--mode`（默认 `no_llm`）。

网格运行的提醒与归档：

```bash
# 经 pushplus 推送提醒（额度用完、调用连续失败、停滞、网格结束）；
# 只读结果目录，需要 PUSHPLUS_TOKEN，网格结束后自己退出
python -m surprise.notify.watch results/NAME --pid GRID_PID

# 打包跑完的网格、核对归档，再精简原始目录
python -m surprise.experiments.archive pack results/NAME --dest NAME.tar.gz
python -m surprise.experiments.archive verify NAME.tar.gz
python -m surprise.experiments.archive prune results/NAME --archive NAME.tar.gz
```

实验服务器上的网格由 `surprise/docs/runs/` 里的脚本起，照旁边的运行单做。现在用的两个脚本（`surprise/docs/runs/e1.sh`、`surprise/docs/runs/e1_pilot_glm.sh`）以 `results/NAME.work` 为工作目录起网格，这样实验生成的 SQL 写不了代码检出里的文件。完整的运行手册是 `surprise/docs/SERVER.md` §5。

## 测试与门槛

```bash
# 在 framework/ 下执行。不要直接敲 pytest：设置了密钥时
# framework/test_api.py 会真的调用 DeepSeek API。
python -m pytest -q testing tests

# 全部会话的门槛；退出码 0 = 通过
python -m surprise.gates.all
```

门槛要用到机器上的资源（各引擎的 venv、PostgreSQL 参照与二进制、源码检出、S8 钉住的产物），清单在仓库根 [README](../README.md) 的"准备一台机器"一节；有些门槛还要和会话 tag 比对。当前的门槛结果与已知的失败见 [surprise/docs/HANDOFF.md](surprise/docs/HANDOFF.md)。

## 旧 CoevoDB（基线臂）

原来的 LLM Hunter/Fixer 共同进化循环在 `surprise/baselines/coevodb_v1/`。`main.py` 转发到它，所以

```bash
python main.py --engine duckdb --mode no_llm ...
```

与 `python -m surprise.baselines.coevodb_v1.main ...` 相同。`--mode` 有九个取值：`full`、`random_category`、`no_llm`、`coverage_only`、`dce_only`、`shuffled_diag`、`coevo`、`coevo_warm`、`coevo_frozen`。作为对比臂时按墙钟时间跑：`python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed N [--mode no_llm]`。

转发入口的例子：

```bash
# DuckDB 上的反馈引导测试
python main.py --engine duckdb --mode full --iterations 100 \
    --queries-per-iter 8 --seed-mutations-per-iter 20

# PostgreSQL（pgserver 自动起一个内嵌的 PG 16.2）
python main.py --engine postgres --mode full --iterations 100 \
    --pg-datadir /tmp/coevo_pg

# 消融
python main.py --engine duckdb --mode random_category ...   # 没有反馈
python main.py --engine duckdb --mode no_llm ...            # 只用种子
```

### 缺陷判定分类

| 判定 | 含义 |
|---|---|
| `true_bug` | 健全 oracle 命中或裁决后的不一致，已最小化并去重 |
| `false_positive` | oracle 报了，但分诊发现测试或改写本身无效 |
| `version_divergence` | 新旧 DuckDB 结果不同；不算缺陷 |
| `cross_engine_divergence` | PG 与 DuckDB 结果不同；只作佐证 |
| `skipped_nondeterministic` | 排序并列或易变函数使测试无法判定 |

只有 `true_bug` 计入测试目标。版本差异与跨引擎差异单独报告。

### 诚实的边界

- 第一个确认的缺陷（DuckDB deliminator 的 `EXISTS` 自连接，见 `results/run_20260913_234645`）是在第 0 轮、反馈还没起作用时找到的——它验证的是 oracle 流水线，不是共同进化的说法。
- `version_divergence` 与 `cross_engine_divergence` 从不计为缺陷。
- UCB1 的遗憾界假设臂的集合固定、奖励平稳；Fixer 生成的根因臂破坏了平稳性，所以 bandit 的保证是经验上的，不是我们对整个系统声称的定理。

假设与实验门槛见 [RESEARCH_PLAN.md](RESEARCH_PLAN.md)，工程规格见 [BRIEF_coevo_framework.md](BRIEF_coevo_framework.md)。

## 机器相关的路径

有几个入口要用检出目录以外的资源。每一个都能用环境变量覆盖（`util/paths.py`）；默认值是原开发者的目录布局（`~/work/db_safety/...`），在新克隆上找不到——设环境变量，不要改源码。

| 环境变量 | 资源 |
|---|---|
| `DEEPSEEK_API_KEY` | LLM 凭据（config.yml 里写作 `${DEEPSEEK_API_KEY}`） |
| `COEVO_PGBLD` | PG assert/ASan 构建前缀的根目录（`pg186_assert`、`pgmaster_inject` 等） |
| `COEVO_PG_PREFIX` | PostgresRunner 用的完整安装前缀（覆盖 `--build` 的解析） |
| `COEVO_PG_EXTRA_OPTS` | LocalPgServer 额外的 postmaster `-c` 选项 |
| `COEVO_OLD_VENV` | 差分 oracle 用的旧版 DuckDB venv（或 `--old-duckdb-venv`） |
| `COEVO_DUCKDB_SRC` | `archive/repair_bench/run_localize.py` 用的 DuckDB 源码检出 |
| `COEVO_ARGUS_DIR` | `scripts/argus_*` 用的同级 Argus 检出 |
| `COEVO_KEYS_YML` | repair_bench 驱动用的 `{key, completion_url}` 文件 |

脚本的文档字符串统一把前缀写成 `$COEVO_PGBLD/<build>`。

惊讶驱动框架在仓库根下找它的资源（经 git 公共目录找，所以所有 worktree 共用一份），资源就位后新克隆可以直接用。下面的变量覆盖默认位置：

| 环境变量 | 资源 |
|---|---|
| `PUSHPLUS_TOKEN` | `surprise.notify` 提醒用的 pushplus token |
| `COEVO_VENVS` | 各版本解释器所在目录（默认 `.venvs`） |
| `SURPRISE_SOURCE_ROOT` | LLM 角色读的引擎源码检出的上级目录（默认 `.src`） |
| `COEVO_REFERENCE_PG_DSN` | Cross-DBMS 用的 PostgreSQL 参照（默认主机 127.0.0.1、端口 55432、用户 `coevo`） |
| `COEVO_TARGET_PG_DSN`、`COEVO_OLD_PG_DSN` | PostgreSQL 目标（16.15）与旧版（15.19）实例；每个运行给自己的实例设好，两个都设了则改用正在运行的实例 |
| `COEVO_PG_BIN`、`COEVO_PG_OLD_BIN` | 每个运行起实例用的 16.15 与 15.19 的 `bin` 目录（默认在 `.orch/pg16` 与 `.orch/pg15` 下） |
| `COEVO_JAVA`、`COEVO_SQLANCER_HOME` | SQLancer 臂用的 Java 与 SQLancer 构建（默认 `.orch/jdk` 与 `.orch/sqlancer`） |
