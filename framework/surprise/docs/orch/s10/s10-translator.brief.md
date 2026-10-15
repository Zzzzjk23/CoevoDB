角色：执行者

# 工作包 s10-translator：迁移翻译者（把一个引擎上的假设翻成另一个引擎的写法与开关；用 bisect 与归属测试检验）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-translator`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s10-frame`、`s10-harness`、`s10-prior`、`s10-oracle` 已合并）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖（已合并，直接用）：`surprise/roles/base.py`（`Role`、`RoleContext`、`Observed`）；`surprise/roles/runtime.py`（`build_roles` 会 `import surprise.roles.translator` 并调用 `build(ctx)`；`RoleSet.sources` 会接上你的 `sources()`）；S9 的 `surprise/roles/implementer.py`（提示、回复处理、φ 核对与重试的样板，**照它的写法，不要改它**）与 `runtime.py` 的 `ImplementerSource`（候选来源的样板）；`surprise/roles/sources_map.py` 的 `DUCKDB_OPTIMIZER_FILES`（DuckDB 优化器的名字）；`surprise.hunter.hunter.Candidate`、`surprise.hunter.operators.oracle_options` 与 `case_digest`；`surprise.features`（`check_spec`、`Phi`）与 `features/vocabulary.layer_of`；`surprise.theory`（`Spec`、`reduce_conjunction`）；`surprise.harness.cve.shape.behavior_shape`。
- 先读：`framework/surprise/gates/s10.py` 的 `check_translator`、`check_translator_real`、`check_switches` 与 `s10_cases.py` 的 `CONSTANTS`、`TRANSLATE_LANE`、`TRANSLATOR_*`——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；`surprise/roles/` 全部代码；`surprise/theory/identity.py`（fix set 与归属测试怎样定身份）；`surprise/experiments/loop.py` 的 `_execute`（翻译的候选怎样被执行：理论预测不到它时走第 3 档完整画像，含 bisect 得出 fix set；预测到某个假设时走第 2 档归属测试）。
- 与你并行的包 `s10-vocab` 只写 `surprise/roles/vocab_inventor.py` 与 `features/registry.py`。你们不碰对方的文件。

## 目标

SESSIONS S10："迁移翻译者：把一个引擎上的假设翻成另一个引擎的开关与写法；用归属测试和 bisect 检验。"S8 的 Hunter 在没有 LLM 时迁移只做字面改写（`_migrate`：换个引擎名原样再跑）；本角色在开着时给出真正的翻译。LLM 不打标签：翻译只是一个实验，由 harness 判；角色只记下它的预测是否兑现。

新文件 `framework/surprise/roles/translator.py`：

```python
def build(ctx: RoleContext) -> Translator

class Translator(Role):
    name = "translator"
    def sources(self) -> tuple         # (TranslatorSource,)
    def observe(self, event) -> None
    def translations(self) -> tuple    # every book row so far (translation rows and settle rows), in order, as dicts
    def step(self) -> dict
    def report(self) -> dict
    def manifest(self) -> dict

class TranslatorSource:
    def candidates(self, wb, *, index: int, round: int) -> list   # list[Candidate]

def allowed_switches(engine: str) -> tuple[str, ...]   # duckdb: sorted(DUCKDB_OPTIMIZER_FILES); others: ()
def translator_prompt(*, hypothesis, source_case, target_engine, spec, mechanism, registry, feedback=None) -> str
```

### 1. 记住用例（`observe` 的前一半）

每个事件都把 `event.record.case` 记在 `event.record.record_id` 下（翻译时要拿假设正例的原 SQL；理论里只有 φ，没有 SQL）。

### 2. 什么时候翻译（`TranslatorSource.candidates`）

