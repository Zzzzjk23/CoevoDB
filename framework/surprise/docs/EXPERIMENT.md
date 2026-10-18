# EXPERIMENT · 正式实验协议

2026-10-19 由 S13 定稿，依据是用户当天的决定（`PLAN.md` §9，`DECISIONS.md` 的 S13 各条）。讨论稿在 Claude Doc：https://claude.ai/code/artifact/b1b40efa-a437-4839-aa25-a4e3a6845e63 。本文件是正式实验的唯一依据；与讨论稿不一致时以本文件为准。实施会话见 `SESSIONS.md` 的 S14–S25。

正式实验在 Linux 服务器上跑六个被测引擎：每格 24h、5 个种子，共 215 个 24 小时格加 45 个 1 小时格（约 217 格·天），分 E1–E7 七个里程碑，每个里程碑单独出一份报告。代码仍在 Windows 本机写。

## 1. 范围

- 只评估新框架及其消融。原 CoevoDB 是早期草稿，已淘汰，不作对照组；`surprise/baselines/coevodb_v1/` 与网格的 `old_coevodb` 臂留在仓库里不动，只是不进正式网格。
- 被测引擎：DuckDB、DataFusion、SQLite、PostgreSQL、TiDB、MySQL。MariaDB 只作 Cross-DBMS 参照。
- 规模：完整，每格 24h × 5 个种子；不加 harness 的结果行数上限；LLM 调用不设上限。
- 顺序：先 DuckDB 主对比（E1），再 PostgreSQL（E2），再其余（E3–E6），最后总报告（E7）。

## 2. 被测引擎与版本

DuckDB 与 DataFusion 不升版本（S4 起的门槛与钉住的产物都绑着这两个版本）；其余沿用旧系统测过的版本线，仓库里已有它们的已知复现，可用来验证 oracle。

| 引擎 | 目标版本 | Version differential 旧版 | Cross-DBMS 参照 | 已知复现 | 何时可用 |
|---|---|---|---|---|---|
| DuckDB | 1.5.5 | 1.1.3 | DataFusion、SQLite、PG | `duckdb/` F1–F11 | 现在 |
| PostgreSQL | 16.15 | 15 系列 | DuckDB、DataFusion、SQLite | `postgres/` PG-A–G | S16 之后 |
| DataFusion | 54.0.0 | 50.0.0 | DuckDB、SQLite、PG | `datafusion/` DF-A–DF-E | 已是目标；S17 补种子语料后才有探索车道 |
| SQLite | 3.51.0 | S17 选定（与目标之间修过最多逻辑缺陷的版本） | DuckDB、DataFusion、PG | `sqlite/` SQLITE-A–C | S17 之后 |
| TiDB | v8.5 系列 | v7.5 系列 | MySQL、MariaDB | `tidb/` TIDB-A、B | S18 之后 |
| MySQL | 8.4 LTS | 8.0 | TiDB、MariaDB | `mysql/` MYSQL-A | S18 之后 |
| MariaDB（只作参照） | 11.8 LTS | — | — | `mariadb/` MDB-A、B | S18 之后 |

- 参照引擎的版本必须与现在一致（SQLite 3.51.0、PG 16.15），否则 DuckDB、DataFusion 的 Cross-DBMS 标签会变，回放检查（§8）过不了。
- MySQL 族的 Cross-DBMS 一次三票（目标加另外两家）。共有的缺陷判不出来：MYSQL-A 与 MDB-A 是同一个缺陷，MySQL 与 MariaDB 都错时目标不是唯一异类，判 `invalid`。这是多数表决本身的局限，报告照实写；这类缺陷由 TLP、NoREC 等单引擎 oracle 去抓。
- 每个新引擎接入时，先用上表的已知复现照 M1 的办法验证 oracle；不够的话，从上游缺陷库补几条旧版有、新版修好的逻辑缺陷。
- 缺陷候选写进报告前，先到该引擎的最新版上复核，区分"已修"与"新"。

## 3. 臂

### 3.1 主臂与对照组

