角色：执行者

# 工作包 s11-runmetrics：从一次运行的账本算出 RQ1–RQ6 的全部单次运行指标

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-runmetrics`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（门槛 `framework/surprise/gates/s11.py` 与 `s11_cases.py` 已经写好）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节、`PLAN.md` 第 5 节 Phase 6
- 依赖：无。与你并行的有 `s11-fixes`（会给 `metrics/dups.py` 加 `run_registry(run_dir)`、给 `new_families` 加 `registry=` 参数）与 `s11-purellm`（`baselines/pure_llm.py`）。**你不改 `dups.py`、`recall.py`、`curve.py`**；需要按运行的词表打开理论时，在你自己的 `rundata.py` 里读 `config.json` 的 `"vocabulary"`（见下文），需要 `new_families` 时把 `Workbench` 自己打开后照它的规则算（或者调用时只在默认词表的运行上调用它）——两包合并后由编排者统一。

## 目标

评估一律从账本算（PLAN 第 1 节第 5 条）。本包交付"给一个运行目录，算出它的全部指标"的库，供之后的网格报告逐格调用。研究问题与指标（来自框架文档《惊讶驱动的 CoevoDB：新框架与故事》的"评估设计"一节）：

| RQ | 回答什么 | 主要指标 |
|---|---|---|
| RQ1 发现 | 追逐惊讶是否更快找到新的 bug 家族 | 每千次执行的新家族数；首个家族用时；新家族总数；重复报告率 |
| RQ2 校准 | P_T 是否可信，高惊讶是否指向新东西 | 预测的 Brier 分数与校准曲线；高惊讶样本中新家族的比例；惊讶曲线的形状 |
| RQ3 LLM 猜想 | 猜想多少经受住反驳、带来多少发现 | 猜想存活率；经由 LLM 新特征、新 oracle、迁移翻译发现的家族数；每个家族的 LLM 调用数与 token |
| RQ4 Harness | 约束的作用 | 重复率；无效率；理论长度；留入与留出的差距 |
| RQ5 协同进化 | 两侧是否互相推动 | CIAO 矩阵（第 i 代理论算第 j 批测试的平均惊讶）；冻结一侧后的曲线；跨代配对 |
| RQ6 理论质量 | 假设是否对应真实故障 | 假设边界与上游修复范围的吻合度；已知 bug 召回；家族划分与人工判定的一致性 |

门槛 `gates/s11.py` 的 `constants`（metrics 部分）、`runmetrics`、`ciao`、`llm_metrics`、`rq6` 五组验收本包，`vocabulary` 组的后半段也用到本包。**先把这几组的代码完整读一遍：门槛里有一份独立的参考计算（`ref_*` 函数），你的实现必须与它逐项一致。** 下文与门槛代码不一致时以门槛代码为准，并在报告里写明。

### 交付的模块（全部新建，都在 `framework/surprise/metrics/` 下）

#### `constants.py`

```python
HIGH_SURPRISE_BITS = 4.0
CALIBRATION_EDGES = (0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0)
CIAO_MAX_GENERATIONS = 12
CIAO_BATCH_SAMPLE = 200
CURVE_WINDOW = 100
TEETH_AMPLITUDE = 0.25
TEETH_WIDTH = 5
def as_dict() -> dict  # 上面七个常数，值保持 Python 类型（元组仍是元组）
```

每个常数配一行英文注释说明含义。

#### `rundata.py`：读一个运行目录

`RunData.open(path)` 读出：

- `path`、`config`（`config.json`）、`report`（`report.json`，没有则 None）、`progress`（`progress.jsonl` 的行列表，没有则空）、`manifest` 与 `records`（`ledger.sqlite` 里唯一一个 run 的 manifest 与全部 `ExperimentRecord`，按 `seq` 升序；用 `surprise.harness.ledger.Ledger`，读完就关）；
- `kind`：manifest 里 `"baseline" == "pure_llm"` 时为 `"pure_llm"`，否则 `"surprise"`；
- `registry`：`config.json` 有 `"vocabulary"` 时 `Registry.load(该路径)`，否则 `default_registry()`；
- `workbench()`：有 `theory/` 时 `Workbench.open(path/"theory", registry=self.registry)`（只打开一次、缓存），否则 None；
- `book(name)`：`llm/<name>.jsonl` 的行列表（没有文件返回空列表），例如 `book("conjectures")`、`book("calls")`；
- `row(record_id)`：该记录的 progress 行（没有则 None）。

**整个 metrics 层只读不写**：打开运行目录不能改动其中任何文件（门槛对目录逐文件取哈希比对）。

#### `rq.py`：指标

公共函数（门槛直接调用其中几个）：

- `label_key(record) -> str | None`：失败且 `label.cve["profile"]["status"] == "ran"` 时，返回 `dups.identity_key(record.case.engine, profile["fix_set"], label.fail_kind, label.identity.error_class, behavior_shape(label.identity.behavior))`（`behavior_shape` 来自 `surprise.harness.cve.shape`）；否则 None。
- `ledger_families(records, progress=None) -> list[dict]`：按 seq 顺序，每个 `label_key` 第一次出现记一行 `{"key", "record_id", "seq", "elapsed_s"}`（`elapsed_s` 取该记录 progress 行的 `elapsed_s`，没有 progress 时为 None）。这是跨臂统一的"家族"口径：不依赖理论，任何写账本的臂都能算。
- `theory_lengths(wb) -> list[dict]`：每个已关闭的代一行 `{"generation": g, "length": theory_length(wb.store.load_generation(g)), "hypotheses": 假设数, "live": False}`，最后加当前活理论一行 `{"generation": wb.generation, "length": theory_length(wb.theory), "hypotheses": ..., "live": True}`（`theory_length` 来自 `surprise.theory.length`）。
- `ciao(wb, *, max_generations=CIAO_MAX_GENERATIONS, sample=CIAO_BATCH_SAMPLE) -> dict | None`：见下文；没有任何有效观察时返回 None。
- `run_metrics(run_dir, *, known=None, prices=None, window=None) -> dict`：见下文。
- `old_metrics(old_dir) -> dict`：原 CoevoDB 的一次运行（`surprise.baselines.old_no_llm` 写的目录，含 `old_run.json`），见下文。

**CIAO 的定义**（门槛 `ref_batches`、`ref_spread`、`ref_sample` 是参考实现）：

- 代：已关闭的代 `0 .. wb.generation-1` 加上当前打开的代 `wb.generation`，共 `total = wb.generation + 1` 个。打开的代用活理论（`wb.surprise_under(wb.generation, ids)` 已经这样处理）。
- 第 j 批：第 j 代打开期间被观察的**有效**记录（标签不是 invalid）。从 `wb.store.journal()` 里 `kind == "observe"` 的行判定：第 j 代的关闭点是 `wb.store.generations()[j]["journal_seq"]`，一条观察属于"关闭点小于它的 seq 的代的个数"那一代。批内保持日志顺序。
- 选代：`total <= max_generations` 时全选；否则取 `floor(k*(total-1)/(max_generations-1) + 0.5)`，k = 0..max_generations-1（去重，保持顺序）。行（理论）与列（批）用同一组代。
- 批抽样：批内超过 `sample` 条时按同样的均匀取法取 `sample` 条，否则全取。
- `matrix[a][b] = wb.surprise_under(gens[a], 抽样后的第 gens[b] 批)`；批为空时为 None。
- 返回 `{"generations": gens, "batches": gens, "matrix": matrix, "diagonal_mean", "below_mean", "above_mean"}`：三个均值分别是对角线、`a > b`（新理论看旧批）、`a < b`（旧理论看新批）上非 None 值的平均（没有值为 None）。Red Queen 的标志是 below 低于 diagonal 而 diagonal 仍大于零。
- 性能：S8 的长跑有 96 代、9500 条记录，`ciao` 在它上面必须几分钟内算完（门槛的 `ciao` 组就是在它上面跑）。

**`run_metrics` 的返回值**（键名、嵌套、类型都要照写；门槛逐项比对）：

```
{
 "run":  {"run_id", "kind", "seed", "engines", "oracles", "status", "experiments", "wall_s", "arm", "llm_roles"},
 "rq1":  {"executions", "families", "family_count", "families_per_1000", "families_per_hour",
          "first_family", "theory_families", "duplicate_rate"},
 "rq2":  {"valid", "brier", "brier_reference", "calibration", "high_surprise", "window", "curve", "teeth"},
 "rq3":  {"conjectures", "predictions", "translations", "timeline", "families_via", "calls",
          "calls_per_family", "tokens_per_family", "pure_llm"},
 "rq4":  {"invalid", "duplicate_rate", "theory_length", "edits", "in_out"},
 "rq5":  {"ciao", "arm"},
 "rq6":  {"recall", "boundary"},
 "cost": {"executions", "wall_s", "llm_calls", "input_tokens", "output_tokens", "usd", "per_family"}
}
```

逐项定义（记录 = 账本里该 run 的全部记录，按 seq）：

- `run`：`run_id`、`seed`、`engines`、`oracles`、`status`（report 的）、`experiments` = 记录条数、`wall_s`（report 的，没有为 None）、`kind`、`arm` = `config.get("arm")`（之后的 `s11-arms` 包会往 config 里写 `"arm"`；没有为 None）、`llm_roles` = `config.get("llm", {}).get("roles", [])`。纯 LLM 基线的 config 字段见 `s11-purellm`（`engine` 单数）：`engines` 取 `[config["engine"]]`。
- `rq1`：
  - `executions` = 记录条数（含 invalid）；`families` = `ledger_families(records, progress)`；`family_count` = 其长度；
  - `families_per_1000` = `1000 * family_count / executions`（executions 为 0 时 None）；
  - `families_per_hour` = `family_count / (wall_s / 3600)`（wall_s 缺或为 0 时 None）；
  - `first_family` = `{"seq", "elapsed_s"}` 取 `families[0]`，没有家族为 None；
  - `theory_families`：有理论且没冻结理论（`arm` 为 None 或 `arm.get("freeze") != "theory"`）时，为该运行理论的家族键列表——口径同 `dups.new_families(store_dir)` 返回各行的 `"key"`（用本运行的词表打开）；否则 None；
  - `duplicate_rate`：`theory_families` 非 None 时 = `dups.duplicate_rate(theory_families)`（S8 的口径）；否则 = 全部"有画像的失败"的键序列（按 seq，含重复）的 `duplicate_rate`。
- `rq2`（有效记录 = `y` 是 pass / fail 且 `p_t` 不是 None）：
  - `valid` = 有效记录数；`brier` = 有效记录上 `(p_t - [y==fail])²` 的均值；`brier_reference` = `r(1-r)`，r 为有效记录的失败率（同一批记录上的常数预测者）；没有有效记录时两者 None；
  - `calibration`：`CALIBRATION_EDGES` 相邻两点一个区间，左闭右开，最后一个区间右端也闭；每个区间 `{"lo", "hi", "count", "mean_p", "fail_rate"}`，空区间 `mean_p`、`fail_rate` 为 None；所有区间都列出；
  - `high_surprise` = `{"threshold": HIGH_SURPRISE_BITS, "count", "new_family", "share"}`：惊讶（`surprise.theory.predict.surprise_bits(p_t, y)`，invalid 或无 p_t 不计）不小于阈值的记录数、其中 progress 行 `triage == "new_family"` 的条数、比例（count 为 0 时 None）；
  - `window` = 参数 `window`，None 时用 `CURVE_WINDOW`；`curve` = `curve.surprise_curve(records, window)`；`teeth` = `curve.teeth(curve, TEETH_AMPLITUDE, TEETH_WIDTH)`。
- `rq3`（读 `llm/` 下的账本；没有这些文件时各计数为 0、比例为 None、列表为空）：
  - `conjectures`：`book("conjectures")` 中 `type == "conjecture"` 的行，`registered` = status 为 registered 的个数、`rejected` = status 为 rejected 的个数；`type == "settle"` 的行给出每条预测的结算（state 为 kept / broken / void）；`with_settled` = 至少有一条 kept 或 broken 的已登记猜想数；`survived` = 其中没有任何 broken 的个数；`survival_rate` = survived / with_settled；
  - `predictions` = `{"total": 已登记猜想的预测条数之和, "kept", "broken", "void", "open": total-kept-broken-void, "accuracy": kept/(kept+broken)}`；
  - `translations`：`book("translations")` 里迁移翻译者的结算，`{"total", "kept", "broken", "accuracy"}`（读一下 `roles/translator.py` 写的行格式；没有结算为 0 / None）；
  - `timeline`：猜想与翻译的每条 kept / broken 结算一行 `{"seq": 结算它的记录的 seq, "source": "conjecture" 或 "translation", "kept": bool, "accuracy": 到这一行为止的累计准确率}`，按 seq 升序（同 seq 保持账本顺序，猜想在前）。这就是"LLM 预测准确率随时间的变化"；
  - `families_via`：对 `ledger_families` 的每个家族，看开出它的记录的 progress 行：`lane` 为 `implement` / `bet` / `translate` 分别计入同名键；`rule` 以 `llm:` 开头计入 `llm_rule`（新 oracle）；记录的 φ 含本运行词表里 LLM 发明的特征（注册表里 `source` 以 `llm` 开头的特征）计入 `invented_feature`。五个键都要有；
  - `calls`：`book("calls")` 按 `role` 汇总 `{"calls", "network", "input_tokens", "output_tokens"}`（`network` = `source == "network"` 的行数），外加总计 `total`、`network`、`input_tokens`、`output_tokens`；
  - `calls_per_family` = 调用总数 / family_count，`tokens_per_family` = (输入+输出 token) / family_count（family_count 为 0 时 None）；
  - `pure_llm`：`kind == "pure_llm"` 时为 `{"total": 记录数, "kept": spec["expect"] 等于 y 的条数, "broken": spec["expect"] 是 pass/fail 且不等于 y 的条数, "accuracy"}`（LLM 自己的预测准确率），否则 None。
- `rq4`：
  - `invalid` = `{"count", "rate": count/executions, "by_reason": {invalid_reason: 条数}, "by_oracle": {oracle: 条数}}`；
  - `duplicate_rate` = 同 `rq1.duplicate_rate`；
  - `theory_length` = `theory_lengths(wb)`，没有理论为 [];
  - `edits` = `{"accepted", "rejected", "rolled_back"}`：`wb.edits()` 中各 decision 的个数；
  - `in_out`：取 decision 为 accepted 且 `surprise_delta_in`、`surprise_delta_out` 都不是 None 的编辑，`{"edits": 个数, "mean_in", "mean_out", "gap": mean_out - mean_in}`；没有这样的编辑时 `{"edits": 0, "mean_in": None, "mean_out": None, "gap": None}`。（delta = 编辑后减编辑前的惊讶总和，负数是变好；gap 为正说明留出上不如留入。）
- `rq5`：`{"ciao": ciao(wb)（没有理论为 None）, "arm": config.get("arm")}`。
- `rq6`：
  - `recall`：传入 `known` 时 = `surprise.metrics.recall.score(known, run_dir/"theory")` 的结果（扩展词表的运行要用本运行的词表；合并 `s11-fixes` 之后 `score` 会有 `registry=` 参数），否则 None；
  - `boundary`：见 `boundary.py`；没有理论为 None。
- `cost`：`executions`、`wall_s`、`llm_calls` = `rq3.calls.total`、`input_tokens`、`output_tokens`、`usd`（传入 `prices`（`{模型名: {"input": 美元每百万 token, "output": ...}}`）时按 `calls.jsonl` 每行的 `model` 计价，否则 None）、`per_family` = `{"executions": executions/family_count, "llm_calls", "tokens", "usd"}`（family_count 为 0 时各为 None）。

`run_metrics` 必须是确定的：同一个目录算两次结果相等（不放当前时间之类的东西）。

`old_metrics(old_dir)`：读 `old_run.json` 与其中 `run_dir` 下的 `bugs.jsonl`（用 `dups.old_reports`），返回与 `run_metrics` 同样的顶层键，其中：`run` = `{"kind": "old_coevodb", "seed", "mode", "status": old_run["ended"], "wall_s", ...其余为 None}`；`rq1` 的 `families` = 报告键第一次出现的位置 `{"key", "record_id": root_key, "seq": 报告序号(从 1 起), "elapsed_s": None}`，`executions` 与 `families_per_1000` 为 None，`families_per_hour` 照算，`theory_families` None，`duplicate_rate` = `dups.duplicate_rate(全部报告键)`；`rq2`..`rq6` 为 None；`cost` 只有 `wall_s`，其余 None。

#### `boundary.py`：假设边界与上游修复范围的吻合度（RQ6）

- `classify(specific: set, conditions: set) -> str`：相等 `"match"`；specific 是 conditions 的真子集 `"too_wide"`（假设要求的条件更少，覆盖得比修复范围宽）；真超集 `"too_narrow"`；其余 `"mixed"`。
- `load_fix_conditions(path=None) -> list[dict]`：默认读 `framework/surprise/metrics/data/fix_conditions.json`（随包分发的数据文件）。格式 `{"schema": 1, "entries": [...]}`，每条 `{"name", "engine", "key", "fix", "evidence", "conditions": [φ 特征名...]}`；校验：每个字段齐全、conditions 非空且都是默认词表里已知的特征（`default_registry().known`）。
- `compare(wb, families) -> list[dict]`：对每条修复条件，找键（同 `dups.new_families` 的 key）等于它的理论家族；有就取该家族第一个假设的 `specific`，输出 `{"name", "family", "classification", "missing": 排序后的 conditions−specific, "extra": 排序后的 specific−conditions}`；没有匹配的条目不输出。`run_metrics` 的 `rq6.boundary` 用它。

`data/fix_conditions.json` 的内容照抄下面（这是编排者从上游 PR 定下的真值，不要改动、不要自己加条目）：

```json
{
 "schema": 1,
 "entries": [
  {
   "name": "F2",
   "engine": "duckdb",
   "key": "fix|duckdb|window_self_join",
   "fix": "https://github.com/duckdb/duckdb/pull/24685",
   "evidence": "PR 'Compare window partitions as sets' (fixes duckdb/duckdb#24629): PartitionsAreEquivalent compared two window expressions' PARTITION BY lists by length plus one-directional membership, so 'a, a' matched 'a, b'. Triggering needs two or more window expressions with PARTITION BY and a duplicated partition key. See docs/UPSTREAM_ISSUES.md item 16.",
   "conditions": ["ast:window_spec:partition", "ast:window_trait:dup_partition_key", "ast:window_trait:multiple"]
  }
 ]
}
```

#### `partition.py`：两种家族划分的成对一致性（RQ6 的"家族划分与人工判定的一致性"）

`pair_agreement(pred: Mapping, truth: Mapping) -> dict`：只看两个映射共有的项；`pred` 里值为 None 的项各自单独成类。对所有无序项对：两边都同类为 TP，只在 pred 同类为 FP，只在 truth 同类为 FN，都不同类为 TN。返回 `{"items", "tp", "fp", "fn", "tn", "precision", "recall", "f1", "ari"}`（分母为 0 时对应值为 None；ari 是调整兰德指数，分母为 0 时为 None）。门槛有手算的例子。

### 其它要求

- 不改 `metrics/` 下现有的 `curve.py`、`dups.py`、`recall.py`（它们由别的包或旧门槛管）；复用它们的函数。
- 只读：所有函数都不写运行目录。
- 读大账本要省内存：S8 长跑的 `ledger.sqlite` 有 558 MB；`ciao` 只需要理论存储，不要为了它去读账本。

## 允许改动的路径

```allow-paths
framework/surprise/metrics/constants.py
framework/surprise/metrics/rundata.py
framework/surprise/metrics/rq.py
framework/surprise/metrics/boundary.py
framework/surprise/metrics/partition.py
framework/surprise/metrics/data/fix_conditions.json
framework/tests/test_surprise_s11_metrics.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `metrics/` 下现有文件、`theory/`、`experiments/`、`hunter/`、`diagnoser/`、`roles/`、`features/`。旧代码（`framework/surprise/` 以外）不碰。
- 指标只从账本、progress、理论存储与 `llm/` 账本算；不调用 LLM，不执行 SQL（`recall.score` 只读理论，不在此列）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告；本包不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。门槛的 `ciao` 组读主检出区的 S8 长跑产物（`framework/results/s08/longrun`，不入库）；你的 worktree 里没有它，见"验收命令"。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                # 通过数不少于 774，0 failed
python -m surprise.gates.s11 --only runmetrics llm_metrics rq6   # 三组 PASS
python -m surprise.gates.s11 --only constants                    # 预期 FAIL：缺 surprise.baselines.pure_llm 等别的包的东西；报告里贴出失败行，确认 metrics 常数那几行没有报错
```

`ciao` 组要读 `framework/results/s08/longrun`（只在主检出区）。在 worktree 里做法：设环境变量后用一个临时脚本按门槛的方式调用——不要复制或链接那个目录。最简单的办法是在报告里写明"ciao 组未在 worktree 运行"，并用你自己造的多代小理论（例如在测试里用 `Workbench` 观察三百条合成记录、每 100 条 `checkpoint`）测试 `ciao` 与 `theory_lengths`；编排者审查时在主检出区跑 `ciao` 组。

新测试放在 `framework/tests/test_surprise_s11_metrics.py`，覆盖：`label_key`、`ledger_families`、Brier 与校准分箱的边界（p 恰好等于 0.95 和 1.0）、高惊讶、`theory_lengths`、`ciao`（多代、选代、抽样、空批）、RQ3 各项（用手写的 `llm/*.jsonl` 小样本）、`classify`、`load_fix_conditions` 的校验、`pair_agreement`、`old_metrics`、只读（前后目录哈希一致）。可以用一次很短的真实 `loop.run`（几条实验）当夹具；测试总时长控制在 3 分钟以内。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-runmetrics

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