- 照 `ImplementerSource`：每个 `index` 只在 `round <= 1` 且这个 `index` 还没服务过时做新翻译，最多 `TRANSLATOR_PER_CHOICE` 个；每次被调用都返回到目前为止全部成功的候选（Hunter 会丢掉做过的）。
- 挑翻译对象：按 `wb.theory.hypotheses` 的次序看每个假设 `h`：`h.engine` 在 `ctx.engines` 里、`h.oracle` 不为 None、`h.positives` 里至少有一条你记住了用例。目标引擎按 `ctx.engines` 的次序取不等于 `h.engine` 的。每个（家族 `wb.family_of(h.hypothesis_id)`，目标引擎）只翻一次（不论成败）。`ctx.engines` 只有一个时什么都不做、不调用。
- 源用例：`h.positives` 里你记住了用例的最后一条。

### 3. 翻译一次

- 目标规格：`Spec(engine=目标, oracle=h.oracle, required=reduce_conjunction([h.specific 里 layer 是 ast 或 data 的字面量], ctx.registry))`（plan 层字面量不进：计划随引擎而变）。`required` 为空就不翻（记 `empty_spec`）。
- 机制：猜想簿（`ctx.book.conjectures()`）里 `hypothesis_id == h.hypothesis_id`、`status == "registered"` 的最后一条的 `mechanism`；没有就是 None。
- 提示（纯函数，英文，**不含**记录号、假设号、家族号、运行号）：源引擎与目标引擎；目标引擎的方言一句；oracle；失败类别、错误类别、行为形状；源引擎上的 fix set（`h.interventions`）与计划差异；规格的必须特征（id 加一行说明，照实现器）；源用例的 setup、query、predicate；机制或 "(none)"；目标引擎可用的开关（`allowed_switches(目标)`；为空时写明"没有开关，身份就是行为形状"）；JSON 形状；"只回一个 JSON 对象"。有 `feedback` 时附上上一次的问题（缺了哪些特征、多了哪些、哪个开关不认、哪个字段不对）。
- 调用：`ctx.gateway.call("translator", prompt, tier=TRANSLATOR_TIER, seed=ctx.seed, temperature=TRANSLATOR_TEMPERATURE, max_tokens=TRANSLATOR_MAX_TOKENS)`，最多 `TRANSLATOR_ATTEMPTS` 次。
- 回复 JSON：`{"setup": [语句...], "query": "语句", "predicate": "表达式" 或 null, "prediction": {"expect": "pass" 或 "fail", "switches": [开关名...], "behavior": "missing_only" | "extra_only" | "both" | null, "why": "..."}}`。
- 每次尝试，按次序（第一处不过就带着反馈重试，用完次数就以最后的状态结束）：网关 `blocked` / `miss` / `error` → 立即结束（状态照抄）；网关拒收或字段不对 → `rejected`；`switches` 不是 `allowed_switches(目标)` 的子集 → `bad_switch`；`behavior` 不在允许值里 → `rejected`；`SqlCase(engine=目标, ...)` 构造失败 → `bad_case`；`oracle_options(case, [oracle])` 为空 → `not_applicable`（不重试）；`ctx.extract(case)` 之后 `check_spec(φ, 规格, ctx.registry)` 不满足 → `spec_unmet`；都过了 → `ok`。
- `ok` 时造候选：`Candidate(case=case, oracle=h.oracle, rule=(oracle_options 的第一个规则，只在 equivalent_query 时；否则 None), lane="translate", hypothesis_id=h.hypothesis_id, parent=源用例的记录号, op="translator", target=规格.to_dict())`。

### 4. 结算（`observe` 的后一半）

事件的 `(case_digest(event.record.case), event.record.label.oracle)` 等于某个还没结算的成功翻译的（用例摘要，oracle）时结算它：

