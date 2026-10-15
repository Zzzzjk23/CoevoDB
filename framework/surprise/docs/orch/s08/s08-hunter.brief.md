角色：执行者

# 工作包 s08-hunter：Hunter（四条车道的候选、按期望惊讶打分、探索保底、降权、新颖性拒绝、常驻 φ 提取进程）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s08-hunter`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s08`（`s07-done-r2` 之后加了 S8 的门槛 `framework/surprise/gates/s08.py` 与 `s08_cases.py`）
- 所属会话：S8（Phase 4：Hunter 与无 LLM 闭环，里程碑 M2），范围见 `framework/surprise/docs/SESSIONS.md` 的 S8 一节
- 依赖：S5 的 `surprise.features`、S6/S7 的 `surprise.theory`（`Workbench`、`Theory.predict`、`position`、`reduce_conjunction`、`Spec`、`Residual.counts` / `rate`）、冻结的 `surprise.harness`。先读 `framework/surprise/theory/workbench.py`、`theory/theory.py`、`theory/hypothesis.py`、`features/__init__.py`、`features/extract.py`、`features/units.py`、`features/registry.py`。旧代码 `framework/evolution/dce.py`（`mutate_query_text`、`mutate_setup`）、`framework/seeds/mutate.py`（`SeedMutator`）、`framework/seeds/store.py`（`SeedCorpus`）只调用、不改
- 同时有另一个执行者在做 `s08-eval`（`surprise/metrics/`、`surprise/baselines/`），与本包不重叠；主循环与 Diagnoser 在你之后的 `s08-loop` 包里做，本包不做

## 目标

依据 `framework/surprise/docs/PLAN.md` 第 5 节 Phase 4（"四类候选、value = P_valid × (D + β·U)、探索保底、降权与新颖性拒绝采样"）与 SESSIONS 的 S8 一节。框架文档的原话：

- "Hunter 最大化期望惊讶，也就是对理论的期望信息增益：value = P_valid × (D + β·U)。D 是版本空间分歧：规格落在某个假设的待定区时接近 1 比特。U 是残余不确定性：由 R 做乐观估计，和已知假设相邻的单元先验更高。"
- "候选分四类，全部由 T 生成：细化（删一个特征）、泛化（换同类取值）、迁移（换引擎）、探索（没测过的单元，只抽样不枚举）。"
- "细化和泛化用变异算子实现，不调 LLM；……给探索留保底名额。" 迁移在无 LLM 时只做字面改写。
- 防止多样性坍缩："未知度项、探索保底名额、给派生探针过多的假设降权、按 φ 做新颖性拒绝采样"。

交付新包 `framework/surprise/hunter/`（目录已有一个空的 `__init__.py`），外加 `theory/constants.py` 里一个新常数。全部是纯逻辑加 φ 提取：不执行被测语句（执行与打标签是下一个包的主循环调 `evaluate_final` 做的），不调用任何模型，不导入 `agents`、`llm`、`guidelines`、`evolution.co_evolution`、`openai`、`httpx`。同样的输入与种子得到同样的候选、同样的选择。

验收以 `framework/surprise/gates/s08.py` 的 `no_llm`（本包的那部分）、`scoring`、`operators`、`candidates` 四组为准（`no_llm` 会同时导入 `surprise.metrics`、`surprise.baselines`、`surprise.diagnoser`、`surprise.experiments.loop`，它们不归你，在你的 worktree 里这一组会因为缺模块而失败，这是预期的；你自己用第 8 节的命令核对本包的部分）。先把 `gates/s08.py` 与 `gates/s08_cases.py` 读一遍：门槛用到的名字、参数、返回值、字段都在下面写明，照写。

### 1. 常数

`framework/surprise/theory/constants.py` 末尾加一个常数（照这个格式带一行注释），别的不动：

```python
# Weight of the residual uncertainty U against the version-space disagreement D in the Hunter's value.
# Provisional; S8 fixes it once with a pre-experiment on independent seeds (PLAN decision 8).
BETA = 1.0
```

新文件 `framework/surprise/hunter/constants.py`，写法照 `theory/constants.py`（每个常数一行注释、`as_dict()` 收集全部公开大写名字并做 JSON 往返）：

