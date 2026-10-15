角色：执行者

# 工作包 s10-frame：角色插件框架、Hunter 的先验与额外改写规则钩子、运行词表（全关时与 S8/S9 逐行相同）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-frame`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s09-done-r2` 加上 S10 门槛的提交）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖（都已在基线里）：S9 的 `surprise/roles/`（网关、实现器、猜想者、`runtime.py` 的 `RoleSet` / `build_roles` / `ImplementerSource`）；S8 的 `surprise/hunter/` 与 `surprise/experiments/loop.py`（S9 加了 `sources` 钩子与 `--llm*` 开关）；`surprise/features/`（`Registry`、`Registry.load/save`、`extract`、`unit_of`）；`surprise/theory/`（`Workbench.create(root, registry=None)`、`Workbench.open(root, registry=None)`）。
- 先读：`framework/surprise/gates/s10.py` 与 `s10_cases.py` 全文——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；本包要让其中 `frame` 组通过，`constants` 组里属于本包的部分（常数表、`ROLES`、`PLUGINS`）通过。再读 `framework/surprise/gates/s09.py` 的 `wiring`、`replay`、`isolation` 三组，与 `gates/s08.py` 的 `no_llm`、`lanes`、`determinism`、`check_rows`：这些现在都通过，你改完以后必须仍然通过。
- 与你并行的包 `s10-harness` 改冻结的 harness（`harness/oracles/rewrites.py`、`equivalent_query.py`），加第二层改写规则库。你**不碰** harness，也不导入它新加的名字；双方只靠下面写死的环境变量名对接。

## 目标

S10 要接四个新角色：探索先验（`prior`）、迁移翻译者（`translator`）、词汇发明者（`vocab_inventor`）、oracle 发明者（`oracle_inventor`）。它们各自由后续的包写在 `surprise/roles/<名字>.py` 里。本包只搭它们共用的框架与钩子，**不写任何一个角色本身**：

1. 角色插件协议与上下文（新文件 `surprise/roles/base.py`）；
2. `RoleSet` / `build_roles` 认识六个角色名，四个新角色按需懒加载（`surprise/roles/runtime.py`）；
3. S10 的全部常数（`surprise/roles/constants.py`）；
4. Hunter 的两个钩子：单元先验（`prior`）与额外改写规则（`extra_rules`），以及可替换的词表（`registry`）（`surprise/hunter/`）；
5. 主循环：六个角色的开关、给角色的事件、oracle 发明者开着时的环境变量、`--vocabulary`（`surprise/experiments/loop.py`）。

原则（PLAN 第 1 节第 4 条："LLM 角色一次接一个，每个都能开关"；S8 验收："角色由开关接入，关掉时行为与 S8 相同"）：**不开新角色、不给 `--vocabulary` 时，一切输出与现在逐位相同**——S8 的 `determinism`、S9 的 `wiring`（全关 40 行与 S8 长跑逐行相同）、S9 的 `replay`（只开 S9 两个角色的 21 条录制回放逐行相同）都必须继续通过。

### 1. `surprise/roles/base.py`（新文件）

```python
PLUGINS = {
    "prior": "surprise.roles.prior",
    "translator": "surprise.roles.translator",
    "vocab_inventor": "surprise.roles.vocab_inventor",
    "oracle_inventor": "surprise.roles.oracle_inventor",
}

@dataclass(frozen=True)
class RoleContext:
    gateway: Gateway            # the run's one gateway (cache, cap, ledger)
    book: ConjectureBook        # the run's conjecture book (shared with the S9 roles)
    extract: Callable           # SqlCase -> Phi, the run's phi extractor
    registry: Registry          # the run's vocabulary; never None
    readers: dict               # engine -> SourceReader (empty when the checkouts are missing)
    engines: tuple[str, ...]
    oracles: tuple[str, ...]
    seed: int
    run_dir: Path
    llm_dir: Path               # run_dir / "llm"; exists

@dataclass(frozen=True)
class Observed:
    """One executed experiment, as the roles see it after the Diagnoser."""
    wb: Any                     # the Workbench
    phi: Phi
    record: Any                 # ExperimentRecord (record_id, seq, case, label, phi, ...)
    outcome: Any                # what wb.observe returned (.observation.triage/.opened, .owner)
    prediction: Any             # the theory's Prediction before execution (.zone, .unit, .hypothesis_id, ...)
    lane: str
    op: str
    hypothesis: str | None      # the candidate's hypothesis id
    target: dict | None         # the candidate's target spec
    index: int                  # the Hunter's choice index (0 for bootstrap)

class Role:
    """Base class with no-op defaults. A plugin module exposes build(ctx: RoleContext) -> Role."""
    name: str = ""
    def sources(self) -> tuple: return ()                  # objects with .candidates(wb, *, index, round)
    def observe(self, event: Observed) -> None: ...
    def after(self, wb, record, outcome) -> None: ...      # after observe, after the S9 conjecturer
    def step(self) -> dict: return {}                      # this step's summary; JSON-safe, no timings
    def report(self) -> dict: return {}
    def manifest(self) -> dict: return {}
    def close(self) -> None: ...
```

