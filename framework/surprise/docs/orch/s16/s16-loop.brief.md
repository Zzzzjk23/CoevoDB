角色：执行者

# 工作包 s16-loop：主循环、网格、pure_llm 与报告在 PostgreSQL 上跑通；φ 的 PG 计划层

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-loop`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`（已合并 `s16-core`：`surprise/experiments/pg_instance.py` 与 harness 的 PG 目标 runner；`s16-oracles`：PG 的 Index presence、Version differential、CVE 与 manifest）
- 所属会话：S16（PostgreSQL 目标），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节。S20（E2：PG 上 `full`、`nollm`、`pure_llm`、`sqlancer` × 5 个种子）写明"不改代码"，所以 E2 跑起来需要的代码都在这里补上。每格独立实例的要求见 `EXPERIMENT.md` §5。
- 依赖：`s16-core`、`s16-oracles`。`pg_instance.ensure(directory, old=True)` 在环境里没有 DSN 时起 16.15 目标与 15.19 旧版、导出 `COEVO_TARGET_PG_DSN` / `COEVO_OLD_PG_DSN`、退出时恢复环境并停掉删除；已经有 DSN 时什么都不起。`pg_instance.stop_all(directory)` 停掉目录下残留的服务器。

## 目标

1. `framework/surprise/features/plan.py`：给 postgres 一支：用 `diagnosis.bisect.plan_op_names(runner, query, "postgres")`（它读 `EXPLAIN (FORMAT JSON)` 的 `Node Type`，名字大写、带空格，如 `HASH JOIN`、`INDEX ONLY SCAN`），把名字里不属于 `[A-Za-z0-9_]` 的字符换成 `_`（`INDEX ONLY SCAN` → `INDEX_ONLY_SCAN`），作为 `plan:` 叶子；没有算子或读不出来就是 `unavailable`。DuckDB 与其他引擎的分支不动（S5 的门槛核对）。
2. `framework/surprise/hunter/operators.py`：`index_presence` 对 `postgres` 也提供（现在只对 `duckdb`）。别的不动。
3. `framework/surprise/experiments/loop.py`：引擎里有 `postgres` 时，整个运行包在 `pg_instance.ensure(<out>/pg, old=True)` 里：实例要在建 manifest、开账本、建角色之前起来（运行 manifest 要记下 PG 版本），无论正常结束、被网格中断（状态 `interrupted`、退出码 130 的现有行为不变）还是出错，都停掉并删除数据目录。只有 DuckDB / DataFusion 的运行一个字节都不变（不建 `pg` 目录）。
4. `framework/surprise/baselines/pure_llm.py`：`engine == "postgres"` 时同样包在 `ensure(<out>/pg, old=True)` 里。别的引擎不变。
5. `framework/surprise/experiments/grid.py`：
   - 每格结束后（`_finish` 里，写 `cell.json` 之前或之后都可以）调用 `pg_instance.stop_all(<格目录>)`，停掉强杀之后可能残留的服务器；停了的话往格的日志写一行 ASCII。只有 DuckDB 的格不受影响（`stop_all` 找不到东西就什么都不做）。
   - `_SQLANCER_RUN_ENGINES = ("duckdb", "postgres")`（SQLancer 臂的 PG 模式由并行的 `s16-sqlancer` 写在 `baselines/sqlancer_run.py` 里，本包只放行网格配置）。
   - PG 的格并发跑时，每格是自己的进程、自己的 `<格目录>/pg`，端口由 `pg_instance` 各自取空闲端口，不需要网格分配。
6. `framework/surprise/metrics/recall.py`：`known` 命令的用例里有 postgres 时，在 `pg_instance.ensure(<临时目录>, old=True)` 里认证；`_engine_versions()` 在设了 `COEVO_TARGET_PG_DSN` 时多一个 `"postgres"`（目标服务器的 `server_version`）。没有 PG 用例时输出与现在相同。
7. `framework/surprise/metrics/` 的报告：让 `python -m surprise.metrics.report <网格目录>` 在 PG 网格上正常出报告（现在有几处默认 `duckdb`，例如 `metrics/report.py`、`metrics/dups.py`；引擎从格的配置或 manifest 取），网格配置的 `known`（`recall known` 的输出）对 PG 的格按身份键算 RQ6 召回。DuckDB 网格的报告输出不变（S11、S14、S15 的门槛核对）。