```python
EXPLORE_SEEDS_PER_STEP = 6      # seeds sampled per engine per step for the explore lane
SEED_MUTATIONS_PER_SEED = 1     # SeedMutator mutations per sampled seed
PARENTS_PER_HYPOTHESIS = 3      # most recent positives of a hypothesis used as parents
MUTANTS_PER_STEP = 48           # mutants examined per step, shared out over hypotheses
MIGRATE_PER_STEP = 8            # migrate candidates kept per step
EXPLORE_EVERY = 5               # every fifth choice is an exploration slot
PROBE_HALF = 50.0               # downweight 1 / (1 + probes / PROBE_HALF)
NOVELTY_WINDOW = 200            # recent experiments of the same scope a candidate is compared with
NOVELTY_FLOOR = 0.2             # acceptance probability of a candidate with zero novelty
ADJACENT_FACTOR = 2.0           # optimistic rate multiplier for a unit next to a known hypothesis
PHI_TIMEOUT_S = 30.0            # wall-clock limit of one phi extraction in the worker process
```

类型必须与上面一致（`PROBE_HALF`、`NOVELTY_FLOOR`、`ADJACENT_FACTOR`、`PHI_TIMEOUT_S` 是 float，其余是 int）。

### 2. 打分（`hunter/scoring.py`，纯函数）

```python
def binary_entropy(p: float) -> float          # 比特；p <= 0 或 p >= 1 时返回 0.0
def optimistic_rate(tested: int, unexplained: int) -> float
    # rho = (unexplained + RESIDUAL_PRIOR_FAILS) / (tested + RESIDUAL_PRIOR_TESTS)   （与 Residual.rate 同一个式子，常数从 theory.constants 读）
    # 返回 min(0.5, rho + sqrt(rho * (1 - rho) / (tested + 1)))
def uncertainty(tested: int, unexplained: int, adjacent: bool) -> float
    # r = optimistic_rate(...)；adjacent 时 r = min(0.5, ADJACENT_FACTOR * r)；返回 binary_entropy(r)
def disagreement(zone: str) -> float           # zone == "pending" 为 1.0，"confirmed" / "unexplored" 为 0.0；别的值 ValueError
def downweight(probes: int) -> float           # 1.0 / (1.0 + probes / PROBE_HALF)
def value(p_invalid: float, D: float, U: float, beta: float, probes: int) -> float
    # (1 - p_invalid) * (D + beta * U) * downweight(probes)
def jaccard(a: frozenset, b: frozenset) -> float     # |a ∩ b| / |a ∪ b|；两个都空为 1.0
def novelty(features: frozenset, recent: Iterable[frozenset]) -> float   # 1 - max jaccard；recent 为空为 1.0
def accept_probability(nov: float) -> float    # NOVELTY_FLOOR + (1 - NOVELTY_FLOOR) * nov
def is_explore_slot(index: int) -> bool        # index >= 1 且 index % EXPLORE_EVERY == 0
def adjacent(unit: str, units: Iterable[str]) -> bool
    # unit 的形状是 unit_of 给的 "engine|oracle|construct|plan|data"。
    # unit 不在 units 里，并且 units 里有某个 u 与它引擎相同（第 0 段）且主构造相同（第 2 段），为 True；否则 False
def hypothesis_units(wb, registry=None) -> frozenset[str]
    # 理论里每个假设的每个正例（E⁺ 的记录编号）在 wb.records() 里找到对应的 Seen，取 unit_of(seen.phi, seen.label.oracle, registry)。
    # 找不到的编号跳过。registry 为 None 时建一个默认词表（整次调用只建一个）
def score(wb, phi, oracle, *, beta: float, probes: Mapping[str, int], units: Collection[str]) -> Score
```

`Score` 是冻结 dataclass，字段依次 `prediction`（`wb.predict(phi, oracle)`）、`D`、`U`、`adjacent`、`probes`、`value`：

- `D = disagreement(prediction.zone)`。
- 只有 `prediction.zone == "unexplored"` 时才算 U：`tested, unexplained = wb.theory.residual.counts(prediction.unit)`，`adjacent = adjacent(prediction.unit, units)`，`U = uncertainty(tested, unexplained, adjacent)`；其余位置 `U = 0.0`、`adjacent = False`。
- `probes = probes.get(prediction.hypothesis_id, 0)`（`hypothesis_id` 为 None 时为 0）。"派生探针过多的假设降权"按**负责预测的那个假设**算，不按候选来自哪条车道。
- `value = value(prediction.p_invalid, D, U, beta, probes)`。
- 返回的 float 都是 Python `float`（门槛用 `isinstance(x, float)` 比较）。