| 臂 | 配置 | 引擎 | 作用 |
|---|---|---|---|
| `full` | 新框架，六个角色全开，fast 档，调用不设上限 | 6 个 | 主系统 |
| `nollm` | 新框架，角色全关 | 6 个 | PLAN 定的"无 LLM 版"对照组，同时是消融下界 |
| `pure_llm` | 纯 LLM 生成用例，同一套 oracle 与 CVE，调用不设上限 | 6 个 | LLM 直接写用例 |
| `sqlancer` | SQLancer 固定 commit，在服务器上运行 | DuckDB、SQLite、PG、TiDB、MySQL；DataFusion 待核实是否支持 | 外部工具基线 |

公平规则：
- 同一台服务器、同一并发度、同样 24h 墙钟；LLM 的等待时间算在预算里。
- 所有臂的家族都由同一个身份裁判来数：SQLancer 报出的用例也要经 CVE 画像，换成同一种身份键。
- 所有 LLM 臂用同一档模型；成本按官方价格折算，作为结果写进每份报告。

### 3.2 消融

全部在 DuckDB 1.5.5 上做；A3–A5 在 SQLite 上再做一遍，看结论在第二个引擎上是否成立。

| 编号 | 臂 | 对比 | RQ |
|---|---|---|---|
| A1 | `nollm`（即 §3.1 的对照组） | 对 `full`：LLM 的总贡献 | RQ3 |
| A2 | `full` + `hunter: random` | 对 `full`：完整系统里追逐惊讶的作用 | RQ1、RQ2 |
| A3 | `nollm` + `hunter: random` | 对 `nollm`：不受 LLM 干扰的选择策略对比 | RQ1、RQ2 |
| A4 | `nollm` + `freeze: theory` | 对 `nollm` | RQ5 |
| A5 | `nollm` + `freeze: diagnoser` | 对 `nollm` | RQ5 |
| A6–A10 | `full` 依次去掉 implementer、conjecturer、prior、vocab_inventor、oracle_inventor | 对 `full` | RQ3 |
| A11 | `full`，全部角色用 strong 档 | 对 `full`：模型强度（PLAN 决策 10） | RQ3 |
| A12 / A13 | 多引擎 `full`（DuckDB + DataFusion + SQLite）/ 同上去掉 translator | 互比：迁移的作用 | RQ3 |
| A14 | 跨代配对：`theory_from` × `select_from` 各取 E1 种子相同的 `full` 运行的早、中、晚三代，9 对，每格 1h，不开 LLM 角色 | — | RQ5 |

- translator 只在两个以上引擎时才工作，所以不在单引擎里做"去掉 translator"，由 A12/A13 回答。
- freeze 只允许 implementer 与 prior 这两个不改理论的角色（`grid.py` 的 `_FROZEN_ROLES`），所以 A4、A5 放在无 LLM 版上对比，最干净，也不花钱。
- 消融与 E1 的 `full`、`nollm` 比较时，两边不在同一批里跑；靠固定的每格 CPU 份额与线程数（§5）保证条件一致，报告里写明这一点。

## 4. 时长、种子与统计

- 时长：主臂、对照、消融、召回每格 24h 墙钟；A14 每格 1h；预实验每格 2h。
- 种子：正式 1001–1005，所有臂共用；预实验 9101、9102。这几个数在 `s12-done-r2` 的门槛与测试里都没出现过（门槛 `s13` 的 `seeds` 组核对）。同种子重跑结果一致（S8 门槛），所以 `repeats = 1`，靠 5 个种子取样。
- 统计：每对比较 5 对 5，双侧 Mann-Whitney U 精确检验，最小可达 p ≈ 0.008；同一张表内的多重比较用 Holm 校正；效应量 Â₁₂；报中位数与 IQR。除了"每小时"，也报"每千次执行"，把吞吐和效率分开。
- 召回：DuckDB 1.1.3（`.venvs/duckdb-1.1.3-full`）单独跑一组（E4），报 RQ6 指标与每个已知缺陷的首次发现时间。其它引擎不加格子：§2 的已知复现在目标版本上本来就存在，直接在主对比的运行里数各臂找到了几个、用了多久。
- β 已在 S8 用独立种子预调并冻结（1.0），正式实验前不再调；其它常数照 manifest。