`base.py` 不在模块顶层导入任何角色模块、任何模型客户端（`httpx`、`agents`、`llm` 等，见 `gates/s09_cases.LLM_MODULES`）。

### 2. `surprise/roles/runtime.py`

- 公开常数 `ROLES = ("implementer", "conjecturer", "prior", "translator", "vocab_inventor", "oracle_inventor")`（替代私有的 `_ROLES`；`build_roles` 按它校验）。
- `build_roles(config, *, run_dir, extract, registry, engines, seed, oracles=())`：多一个关键字参数 `oracles`（默认空元组，S9 的调用方不传也照旧）。`config["roles"]` 里每个新角色名：`importlib.import_module(PLUGINS[name])`，调用它的 `build(ctx)`；**没开的角色，它的模块一律不导入**（门槛 `switches` 组在子进程里查）。模块还不存在时（本包里四个都不存在）抛 `ValueError(f"role {name!r} is not available: ...")`。`ctx` 用同一个网关、同一本猜想簿，`registry` 为 None 时用 `default_registry()`，`llm_dir = run_dir / "llm"`。
- `RoleSet` 多出（S9 已有的属性与方法行为不变）：
  - `plugins`：`{name: role}`，按 `ROLES` 的次序，只含开着的新角色；
  - `prior`：开着 `prior` 时是那个角色对象，否则 `None`；
  - `rewrite_rules()`：开着 `oracle_inventor` 时返回 `tuple(role.rules())`，否则 `()`；
  - `rewrite_library`：开着 `oracle_inventor` 时是 `llm_dir / "rewrites.json"`（`Path`），否则 `None`；
  - `sources`：S9 的 `ImplementerSource`（开着实现器时）在前，之后按 `ROLES` 次序接上每个插件的 `sources()`；
  - `observe(phi, label, record_id, *, event=None)`：先照旧结算猜想簿，再把 `event`（不为 None 时）按次序交给每个插件的 `observe`；返回值照旧（猜想簿结算的条目）；
  - `after(wb, record, outcome)`：先照旧调猜想者，再按次序调每个插件的 `after`；返回值照旧；
  - `step()`：S9 的四个键照旧，之后每个开着的插件一个键 `result[name] = role.step()`（没开的不出现，所以只开 S9 两个角色时整行与现在逐位相同）；
  - `report()`：S9 的内容照旧，之后每个开着的插件 `result[name] = role.report()`；
  - `manifest()`：S9 的内容照旧，多一个键 `"plugins": {name: role.manifest()}`（只在至少开了一个新角色时才加这个键）；
  - `close()`：S9 的照旧，再按次序调每个插件的 `close()`（第一个异常最后再抛）。
- 测试里用假的插件模块（`monkeypatch.setitem(base.PLUGINS, "prior", "你的测试模块路径")` 或往 `sys.modules` 里塞一个假模块），核对懒加载、次序、`step` 的键、`prior` / `rewrite_rules` / `rewrite_library`。

### 3. `surprise/roles/constants.py`

把 `gates/s10_cases.py` 的 `CONSTANTS` 表里的全部常数，原值原类型加进来（每个前面一行英文注释说明含义，照现有写法），放在 S9 常数之后。S9 的常数一个都不改。`as_dict()` 不改。

### 4. Hunter（`surprise/hunter/`）

- `Hunter.__init__` 在现有参数之后加三个关键字参数：`prior=None`、`extra_rules=None`、`registry=None`。
  - `registry`：None 时照旧 `default_registry()`；否则存成 `self._registry`，Hunter 内部一切用词表的地方（`position`、`closure`、`siblings`、`reduce_conjunction`、`hypothesis_units`、`unit_of`）都用它。
  - `extra_rules`：None 或一个无参可调用对象，返回额外改写规则 id 的元组（oracle 发明者验收过的 `llm:*` 规则，会随运行增长）。探索与迁移车道给候选列 oracle 选项时，`equivalent_query` 的选项是冻结的三条之后接上 `extra_rules()` 的结果（见下面 `oracle_options`）。细化 / 泛化沿用父本的规则（不变）。
  - `prior`：None 或一个对象，有 `prepare(wb, units, *, index)` 与 `pseudo(unit) -> (fails, tests) 或 None`。