### 3. 变异算子与 oracle 选项（`hunter/operators.py`）

```python
RULES: tuple[str, ...] = tuple(surprise.harness.oracles.rewrites.RULES)   # ("double_negation", "demorgan", "case_to_coalesce")
def case_digest(case: SqlCase) -> str
    # sha256(json.dumps(case.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
def mutants(case: SqlCase) -> list[tuple[SqlCase, str]]
def oracle_options(case: SqlCase, oracles: Sequence[str]) -> list[tuple[str, str | None]]
```

`mutants` 按下面的次序产生，同一 `case_digest` 只留第一次出现的，原用例本身不算：

1. `for text, op in mutate_query_text(case.query)`：`replace(case, query=text)`，标签 `"q:" + op`；
2. `case.predicate` 非空时 `for text, op in mutate_query_text(case.predicate)`：`replace(case, predicate=text)`，标签 `"p:" + op`；
3. `for setup, op in mutate_setup(list(case.setup))`：`replace(case, setup=tuple(setup))`，标签 `"s:" + op`；
4. **删一行**：对 setup 里第 i 条语句（从 0 数），若它是 `INSERT INTO ... VALUES` 且 VALUES 后面有至少两个顶层的括号行，就对每个行 j 产生一个删掉第 j 行的变体，标签 `f"s:drop_row[{i}][{j}]"`。行的切分要认引号（`'...'`，`''` 是转义）与嵌套括号；删掉之后用 `", "` 把剩下的行重新连起来，VALUES 之前的部分和最后一行之后的部分（如 `ON CONFLICT ...`、末尾分号）原样保留。门槛里的例子：`"INSERT INTO t VALUES (1, 2), (3, NULL), (3, NULL)"` 删第 1 行得 `"INSERT INTO t VALUES (1, 2), (3, NULL)"`，删第 0 行得 `"INSERT INTO t VALUES (3, NULL), (3, NULL)"`；
5. **删一条 INSERT**：对每条以 `INSERT`（不分大小写，可有前导空白）开头的 setup 语句 i，产生去掉它的变体，标签 `f"s:drop_insert[{i}]"`。

`SqlCase` 构造不合法（`ValueError`）的变体直接丢掉。同一个输入两次调用结果相同。

`oracle_options` 按 `oracles` 给的次序逐个看：`tlp`、`norec` 只在 `case.predicate` 非空时给（`(o, None)`）；`equivalent_query` 按 `RULES` 的次序每条规则一项 `(o, rule)`；`index_presence` 只在 `case.engine == "duckdb"` 时给；其余 `(o, None)`。不认识的 oracle 名 `ValueError`。

### 4. 常驻 φ 提取进程（`hunter/phi_worker.py`、`hunter/extractor.py`）

候选的 φ 要在库上算（会执行 setup、取 EXPLAIN、取表），种子语料里有建几十万行表的 setup，旧系统在这类种子上会长时间卡住；所以 φ 在一个常驻子进程里提取，每次请求有墙钟上限。

- `python -m surprise.hunter.phi_worker`：从 stdin 逐行读 JSON `{"id": n, "case": SqlCase.to_dict()}`，对每行调用 `surprise.features.extract(SqlCase.from_dict(case))`（默认词表、三层），向 stdout 写一行 `{"id": n, "phi": phi.to_dict()}` 并 flush；`extract` 抛异常时写 `{"id": n, "error": "<类型>: <消息>"}`。stdin 关闭即退出。不打印别的东西到 stdout。
- `PhiExtractor(*, timeout_s: float = PHI_TIMEOUT_S)`：
  - `extract(case) -> Phi`：先查缓存（键 `case_digest(case)`）；没有就交给子进程（第一次用时启动：`[sys.executable, "-m", "surprise.hunter.phi_worker"]`，`cwd` 为 `framework/`，环境变量里去掉 `DEEPSEEK_API_KEY`，stderr 丢弃或写到临时文件，不要让它塞满管道）。等回答最多 `timeout_s` 秒（Windows 上读管道没有超时，用一个读线程加队列）。超时、子进程退出、回答不是合法 JSON、`id` 对不上、或回答是 `error`：杀掉子进程（下次请求时重新启动），返回**降级的 φ**：语句层照算（`extract_ast(full_query(case), case.engine)`，`full_query` 来自 `surprise.harness.oracles.forms`），`plan`、`data` 两层记 `"unavailable"`，用 `make_phi` 组装——与 `features.extract_isolated` 在超时时给的结果相同。降级的结果也进缓存。
  - `stats` 属性：dict，键 `calls`、`cache_hits`、`timeouts`、`restarts`、`errors`。
  - `close()`：关闭子进程（关 stdin，等最多 5 秒，不退就杀）。可重复调用。