## 5. 调度与资源

- 块设计：每一批同时跑同一引擎、同一种子下的全部臂（主对比一批 4 格），负载、API 延迟、时段对每个臂都一样。
- 并发：目标 8 格（两批同时跑），每格 2 个线程、引擎线程数固定；退路 4 格。每个里程碑的预实验比较 1、4、8 格并发下的吞吐与标签是否稳定（S10 见过负载把标签判得不一样），定下来之后正式期间不变。
- PG、TiDB、MySQL、MariaDB 每格各起一个独立实例（不同端口与数据目录），格与格之间互不干扰。TiDB 吃内存，E6 可能只能跑 4 格。
- 不加结果行数上限：慢的单条照常占用墙钟，报告里列出每格最慢的 10 条及耗时；墙钟强杀（S15）保证一格到 24h 一定结束。
- 磁盘（服务器可用 309 GB，每格 24h 约 2 GB）：每个里程碑出完报告后，原始格子目录压缩、拷回 Windows 本机，服务器上只留报告与摘要。E1 的原始目录例外（约 40 GB）：E3 的 A14 要用它的理论存储，S16–S18 的回放检查要用它的账本，留到两者都用完。峰值在 E5，约 130 GB。

## 6. 里程碑与顺序

每个里程碑以 `python -m surprise.metrics.report` 加一份人工分析结束，单独就能写成一份报告。全部 215 个 24 小时格加 45 个 1 小时格；同时跑 8 格约 5 周，只能跑 4 格约 8 周，另加预实验与部署空档约 1 周。

| 里程碑 | 内容 | 前置 | 格数 | 日历（8 格 / 4 格并发） | 报告能写什么 | 运行会话 |
|---|---|---|---|---|---|---|
| E1 DuckDB 主对比 | §3.1 的 4 个臂 × 5 个种子 | S14、S15 | 20 | 3 / 5 天 | DuckDB 上的 RQ1、RQ2、RQ4；新缺陷候选清单 | S19 |
| E2 PostgreSQL | 4 个臂 × 5 | S16 | 20 | 3 / 5 天 | 服务器型引擎上的 RQ1–RQ4、已知复现召回 | S20 |
| E3 DuckDB 机制 | A2–A11 × 5；A14 | E1 | 50 + 45 个 1 小时格 | 7 / 13 天 | RQ3、RQ5：LLM 各角色、选择策略、冻结一侧、模型强度各贡献多少 | S21 |
| E4 DuckDB 召回与理论质量 | 1.1.3 上 4 个臂 × 5；人工真值抽样 | S15 | 20 | 3 / 5 天 | RQ6：召回、边界吻合度、家族划分与人工判定的一致性 | S22 |
| E5 嵌入式引擎泛化 | DataFusion、SQLite 各 4 个臂 × 5；A12/A13 × 5；SQLite 上 A3–A5 × 5 | S17 | 65 | 9 / 17 天 | 两个新引擎上的 RQ1–RQ4、已知复现召回；迁移（RQ3） | S23 |
| E6 TiDB 与 MySQL | 每个引擎 4 个臂 × 5 | S18 | 40 | 5–10 / 10 天 | MySQL 族的结果 | S24 |
| E7 总报告 | 跨引擎总表、缺陷汇总 | 以上全部 | 0 | — | 论文级的完整结果 | S25 |

- E5 的 65 格里有 5 格是 DataFusion 上的 SQLancer；SQLancer 若不支持 DataFusion（S15 核实），E5 是 60 格。
- PG 提前了，所以第一批解冻 harness 的是 PG（S16），目标是在服务器跑 E1 的 3–5 天里做完；赶不上，服务器就空等，不提前跑别的。其余四个里程碑按改动量从小到大排：E3、E4 仍在 DuckDB 上，不用动 harness；E5、E6 要等 S17、S18。
- 带 LLM 的格约 115 个，不设调用上限，成本在每份报告里按官方价格折算列出。

时间线（服务器与 Windows 本机并行）：

