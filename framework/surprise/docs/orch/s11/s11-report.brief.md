角色：执行者

# 工作包 s11-report：一条命令生成 RQ1–RQ6 的指标、统计检验与图

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-report`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（已合并：`s11-fixes`、`s11-runmetrics`（`metrics/rq.py` 的 `run_metrics`、`old_metrics`、`ciao` 等）、`s11-purellm`、`s11-grid`（`experiments/grid.py` 的网格目录布局、`baselines/sqlancer.py`））。与你并行的有 `s11-arms`（loop 的 `--freeze` 等开关，`config.json` 的 `"arm"` 键）与 `s11-dedup`（`metrics/dedup.py`、`metrics/coverage.py`，输出格式见它们的说明，报告只把它们的 JSON 原样放进 `extras`）；你的测试不依赖这两个包
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节；门槛的出口要求是"RQ1–RQ6 指标与图一条命令生成"
- 依赖：上面这些已合并的包。先读 `metrics/rq.py`（每格的指标从哪来、键名）与 `experiments/grid.py`（网格目录布局、`grid.json`、`cell.json`）。

## 目标

门槛 `gates/s11.py` 的 `stats` 组与 `grid` 组（后半段）验收本包。**先把这两组的代码完整读一遍，它们就是验收标准。**

### 1. `framework/surprise/metrics/stats.py`

- `median(values) -> float | None`：空为 None；偶数个取中间两个的平均。
- `summarize(values) -> {"n", "median", "min", "max"}`：先去掉 None；空时后三项为 None。
- `a12(x, y) -> float | None`：Vargha–Delaney Â₁₂ = (x 中大于 y 的对数 + 0.5 × 相等的对数) / (len(x) × len(y))；任一为空返回 None。
- `mann_whitney_u(x, y) -> dict | None`：任一为空返回 None；否则 `{"u": U_x, "p": 双侧 p 值, "method": "exact" 或 "asymptotic"}`，其中 U_x = x 中大于 y 的对数 + 0.5 × 相等的对数。
  - 没有任何并列值、且 len(x)+len(y) ≤ 20 时用精确分布：在两组合并后的所有 `C(n, len(x))` 种分组下 U 的分布，`p = min(1, 2 × min(P(U ≤ u), P(U ≥ u)))`（与 `scipy.stats.mannwhitneyu(..., method="exact")` 相同）。用动态规划或枚举都行，n ≤ 20 时要快（毫秒级）。
  - 否则用正态近似，带并列修正与连续性修正：`μ = n₁n₂/2`，`σ = sqrt(n₁n₂/12 × ((n+1) − Σ(t³−t)/(n(n−1))))`（t 为每组并列值的个数），`z = (max(U, n₁n₂−U) − μ − 0.5)/σ`，`p = min(1, 2 × (1 − Φ(z)))`（与 scipy 的 `method="asymptotic", use_continuity=True` 一致）；σ 为 0（全部值相等）时 `p = 1.0`。
  - 只用标准库实现（`math.erfc` 求正态尾概率）；scipy 只能在测试里用来交叉核对，而且测试要在没装 scipy 时也能跑（`pytest.importorskip` 不允许——不许新增 skip；没装就不做交叉核对那一步）。门槛里有手算值与参考实现。

### 2. `framework/surprise/metrics/report.py`：一条命令

`python -m surprise.metrics.report GRID_DIR [--out DIR] [--dedup FILE] [--coverage FILE]`（`--out` 默认 `GRID_DIR/report`）；函数 `build(grid_dir, out=None, *, dedup=None, coverage=None) -> dict`。

**只读网格**：除了 `--out` 目录，不写任何东西（不在格目录里缓存 `metrics.json` 之类；门槛检查格目录没有被改）。**确定**：同一个网格算两次，`report.json` 完全相同（不写时间戳；字典键排序输出）。

做什么：

1. 读 `GRID_DIR/grid.json`（规范化后的配置）与每格的 `cell.json`。只有 status 为 `done` 的格参与统计；`failed` 的格在 `cells` 里列出、`metrics` 为 None。
2. 每格算指标：`surprise` 与 `pure_llm` 臂用 `rq.run_metrics(格目录, known=配置的 known 文件内容（有的话）, prices=配置的 prices, window=配置的 window)`；`old_coevodb` 臂用 `rq.old_metrics(格目录)`。`sqlancer` 臂（如果配置里有）没有格，用 `baselines.sqlancer.metrics(load(summary), engine)` 作为它唯一的一行。
3. 每个 RQ 一组**标量指标**（每格一个数，取不到为 None），按臂汇总成 `stats.summarize`：

| RQ | 标量指标（名字照写）| 取自 `run_metrics` |
|---|---|---|
| rq1 | `family_count`、`families_per_1000`、`families_per_hour`、`first_family_minutes`、`duplicate_rate` | `rq1.*`；`first_family_minutes` = `rq1.first_family.elapsed_s / 60` |
| rq2 | `brier`、`brier_reference`、`high_surprise_share`、`teeth` | `rq2.brier` 等；`high_surprise_share` = `rq2.high_surprise.share`；`teeth` = `len(rq2.teeth)` |
| rq3 | `survival_rate`、`prediction_accuracy`、`calls_per_family`、`tokens_per_family`、`pure_llm_accuracy` | `rq3.conjectures.survival_rate`、`rq3.predictions.accuracy`、…、`rq3.pure_llm.accuracy` |
| rq4 | `invalid_rate`、`duplicate_rate`、`theory_length_final`、`in_out_gap`、`edits_accepted` | `rq4.invalid.rate`、…、`rq4.theory_length[-1].length`、`rq4.in_out.gap`、`rq4.edits.accepted` |
| rq6 | `recall` | `rq6.recall.recall` |

   每个 RQ 的输出：`{"metrics": [上表的名字], "arms": {臂: {指标: summarize(...)}}}`，外加：
   - `rq1["curves"]`：每格的累计家族数曲线 `[[分钟, 累计家族数], ...]`（surprise / pure_llm 格用 `rq1.families` 的 `elapsed_s`；old 格没有时间点，只给终点 `[wall_s/60, family_count]`）；
   - `rq2["calibration"]`：每臂把各格的校准分箱按区间合并（count 相加，mean_p 与 fail_rate 按 count 加权）；
   - `rq3["timeline"]`：每格的 `rq3.timeline`；
   - `rq4["theory_length"]`：每格的 `rq4.theory_length`；
   - `rq5`：`{"ciao": {格: rq5.ciao}（只取 reference 臂的格，ciao 为 None 的跳过）, "freezing": [...], "pairing": [...]}`。`freezing`：每个 `surprise` 臂里配置有 `freeze` 或 `hunter == "random"` 的臂一行 `{"arm", "freeze", "hunter", "vs": reference, "delta": {指标: 该臂中位数 − reference 中位数（任一为 None 则 None）}}`，指标取 rq1 的 `family_count`、`families_per_hour` 与 rq2 的 `brier`；`pairing`：配置有 `theory_from` 或 `select_from` 的臂一行 `{"arm", "theory_from", "select_from", "family_count": summarize, "mean_surprise": summarize(每格有效记录惊讶的均值，可用 rq2.curve 之外自己从 run_metrics 已有的数据算；算不出为 None)}`。网格里没有这类臂时两个列表为空；
   - `rq6`：外加 `{"boundary": {格: rq6.boundary}, "partition": None}`（人工划分的真值不在网格里，留空）。
4. **统计检验** `stats`：对每个 RQ 的每个标量指标、每对臂 (a, b)（a 在配置里排在 b 前面；sqlancer 臂只有一个值，也参与），一行 `{"rq", "metric", "a", "b", "n_a", "n_b", "median_a", "median_b", "u", "p", "method", "a12"}`（两组都至少有一个值才出行；`mann_whitney_u` 返回 None 时 u / p / method 为 None）。按 rq、metric、a、b 排序。
5. `external`：`{"sqlancer": sqlancer.metrics(sqlancer.load(), engine="duckdb")}`，无论配置里有没有 sqlancer 臂都写（论文对照的固定一行）。
6. `extras`：`--dedup` / `--coverage` 给的 JSON 原样放进来；也读 `GRID_DIR/extras/dedup.json` 与 `GRID_DIR/extras/coverage.json`（存在的话）。没有就省略这个键。
7. 顶层：`{"schema": 1, "grid": 配置的 name, "reference", "arms": {臂: {"kind", "cells": [格名...], "options": 该臂的配置}}, "cells": {"<臂>/s<seed>-r<rep>": {"arm", "seed", "rep", "status", "metrics"}}, "rq1".."rq6", "stats", "external", ["extras"]}`。

写出：`OUT/report.json`（`json.dumps(..., sort_keys=True, indent=1, ensure_ascii=True)`）；`OUT/report.md`：标题 + 每个 RQ 一节（`## RQ1 发现` … `## RQ6 理论质量`，节标题里要有 `RQ1`…`RQ6` 字样），每节一张"臂 × 指标中位数（n）"的表，加该 RQ 的检验结果（p 与 Â₁₂）和对应图的相对链接；外加对照组（SQLancer 一行）与附加结果（去重、覆盖度）两节；`OUT/figures/` 下 7 张 PNG（matplotlib，`Agg` 后端，确定的尺寸与 dpi，不依赖显示器）：