- 只支持默认词表（S8 没有发明特征）。

### 5. Hunter（`hunter/hunter.py`）

```python
LANES = ("refine", "generalize", "migrate", "explore")

@dataclass(frozen=True)
class Candidate:
    case: SqlCase
    oracle: str
    rule: str | None          # 只有 equivalent_query 有
    lane: str                 # LANES 之一
    hypothesis_id: str | None # 派生自哪个假设（refine / generalize / migrate）；explore 为 None
    parent: str | None        # 派生自哪条实验记录（refine / generalize / migrate）；explore 为 None
    op: str                   # 变异标签；migrate 为 "literal"；explore 为 "seed" 或 "seed_mutation"
    target: dict | None       # refine / generalize 的目标规格（Spec.to_dict()）；其余为 None
    def key(self) -> tuple[str, str, str]   # (case_digest(case), oracle, rule or "")

@dataclass(frozen=True)
class Choice:
    index: int                # 第几次选择，从 1 数（主循环的引导实验不算）
    slot: str                 # "explore" 或 "any"
    scored: Scored            # 选中的那个
    scored_pool: tuple[Scored, ...]   # 通过全部过滤并打了分的候选，按产生次序
    pool: dict[str, int]      # 见下

@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    phi: Phi
    score: Score              # 第 2 节的 Score
    # 便利属性（只读 property）：prediction、D、U、adjacent、probes、value，都转给 score

class Hunter:
    def __init__(self, *, engines, oracles, seed: int, beta: float | None = None,
                 corpus_path=None, extractor: PhiExtractor | None = None): ...
    def phi(self, case) -> Phi                      # 交给 extractor（带缓存）
    def record(self, record: ExperimentRecord, *, rule: str | None = None, prediction: Prediction | None = None) -> None
    def candidates(self, wb) -> list[Candidate]
    def choose(self, wb) -> Choice | None
    def close(self) -> None
    def manifest(self) -> dict                      # 见第 6 节
```

构造：`engines`、`oracles` 是非空的字符串序列（存成元组，次序保留）；`beta` 为 None 时取 `surprise.theory.constants.BETA`；`corpus_path` 默认 `framework/seeds/corpus.json`（用 `SeedCorpus.load`）；`extractor` 为 None 时新建一个 `PhiExtractor()`（由 Hunter 负责 `close`）。随机数只有两个来源：`self.rng = random.Random(seed)`，以及 `SeedMutator(rng=random.Random(seed + 1))`。任何遍历集合或字典的地方都先排序或按插入次序，保证换一个进程（`PYTHONHASHSEED` 不同）结果也一样。

`record(record, rule=, prediction=)`：主循环每做完一条实验（包括引导实验）就调用一次。它登记：`record_id → (case, oracle, rule)`；该实验的键 `(case_digest, oracle, rule or "")` 进"已做过"；`record.phi` 不为 None 时把 `(engine, oracle)` 作用域下的特征集合追加进新颖性窗口（每个作用域只留最近 `NOVELTY_WINDOW` 条），并把 `(oracle, rule or "", frozenset(features))` 记进"已做过的 φ"；标签是 `invalid` 且 `invalid_reason == "setup_error"` 时把 `tuple(case.setup)` 记进"坏 setup"；`prediction` 不为 None 且 `prediction.hypothesis_id` 不为 None 时该假设的探针数加一。

`candidates(wb)`：按当前理论生成全部候选（还没做新颖性等过滤），次序是"细化 / 泛化（按理论里假设的次序）→ 迁移 → 探索"。会消耗 `self.rng`。