- `choose`：每一轮里，先照现在的次序做全部过滤（已做过、坏 setup、φ 新颖性、新颖性抽签——**随机数的消耗次序一位都不能变**），把通过过滤的 `(候选, φ)` 收齐；如果 `prior` 不为 None 且这一轮至少有一个通过过滤的候选，就调用一次 `prior.prepare(wb, units, index=self._index)`，`units` 是这些候选的 `unit_of(φ, 候选.oracle, self._registry)`，按候选次序、去重保序；然后再逐个打分（`score(..., prior=self.prior)`）。`prior` 为 None 时不算 `units`、不调用任何东西，结果与现在逐位相同。
- `scoring.py`：
  - `optimistic_rate(tested, unexplained, prior_fails=RESIDUAL_PRIOR_FAILS, prior_tests=RESIDUAL_PRIOR_TESTS)`：把公式里的两个先验换成参数，默认值不变。
  - `uncertainty(tested, unexplained, adjacent, prior_fails=..., prior_tests=...)`：同上传下去。
  - `score(wb, phi, oracle, *, beta, probes, units, prior=None)`：只在未探索区算 U 时，若 `prior` 不为 None 且 `prior.pseudo(prediction.unit)` 不为 None，就用它返回的 `(fails, tests)` 当先验；否则照旧。别的区、别的项都不变。
- `operators.py`：`oracle_options(case, oracles, extra_rules=())`：`equivalent_query` 的选项是 `RULES` 的三条之后，按给定次序接上 `extra_rules` 里的规则 id（去掉与 `RULES` 重名的）。别的 oracle 不变。`RULES` 常数本身不改。
- `extractor.py` / `phi_worker.py`：`PhiExtractor(*, timeout_s=PHI_TIMEOUT_S, registry_path=None)`；给了 `registry_path` 时，常驻子进程以 `python -m surprise.hunter.phi_worker --registry <路径>` 启动，子进程里 `extract(case, registry=Registry.load(路径))`。不给时命令行与现在完全相同。
- `surprise/hunter/` 不得导入 `surprise.roles`。`LANES`、`constants.py` 不改。

### 5. 主循环（`surprise/experiments/loop.py`）

- `run(..., llm=None, vocabulary=None)`；命令行加 `--vocabulary FILE`。`--llm` 的取值扩成 `ROLES` 的六个名字；`_normalise_llm` 的角色校验也按六个名字（不要在模块顶层导入 `surprise.roles`：在 loop 里写一份同样的元组，`frame` 组之外的门槛会核对两者一致……如果你更愿意，在 `_normalise_llm` 里懒导入 `surprise.roles.runtime.ROLES` 也行，但 `llm` 为 None 时绝不能导入）。
- `vocabulary`：给了文件路径时：`registry = Registry.load(路径)`；φ 提取器用 `PhiExtractor(registry_path=路径)`；`Hunter(..., registry=registry)`；`Diagnoser(phi=..., registry=registry)`；`Workbench.create(theory_dir, registry=registry)`；角色的 `registry` 也是它。`config.json` 多一个键 `"vocabulary": 路径字符串`；run manifest 多一节 `manifest["vocabulary"] = {"path": 路径字符串, "sha256": 文件的 sha256, "digest": registry.digest()}`。没给时这些键都不出现，行为与现在逐位相同。
- 构造角色时多传 `oracles=state.oracles`；建 Hunter 时传 `prior=state.roles.prior`、`extra_rules=state.roles.rewrite_rules`（`llm` 为 None 时这两个参数不传或传 None）。
- `rewrite_library` 不为 None 时：在 `_prepare` 里把环境变量 `SURPRISE_REWRITE_LIBRARY`（这个名字写死；它是 `constants.REWRITE_LIBRARY_ENV`，也是并行的 harness 包读的名字）设成该路径的字符串，运行结束（正常、出错、中断）时恢复成原值（原来没有就删掉）。harness 每次判定都在子进程里读这个变量。
- `_execute` 里给角色的调用改成：`state.roles.observe(step.phi, record.label, record.record_id, event=Observed(wb=state.wb, phi=step.phi, record=record, outcome=outcome, prediction=step.prediction, lane=step.lane, op=step.op, hypothesis=step.hypothesis, target=step.target, index=step.index))`，再 `state.roles.after(...)`（次序照旧）。`Observed` 在开着角色时从 `surprise.roles.base` 懒导入。
- `code_digests()` 不改（它会把你改过的文件算进去，这是预期的：编排者之后会重跑 S8 长跑并重钉哈希）。