- `label.y == "invalid"` → `state = "void"`，`identity = None`；
- 否则 `y == expect` → `kept`，不等 → `broken`；
- `identity` 只在 `y == "fail"` 且 `expect == "fail"` 时定，其余为 None：
  - 预测了开关：`label.cve["profile"]` 跑过（`status == "ran"`）且有 `fix_set` → 集合相等为 `match`，否则 `mismatch`（这就是 bisect 检验）；没有画像但 `label.cve["attribution"]` 跑过、`consistent` 为 True、它的 `hypothesis_id` 在 `event.wb.theory` 里 → 拿那个假设的 `interventions` 比（这就是归属测试检验）；`consistent` 为 False → `mismatch`；都没有 → `unknown`。
  - 没预测开关：预测的 `behavior` 为 None → `unknown`；否则与 `behavior_shape(label.identity.behavior)` 比，相等 `match`，否则 `mismatch`。
- 门槛的脚本测试会给你简单对象：`event.prediction` 与 `event.outcome` 可能不是真类型，`event.wb` 可能是 None；只读上面用到的字段。

### 5. 记账与汇报

- 账本 `ctx.llm_dir / "translations.jsonl"`（每写一行就 flush），`translations()` 返回同样的行：
  - 每次翻译（不论成败）一行 `{"type": "translation", "translation_id": "t1"…, "hypothesis_id", "family", "source_engine", "target_engine", "oracle", "status", "case": case.to_dict() 或 None, "case_digest": ... 或 None, "expect", "switches", "behavior", "tries", "keys", "parent"}`；
  - 每次结算一行 `{"type": "settle", "translation_id", "state", "identity", "record_id"}`。
  - 不写耗时、token。
- `step()`：本步的 `{"translated": [[translation_id, status] ...], "settled": [[translation_id, state, identity] ...]}`。
- `report()`：`{"translations": n, "by_status": {...}, "settled": {"kept": n, "broken": n, "void": n}, "identity": {"match": n, "mismatch": n, "unknown": n}}`。
- `manifest()`：`{"switches": {engine: list(allowed_switches(engine)) for engine in ctx.engines}}`。

### 6. 测试

新文件 `framework/tests/test_surprise_s10_translator.py`：用脚本传输覆盖翻译时机（每个家族与引擎一次、每次选择最多一次、单引擎不调用）、提示内容与纯度、每种状态（含 `spec_unmet` 重试带缺失特征、`bad_switch`、`not_applicable`）、结算的每种 `state` 与 `identity`（fix set、归属测试、行为形状、unknown）、账本行；`build_roles({"roles": ["translator"], ...})` 之后 `RoleSet.sources` 里有它。

### 7. 真实调用（可选）

派发时给了你 `DEEPSEEK_API_KEY` 与 `SURPRISE_LLM_MAX_CALLS`。可以用几次真实调用确认提示在 `deepseek-flash` 上能拿到合法回复（例如照门槛 `translator_real` 的设置：F2 在 DuckDB 上开出的家族翻到 DataFusion），缓存目录放 `.orch/tmp/` 下，不入库。报告里写明调用次数与结论。**不要用 strong 档**。

## 允许改动的路径

```allow-paths
framework/surprise/roles/translator.py
framework/tests/test_surprise_s10_translator.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（冻结）、`framework/surprise/` 里除上面两个文件以外的任何文件（`implementer.py`、`runtime.py`、`hunter/` 等都不改；觉得非改不可，写进报告，停下）。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest；旧测试一个都不改。某个测试确实该改，就写进报告的"未决问题"，停下。
- 标签路径上不调用 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不跑超过 15 分钟的 run，不往 `framework/results/` 写东西。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。worktree 里跑测试一律用 `python -m pytest`。

```powershell
cd framework
python -m pytest -q testing tests        # 通过数不少于起点（先在起点跑一次记下），skip 仍是 3
python -m surprise.gates.s10 --only constants frozen library frame prior oracle_inventor translator    # 7/7
python -m surprise.gates.s09 --only isolation wiring replay                                            # 3/3
```

`isolation`、`switches` 要六个角色都在才能过，`translator_real` 与 `m3` 要编排者录的回复，都不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-translator

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