- **细化 / 泛化**（变异车道，由 S 与 G 之间的差驱动）：取 `wb.theory.hypotheses` 里引擎在 `engines` 中的假设；每个假设的父本是它 `positives` 里已在 `record` 登记过的编号中最后 `PARENTS_PER_HYPOTHESIS` 个；父本的全部 `mutants(...)` 按父本次序连成这个假设的池（每项记住父本编号与变异标签）。有父本的假设个数为 k 时，每个假设的配额是 `max(1, MUTANTS_PER_STEP // k)`；池比配额大时用 `self.rng.sample(range(len(池)), 配额)` 选下标并按下标排序。对选中的每个变体：引擎不在 `engines` 里就跳过；`phi = self.phi(变体)`；`position(h, phi, h.oracle, registry)` 必须是 `"pending"`，否则丢弃；`missing` = S 里不在 `registry.closure(phi.features)` 中的字面量（按 S 的次序）；`swapped` = `[(l, s) for l in missing for s in registry.siblings(l) if s in closure]`；有 `swapped` 是 `generalize`，否则 `refine`；目标规格 `Spec(engine=h.engine, oracle=h.oracle, required=reduce_conjunction([S 里不在 missing 中的] + [s for _, s in swapped], registry), forbidden=tuple(sorted(missing)))`，存 `to_dict()`。oracle 取 `h.oracle`；`rule` 取父本那条实验的 rule（父本不是 `equivalent_query` 时为 None）。
- **迁移**（字面改写）：`len(engines) >= 2` 时，对每个假设（理论次序）、每个父本（同上，最后 `PARENTS_PER_HYPOTHESIS` 个）、每个别的引擎 e（`engines` 次序，跳过 `h.engine`）：`replace(父本用例, engine=e)`；`oracle_options(新用例, [h.oracle])` 为空就跳过，否则 oracle 为 `h.oracle`，rule 取父本的 rule（若它在选项里），否则取选项里第一个；`op = "literal"`。全部迁移候选多于 `MIGRATE_PER_STEP` 时用 `self.rng.sample(range(n), MIGRATE_PER_STEP)` 选下标、按下标排序。
- **探索**：对 `engines` 里每个引擎，种子是 `corpus.for_engine(engine).seeds`（语料次序）；为空就跳过；`self.rng.sample(种子表, min(EXPLORE_SEEDS_PER_STEP, len))`。对每个抽到的种子：基本用例 `SqlCase(engine, setup=tuple(seed.setup_sqls), query=seed.query, predicate=None)`，`op="seed"`；再加 `mutator.mutations_for(seed, max_per_seed=SEED_MUTATIONS_PER_SEED)` 的每个 `m`：`SqlCase(engine, tuple(m.setup_sqls), m.select_from, m.predicate)`，`op="seed_mutation"`。构造不合法的跳过。每个用例按 `oracle_options(用例, self.oracles)` 各出一个候选。

`choose(wb)`：

1. `index += 1`；`slot = "explore" if is_explore_slot(index) else "any"`。
2. `pool = self.candidates(wb)`；计数 `pool[lane]` = 各车道产生的个数。
3. 按产生次序逐个过滤：键在"已做过"里，丢（`rejected_known`）；`tuple(case.setup)` 在"坏 setup"里，丢（`rejected_bad_setup`）；`phi = self.phi(case)`；`(oracle, rule or "", frozenset(phi.features))` 在"已做过的 φ"里，丢（`rejected_novelty`）；否则 `nov = novelty(frozenset(phi.features), 该作用域的窗口)`，抽 `u = self.rng.random()`，`u >= accept_probability(nov)` 就丢（`rejected_novelty`）。同一轮里重复出现的键只留第一个（后面的算 `rejected_known`）。
4. 留下的逐个 `score(wb, phi, oracle, beta=self.beta, probes=探针数, units=hypothesis_units(wb))`（`units` 每轮算一次）。`scored` = 留下的个数。
5. 选择范围：`slot == "explore"` 且有探索车道的候选时只在探索车道里选，否则在全部里选；没有候选返回 None。
6. 最大 value 为 m；`ties = [s for s in 范围 if s.value >= m - 1e-12]`；一个就选它，多个用 `self.rng.choice(ties)`。
7. 返回 `Choice(index, slot, scored, scored_pool=留下的全部, pool={"refine", "generalize", "migrate", "explore", "rejected_known", "rejected_bad_setup", "rejected_novelty", "scored" 这八个键})`。`choose` 本身不调用 `record`，也不改理论。

### 6. `Hunter.manifest()`

返回 JSON 安全的 dict：`{"constants": constants.as_dict(), "beta": self.beta, "engines": [...], "oracles": [...], "seed": seed}`。（主循环会再加上 Diagnoser 的常数与代码摘要，那是下一个包的事。）