### 6. 测试

新文件 `framework/tests/test_surprise_s10_frame.py`，至少覆盖：

- `base.py` 的数据类与 `Role` 的默认实现；`PLUGINS` 的内容。
- `build_roles`：六个名字都认；未知名字、空列表照旧报错；开一个假插件时只导入它（`sys.modules` 里没有别的插件模块）；`RoleSet` 的 `plugins`、`prior`、`rewrite_rules()`、`rewrite_library`、`sources` 的次序、`observe` / `after` 的次序、`step` / `report` / `manifest` 的键；只开 S9 两个角色时 `step()`、`report()`、`manifest()` 与现在完全相同。
- Hunter：`prior` 为 None 时同种子 `choose` 若干次的结果与 `pool` 与不传完全相同；假先验被每轮最多调用一次、`index` 正确、单元格式是 `engine|oracle|construct|plan|data`；U 只在未探索区随先验变；`extra_rules` 出现在探索候选的 `equivalent_query` 选项里；`registry` 被用上（一个接受了的发明特征出现在候选的 φ 里）。
- `scoring`：`optimistic_rate` / `uncertainty` 的默认值与现在相同，给先验时按公式变。
- 主循环：`--vocabulary` 的一次短 run（DataFusion、引导 DF-A、`max_experiments=0`）：账本里 φ 带着发明特征、`config.json` 与 manifest 的 `vocabulary`；不给时没有这些键；假的 `RoleSet`（`monkeypatch.setattr(loop, "_build_roles", ...)`）带 `rewrite_library` 时运行期间环境变量被设上、结束后恢复（出错时也恢复）；`observe` 收到 `event`。
- 不做任何真实调用，不需要密钥。

## 允许改动的路径

```allow-paths
framework/surprise/roles/base.py
framework/surprise/roles/runtime.py
framework/surprise/roles/constants.py
framework/surprise/roles/__init__.py
framework/surprise/hunter/hunter.py
framework/surprise/hunter/scoring.py
framework/surprise/hunter/operators.py
framework/surprise/hunter/extractor.py
framework/surprise/hunter/phi_worker.py
framework/surprise/experiments/loop.py
framework/tests/test_surprise_s10_frame.py
framework/tests/test_surprise_roles_runtime.py
```

（`tests/test_surprise_roles_runtime.py` 只在 S9 的某条断言因为"角色名单从两个变成六个"而必须改时才改，并且只能改成同样严或更严的断言，在报告里逐条说明；能不改就不改。）

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（冻结；并行的包在改其中两个文件，你不碰）、`framework/surprise/theory/`、`framework/surprise/features/`、`framework/surprise/diagnoser/`、`framework/surprise/metrics/`、`framework/surprise/baselines/`，以及 `surprise/roles/` 里除上面列出的以外的文件（`implementer.py`、`conjecturer.py`、`gateway.py` 等一个字都不改：改了 S9 的提示，S9 的录制就重放不了）。
- 不写四个新角色的任何一个（`prior.py`、`translator.py`、`vocab_inventor.py`、`oracle_inventor.py` 都不建）；测试里用假插件。
- 不改 S8 的规则（车道、打分公式本身、保底位、新颖性、Diagnoser）与 S9 的行为；不改任何现有常数的值。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下（上面允许的那一个文件除外，且只能更严）。
- 不做任何 LLM 调用；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不跑超过 15 分钟的 run，不往 `framework/results/` 写东西。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。worktree 里跑测试一律用 `python -m pytest`（直接敲 `pytest` 会因导入路径失败）。

```powershell
cd framework
python -m pytest -q testing tests        # 通过数不少于 692（起点），skip 仍是 3
python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism     # 6/6，约 8 分钟
python -m surprise.gates.s09 --only isolation constants cache reject cap wiring replay       # 7/7（wiring 证明全关时与 S8 逐行相同，replay 证明只开 S9 两个角色时与录制逐行相同）
python -m surprise.gates.s10 --only frame       # 通过
python -m surprise.gates.s10 --only constants   # 预期失败，且第一处失败只能是 harness 的 rewrites.* 常数（并行包还没合并）；在那之前的常数检查必须已经通过
```

`s08` 的 `longrun` 组会因为代码摘要变了而失败，这是预期的，不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-frame

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