| 文件 | 内容 |
|---|---|
| `rq1_families.png` | 累计家族数随墙钟分钟的曲线，每格一条，按臂着色，图例为臂名 |
| `rq2_surprise.png` | reference 臂各格的惊讶曲线（窗口 = 配置的 window），标出齿 |
| `rq2_calibration.png` | 每臂的校准曲线（合并分箱的 mean_p 对 fail_rate）与对角线 |
| `rq3_llm.png` | LLM 预测累计准确率随 seq 的变化（每格一条）；没有 LLM 的网格画一张写着 "no LLM predictions in this grid" 的空图 |
| `rq4_quality.png` | 每臂的无效率与重复率中位数（分组柱状图）|
| `rq5_ciao.png` | reference 臂第一格的 CIAO 热图（行 = 理论代，列 = 批，数值标在格里）；没有就画空图说明 |
| `rq6_recall.png` | 每臂的召回中位数柱状图；没有 known 文件时画空图说明 |

空图也要是正常的 PNG（门槛要求每张大于 1000 字节、以 PNG 签名开头）。颜色按臂固定（臂在配置里的顺序对应调色板的顺序），图里的文字一律英文。

### 3. 顺带的一处小修：`framework/surprise/experiments/grid.py`

`s11-grid` 合并时留下一处与说明不符：`surprise` 臂的 `hunter` 只接受 `"random"`（`_HUNTER_OK = ("random",)`），显式写默认值 `"value"` 会被 `load_config` 拒绝。改成接受 `"value"` 与 `"random"`；`"value"` 与不写等价（不给 loop 传 `--hunter`）。在 `framework/tests/test_surprise_s11_grid.py` 里加一条测试。grid.py 别的地方一个字都不改。

## 允许改动的路径

```allow-paths
framework/surprise/metrics/stats.py
framework/surprise/metrics/report.py
framework/tests/test_surprise_s11_report.py
framework/surprise/experiments/grid.py
framework/tests/test_surprise_s11_grid.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `metrics/` 下别的文件、`experiments/`（除上面第 3 节那一处）、`baselines/` 等；旧代码不碰（`scripts/final_report.py` 等可以读来参考，不导入）。
- 报告只读网格：不重跑实验，不调用 LLM，不执行 SQL，只写 `--out` 目录。
- 不靠改测试让测试通过：不新增 skip / xfail（包括 `importorskip`），不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 本包不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                   # 通过数不少于基线，0 failed
python -m surprise.gates.s11 --only stats grid      # 两组 PASS（grid 真跑 4 格 x 1 分钟，约 7 分钟）
```

新测试：`stats` 的每个函数（手算值；有 scipy 时交叉核对）；`report.build` 在一个手工造的小网格上（两个臂、各两格；格目录用很短的真实 `loop.run`、手写的 `old_run.json` + `bugs.jsonl`）——检查各键、汇总、检验行、只读、确定、7 张图存在。测试总时长控制在 4 分钟以内。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-report

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