| 阶段 | 服务器 | Windows 本机 |
|---|---|---|
| 1 | S14 部署 | S14、S15 |
| 2 | E1 DuckDB 主对比（约 3–5 天） | S16 PostgreSQL 接入 |
| 3 | 空档：S16 部署与回放检查（S16 没做完就空等）；然后 E2 PostgreSQL（约 3–5 天） | S17 DataFusion、SQLite；写 E1 报告 |
| 4 | E3 → E4（DuckDB 消融与召回，约 1.5–2.5 周） | S18 的 MySQL 部分；写 E2 报告 |
| 5 | 空档：S17 部署与回放检查，S18 的 TiDB 门槛；然后 E5（约 1.5–2.5 周） | S18 收尾；写 E3、E4 报告 |
| 6 | 空档：S18 部署与回放检查；E6（5–10 天） | E5 报告 |
| 7 | — | E6、E7 报告 |

## 7. 服务器分工

- 服务器：`ssh 3090`（经 UNSW 跳板、免密钥），Ubuntu 24.04.4，Xeon Gold 5315Y（8 个物理核、16 线程），62 GB 内存，可用磁盘 309 GB；实验期间专用。
- 实验由用户自己 ssh 上服务器跑，照每个里程碑的运行单（S19–S24 交付）。
- Claude 只在搭环境（S14）与部署新引擎（S16–S18 的部署与回放检查）时动服务器，而且只在用户确认服务器空闲时动。
- grok 不登录服务器，只在本机 worktree 里写代码与脚本：它的 deny 规则看不到 ssh 引号里的远程命令，服务器上的操作也不留 diff 可审。
- 代码经服务器上的 git 仓库部署：本机推送 tag，服务器工作目录只检出 tag，不在上面改代码。结果由用户压缩后拷回本机。

## 8. 执行规则

- **协议冻结**：每个里程碑开跑前，把配置 JSON、harness 哈希、种子、并发度写进 manifest；跑的过程中不改。
- **回放检查**：每次解冻 harness 后，在服务器上用新 harness 回放 E1 账本里的一批记录。按 oracle 与标签分层抽 2000 条，`y`、oracle、身份证据、CVE 各档结果要逐条相同；本来就标成重跑不稳定或超时的记录只要求仍是 `invalid`。有一条不同就停下来查，DuckDB 的旧结果不能直接和新结果放进同一张表。
- **缺陷上报**：每个里程碑报告之后，把新家族的代表用例最小化，到该引擎的最新版上复核，去掉已修的、与已知复现相同的，按 `docs/UPSTREAM_ISSUES.md` 的格式整理成上报材料，交给用户提交。issue 编号与状态（已提交、已确认、已修复、被拒）记在同一个文件里，E7 汇总。Claude 不替用户提交。
- **预实验**：结果不进正式统计。
- **失败重跑**：正式格失败（`error.txt`）只按原配置重跑，不改配置；重跑次数记进报告。
- **密钥**：只走 `DEEPSEEK_API_KEY`；不带 LLM 的臂，子进程里没有密钥（网格已经这样做了）；服务器上的密钥只放在用户环境里，不进仓库、不进日志。

## 9. 机读清单

门槛 `gates/s13.py` 读下面这段 JSON：臂的每个配置键要么网格现在就认，要么在 `needs` 里写明由哪个会话补；每个引擎要么现在就是目标，要么写明由哪个会话接入；格数按清单重算，必须与上表一致。S19–S24 写网格配置时从这里抄。`"max_calls": "unlimited"` 与 `tier` 的写法以 S15 实现的为准，到时同步改这里。