### 7. 导出

`surprise/hunter/__init__.py` 导出并列进 `__all__`：`constants`、`scoring`、`operators`（三个子模块）、`Candidate`、`Choice`、`Hunter`、`LANES`、`PhiExtractor`、`Score`、`Scored`。导入 `surprise.hunter` 不能启动子进程。

### 8. 测试

新增 `framework/tests/test_surprise_s08_hunter*.py`（可以分几个文件）。至少覆盖：第 2 节每个函数的数值与边界；`mutants` 的五类算子、去重、删行时引号里的逗号与括号；`oracle_options`；`PhiExtractor` 的缓存、超时降级与重启（用一个会睡很久的假 worker 或把 `timeout_s` 设得极小）、`close` 之后再用；`Hunter.candidates` 在一个手工搭的工作台上产生细化 / 泛化 / 迁移 / 探索四种，且出处都对（可以用门槛 `candidates` 组的做法，跑真实引擎的测试要控制在一分钟内）；`choose` 的探索保底、平分时的随机选择、过滤计数；两个不同 `PYTHONHASHSEED` 的子进程用同一种子得到同样的候选键序列。

## 背景

- 原型探测（编排者做的，不在仓库里）的发现，写给你避免踩坑：只有 DCE 的算子时，S 被泛化到只剩两三个字面量的假设几乎产生不了细化 / 泛化的候选，这是预期的（无 LLM 版的"假设更碎、泛化更少"）；门槛的 `candidates` 组先喂 F1 与 DF-A 两条已知复现，它们的 S 很长、语句里有比较与多行数据，四条车道都会有候选。
- `features.extract` 会执行 setup；DuckDB 种子里有建 90 万行表的语句。不要在 Hunter 进程里直接调用 `features.extract` 处理候选（第 4 节的子进程是为此做的）；`position`、`predict` 这类纯计算在本进程里做。
- 理论层与特征层的函数在 `registry=None` 时每次新建默认词表，很慢。`Theory` 与 `Workbench` 没有公开词表的属性，不要去读 `_registry`：Hunter 在构造时建一个 `default_registry()` 存起来，到处传它（S8 没有发明特征，工作台用的也是默认词表）。`hypothesis_units(wb, registry=None)` 加一个可选的 `registry` 参数，Hunter 调用时传自己的；门槛不传。
- worktree 里没有 `.venvs`，旧版引擎与 PostgreSQL 参照只在主检出区；本包的测试与门槛组不需要它们（`candidates` 组只用 DuckDB 1.5.5、DataFusion 54 与 PostgreSQL 参照跑两条引导实验，PostgreSQL 已在运行，门槛自己会找到）。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/hunter/**
framework/surprise/theory/constants.py
framework/tests/test_surprise_s08_hunter*.py
```

`theory/constants.py` 只为第 1 节的 `BETA` 开放。

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`，以及 `framework/surprise/theory/` 里 `constants.py` 以外的文件。觉得其中哪个非改不可，写进报告，停下。
- 旧代码（`framework/surprise/` 以外，包括 `evolution/`、`seeds/`）只调用、不改。
- 不改 S6、S7 的任何常数取值；`BETA` 之外不加理论常数。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 不调用任何 LLM，不导入 `agents`、`llm`、`guidelines`、`evolution.co_evolution`、`openai`、`httpx`；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不做主循环、Diagnoser、指标、基线（另外两个包的事）。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于 550，skip 仍是 3。用 `python -m pytest`：直接敲 `pytest` 会让 `import surprise` 失败
python -m surprise.gates.s08 --only scoring operators candidates     # 3/3
python -c "import sys, surprise.hunter, surprise.hunter.extractor; bad=[m for m in ('openai','httpx','httpx2','agents','llm','guidelines','evolution.co_evolution') if m in sys.modules]; print('LLM-FREE' if not bad else bad)"
python -m surprise.gates.s06            # 12/12（BETA 是新增常数，S6 的门槛允许新增）
python -m surprise.gates.s07 --only constants    # 1/1
```

`python -m surprise.gates.all` 在本包里会因为 S8 门槛的其余几组（属于后面的包与编排者）而失败，这是预期的；S1–S7 的门槛必须全部通过：跑一遍 `python -m surprise.gates.all`，把输出末尾的汇总贴进报告，确认 s01–s07 都是 PASS。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s08-hunter

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