测试：新文件 `framework/tests/test_surprise_s16_loop.py`（真实的 PG 实例）：φ 的 PG 计划层（含 `plan:MEMOIZE` 的用例可以用 `gates/s16_cases.py` 里的 PG-F，也可以自己写一个能走 Memoize 的）、Hunter 对 PG 提供 index presence、主循环在 PG 上跑几条实验后实例被删、环境里已有 DSN 时不起新实例、DuckDB 运行不建 `pg` 目录、`stop_all` 在网格 `_finish` 里被调用（可用小的替身格）、`recall known` 认证一个 PG 用例。

## 背景

- 门槛 `s16.py` 的 `phi`、`loop`、`grid` 三组是本包的验收（`grid` 组包括报告与召回）：
  - `phi`：`features.extract.extract_isolated` 对 PG-F、`plain_pred`、`indexable`、PG-A 在两个子进程里结果相同，计划层 `ok`；PG-F 的叶子含 `plan:MEMOIZE`、`plan:NESTED_LOOP`、`plan:INDEX_SCAN`、`plan:AGGREGATE`、`plan:INDEX_ONLY_SCAN`（编排者实测的 16.15 计划）；`plain_pred` 的数据层 `ok`。
  - `loop`：环境里去掉两个 DSN，`python -m surprise.experiments.loop --out <dir> --seed 7 --engine postgres --max-experiments 40` 退出码 0；`report.json` 的 `experiments == 40`、`engines == ["postgres"]`；全部记录是 PG 用例；`harness_error` 不超过 10%；标签里有 pass 与 invalid；运行 manifest 的 `environment.engines.postgres == "16.15"`、`old_engines.postgres == "15.19"`，`verify_manifest` 为空；`<dir>/pg/target/instance.json` 存在、两个 `data/` 都删了、`stop_all(<dir>)` 返回空；再在门槛自己起的实例（DSN 已导出）下跑一次，不建 `<dir>/pg`。
  - `grid`：先用 `recall known` 认证 `gates/s16_data/known_pg_cases.json`（PG-F，身份键要是 `fix|postgres|enable_indexscan,enable_memoize,enable_nestloop`，`engines.postgres == "16.15"`），再跑一个 2 格的网格（`nollm`，引擎 postgres，种子 7、8，1 分钟，并发 2，`known` 指向上面的输出），两格都 `done`、各自的 `pg/target/instance.json` 端口不同、网格目录下没有残留服务器；然后 `surprise.metrics.report` 出报告，`report["arms"]["nollm"]["cells"]` 是两格、`report["rq6"]["arms"]["nollm"]["recall"]["n"] == 2`。
- E2 的格是 24 小时：实例要在格的整个生命里都在；PG 的数据目录会随运行变大（每格 24 小时估计几 GB），格结束时删数据目录、留 `server.log` 与 `instance.json`。
- 实例的服务器进程留在格的进程组里（`pg_instance` 已经这样起），网格强杀格时会一起结束；`stop_all` 是兜底。

## 允许改动的路径

```allow-paths
framework/surprise/features/plan.py
framework/surprise/hunter/operators.py
framework/surprise/experiments/loop.py
framework/surprise/experiments/grid.py
framework/surprise/baselines/pure_llm.py
framework/surprise/metrics/**
framework/tests/test_surprise_s16_loop.py
```

（`framework/surprise/metrics/replay.py` 属于已合并的 `s16-replay`，不要改它。）

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`（已重新冻结的部分由编排者处理，本包不碰）、`framework/surprise/experiments/pg_instance.py`、`framework/surprise/baselines/sqlancer_run.py`（并行包的文件）。
- 不改 `framework/oracles/`、`framework/targets/`、`framework/diagnosis/`、`framework/seeds/` 等旧代码与数据。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 本包不做任何真实的 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 测试与门槛起的 PG 实例都在临时目录里，结束时停掉；不要停、不要改端口 55432 的参照实例与 `.orch/pg16/data`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                                  # 基线通过数上只增不减，skip 不增加
python -m surprise.gates.s16 --only phi loop grid        # PASS (3/3)
python -m surprise.gates.s05                             # PASS（φ）
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes   # PASS
python -m surprise.gates.s11                             # 只允许 ciao 一组失败（worktree 里没有 S8 长跑）
python -m surprise.gates.s15 --only config parallel kill interrupt llm   # PASS
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/`，S08、S11、S15 的几组本来就过不了；S10 的 `frozen`、S19 的 `scope` 会因为本会话的改动失败，这是已知的，编排者处理。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-loop

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