```json
{
  "schema": 1,
  "hours": {"cell": 24, "pilot": 2},
  "seeds": {"formal": [1001, 1002, 1003, 1004, 1005], "pilot": [9101, 9102]},
  "concurrency": {"target": 8, "fallback": 4, "threads_per_cell": 2},
  "engines": {
    "duckdb": {"role": "target", "version": "1.5.5", "old": "1.1.3", "session": null},
    "datafusion": {"role": "target", "version": "54.0.0", "old": "50.0.0", "session": "S17"},
    "postgres": {"role": "target", "version": "16.15", "old": "15", "session": "S16"},
    "sqlite": {"role": "target", "version": "3.51.0", "old": null, "session": "S17"},
    "tidb": {"role": "target", "version": "8.5", "old": "7.5", "session": "S18"},
    "mysql": {"role": "target", "version": "8.4", "old": "8.0", "session": "S18"},
    "mariadb": {"role": "reference", "version": "11.8", "old": null, "session": "S18"}
  },
  "arms": {
    "full": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "nollm": {"kind": "surprise"},
    "pure_llm": {"kind": "pure_llm", "llm": {"cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "sqlancer": {"kind": "sqlancer", "needs": {"run": "S15"}},
    "A2": {"kind": "surprise", "hunter": "random", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A3": {"kind": "surprise", "hunter": "random"},
    "A4": {"kind": "surprise", "freeze": "theory"},
    "A5": {"kind": "surprise", "freeze": "diagnoser"},
    "A6": {"kind": "surprise", "llm": {"roles": ["conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A7": {"kind": "surprise", "llm": {"roles": ["implementer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A8": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A9": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A10": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "vocab_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A11": {"kind": "surprise", "tier": "strong", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15", "tier": "S15"}},
    "A12": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A13": {"kind": "surprise", "llm": {"roles": ["implementer", "conjecturer", "prior", "vocab_inventor", "oracle_inventor"], "cache": "per-cell", "max_calls": "unlimited"}, "needs": {"llm.max_calls": "S15"}},
    "A14": {"kind": "surprise", "theory_from": "E1:full@early|mid|late", "select_from": "E1:full@early|mid|late", "pairs": 9, "hours": 1}
  },
  "milestones": [
    {"id": "E1", "name": "DuckDB main comparison", "run_session": "S19", "requires": ["S14", "S15"],
     "groups": [{"engine_sets": [["duckdb"]], "arms": ["full", "nollm", "pure_llm", "sqlancer"]}],
     "cells_24h": 20, "cells_1h": 0},
    {"id": "E2", "name": "PostgreSQL", "run_session": "S20", "requires": ["S14", "S15", "S16"],
     "groups": [{"engine_sets": [["postgres"]], "arms": ["full", "nollm", "pure_llm", "sqlancer"]}],
     "cells_24h": 20, "cells_1h": 0},
    {"id": "E3", "name": "DuckDB mechanisms", "run_session": "S21", "requires": ["S14", "S15", "E1"],
     "groups": [{"engine_sets": [["duckdb"]], "arms": ["A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11"]},
                {"engine_sets": [["duckdb"]], "arms": ["A14"]}],
     "cells_24h": 50, "cells_1h": 45},
    {"id": "E4", "name": "DuckDB recall", "run_session": "S22", "requires": ["S14", "S15"],
     "groups": [{"engine_sets": [["duckdb"]], "version": "1.1.3", "arms": ["full", "nollm", "pure_llm", "sqlancer"]}],
     "cells_24h": 20, "cells_1h": 0},
    {"id": "E5", "name": "embedded engines", "run_session": "S23", "requires": ["S14", "S15", "S16", "S17"],
     "groups": [{"engine_sets": [["datafusion"], ["sqlite"]], "arms": ["full", "nollm", "pure_llm", "sqlancer"], "unverified": ["sqlancer@datafusion"]},
                {"engine_sets": [["duckdb", "datafusion", "sqlite"]], "arms": ["A12", "A13"]},
                {"engine_sets": [["sqlite"]], "arms": ["A3", "A4", "A5"]}],
     "cells_24h": 65, "cells_1h": 0},
    {"id": "E6", "name": "TiDB and MySQL", "run_session": "S24", "requires": ["S14", "S15", "S16", "S17", "S18"],
     "groups": [{"engine_sets": [["tidb"], ["mysql"]], "arms": ["full", "nollm", "pure_llm", "sqlancer"]}],
     "cells_24h": 40, "cells_1h": 0},
    {"id": "E7", "name": "final report", "run_session": "S25", "requires": ["E1", "E2", "E3", "E4", "E5", "E6"],
     "groups": [], "cells_24h": 0, "cells_1h": 0}
  ],
  "totals": {"cells_24h": 215, "cells_1h": 45}
}
```
