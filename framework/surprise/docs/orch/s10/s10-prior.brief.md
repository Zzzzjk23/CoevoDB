角色：执行者

# 工作包 s10-prior：探索先验（给未测单元先验失败率，用 Brier 分数校准）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-prior`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s10-frame`、`s10-harness` 已合并）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖（已合并，直接用）：`surprise/roles/base.py`（`Role`、`RoleContext`、`Observed`、`PLUGINS`）；`surprise/roles/runtime.py`（`build_roles` 会 `import surprise.roles.prior` 并调用 `build(ctx)`；`RoleSet.prior` 就是你的对象，Hunter 每轮调用它）；网关 `ctx.gateway.call(...)`；读源码工具 `ctx.readers`（`SourceReader.grep`）；`roles/constants.py` 里的 `PRIOR_*` 常数；`theory/constants.py` 的 `RESIDUAL_PRIOR_FAILS`、`RESIDUAL_PRIOR_TESTS`；`features/units.py`（单元的含义）。
- 先读：`framework/surprise/gates/s10.py` 的 `check_prior`、`check_switches`、`check_frame` 与 `s10_cases.py` 的 `CONSTANTS`、`PRIOR_*`——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；`surprise/roles/` 全部代码（S9 的实现器与猜想者是提示与回复处理的样板）；`surprise/hunter/hunter.py` 与 `scoring.py`（先验怎么被用：`prepare(wb, units, index=...)`、`pseudo(unit)`）。
- 与你并行的包 `s10-oracle` 只写 `surprise/roles/oracle_inventor.py`。你们不碰对方的文件。

## 目标

SESSIONS S10："探索先验：读文档、发布说明、历史 bug，给未测单元先验失败率；用 Brier 分数校准。"PLAN 第 5 节 Phase 5 的角色次序里它是第三个（"探索先验（Brier 校准）"）。框架原则："LLM 永不打标签"——先验只改变 Hunter 挑哪个实验（未探索区的 U），不改理论的 P_T、惊讶、标签。

新文件 `framework/surprise/roles/prior.py`：

```python
def build(ctx: RoleContext) -> ExplorationPrior

class ExplorationPrior(Role):
    name = "prior"
    def prepare(self, wb, units, *, index: int) -> None
    def pseudo(self, unit: str) -> tuple[float, float] | None
    def weight(self) -> float
    def brier(self) -> dict          # {"settled": int, "llm": float | None, "reference": float | None, "weight": float}
    def priced(self) -> dict         # unit -> the model's raw p_fail
    def observe(self, event) -> None
    def step(self) -> dict
    def report(self) -> dict
    def manifest(self) -> dict

def prior_evidence(units, readers) -> tuple[str, ...]
def prior_prompt(units, evidence) -> str
```

### 1. 定价（`prepare`）

- 每次选择（同一个 `index`）最多调用 `PRIOR_CALLS_PER_CHOICE` 次网关；Hunter 一次选择里可能调用 `prepare` 好几轮，同一个 `index` 的后几轮不再调用。
- 要定价的单元：`units` 里既没有定过价、也没有问过的，去重后**按字符串排序**，取前 `PRIOR_UNITS_PER_CALL` 个；一个都没有就不调用。
- 一次调用：`ctx.gateway.call("prior", prompt, tier=PRIOR_TIER, seed=ctx.seed, temperature=PRIOR_TEMPERATURE, max_tokens=PRIOR_MAX_TOKENS)`，`prompt = prior_prompt(这批单元, prior_evidence(这批单元, ctx.readers))`。
- 回复 JSON：`{"prediction": [{"unit": "...", "p_fail": 0.0 到 1.0 的数, "why": "..."}]}`。只收这一批里问过的单元；`p_fail` 必须是数（不是布尔）且在 [0, 1] 内，否则这个单元不定价；同一单元出现两次取第一次。回复被拒（网关的 `status` 不是 `ok`）或被挡（`blocked` / `miss` / `error`）时整批都不定价。
- 问过的单元都记为"问过"，**不再问**（不论有没有定上价、不论网关的状态）。

### 2. 先验伪计数（`pseudo`）与权重（`weight`）

- 参照率 `ref = RESIDUAL_PRIOR_FAILS / RESIDUAL_PRIOR_TESTS`（S6 的残差先验，现在是 0.01）。
- `pseudo(u)`：没定价 → None；否则 `p_eff = w·p + (1 − w)·ref`，返回 `(p_eff · PRIOR_STRENGTH, PRIOR_STRENGTH)`，`w = weight()`，`p` 是模型给的原值。
- `weight()`：结算条数 `n < PRIOR_MIN_SETTLED` 时为 `PRIOR_INITIAL_WEIGHT`；否则 `w = clip(1 − B_llm / B_ref, 0, 1)`，`B_llm` 与 `B_ref` 是到目前为止全部结算的平均 Brier 分数（`B_ref` 为 0 时：`B_llm` 也为 0 取 1，否则取 0）。

### 3. 结算（`observe`）

只结算同时满足这三条的实验：`event.prediction.zone == "unexplored"`；`event.prediction.unit` 已定价；`event.record.label.y` 是 `pass` 或 `fail`。结果 `o = 1`（fail）或 `0`（pass）；`B_llm` 累加 `(p − o)²`（用模型的原值 `p`，不是 `p_eff`），`B_ref` 累加 `(ref − o)²`。别的实验什么都不做。门槛只经 `event.prediction.zone / .unit` 与 `event.record.label.y / event.record.record_id` 喂你（`prediction` 与 `outcome` 可能是简单对象），不要读别的字段。

### 4. 证据（`prior_evidence`）与提示（`prior_prompt`）

- 证据只来自两份引擎检出（`ctx.readers`，可能是空 dict：那就没有证据），**不读项目自己的任何文件**（`docs/manual_findings.jsonl`、`docs/FAMILY_LEDGER_155.md`、`docs/recall_repros.json`、`duckdb/`、`datafusion/` 复现目录都是召回的真值，读了就泄漏；门槛会查证据行里没有这些名字）。
- 按单元的引擎与主构造（单元的第三段，见 `features/units.py` 的 `_CONSTRUCTS`）找关键词，例如 `set_op_all` → `EXCEPT ALL|INTERSECT ALL|UNION ALL`，`window` → `OVER \(|window function`，`asof_join` → `ASOF`，等等（你定一张表，覆盖 `_CONSTRUCTS` 的全部名字；`plain` 可以没有关键词）。正则一律忽略大小写。
- DataFusion：在 `dev/changelog` 下的 `.md` 文件里找（`reader.grep(pattern, under="dev/changelog", suffixes=(".md",), max_hits=PRIOR_EVIDENCE_PER_CONSTRUCT)`）。DuckDB：在 `test/issues` 下的 `.test` 文件里找（同样的调用，`under="test/issues"`, `suffixes=(".test",)`）。每个（引擎，构造）最多 `PRIOR_EVIDENCE_PER_CONSTRUCT` 行。
- 每行证据写成 `EVIDENCE <engine> <path>:<line> <text>`，`text` 去掉首尾空白、截到 200 个字符；按（引擎，构造）的排序、再按 grep 的次序排列。确定的输入给确定的输出（门槛调用两次比较）。
- 提示是**纯函数**（英文）：任务（"估计每个单元里一条有效测试会暴露缺陷的概率"）；单元格式 `engine|oracle|construct|plan class|data class` 的含义；一个典型单元大约 100 条有效测试里失败 1 条（参照率）；每个要定价的单元单独一行 `UNIT <unit>`（行首就是 `UNIT `，门槛用正则 `^UNIT (\S+)$` 取）；全部证据行；JSON 的形状逐字段写出；"只回一个 JSON 对象"。不得包含记录号、假设号、运行号、时间、随机数、绝对路径。

### 5. 记账与汇报

- 账本 `ctx.llm_dir / "prior.jsonl"`（每写一行就 flush）：每次调用一行 `{"type": "call", "units": [...], "status": ..., "reason": ..., "key": ...}`；每个定上价的单元一行 `{"type": "price", "unit": ..., "p": ..., "why": ...}`；每个没定上价的问过的单元一行 `{"type": "unpriced", "unit": ..., "reason": ...}`；每次结算一行 `{"type": "settle", "unit": ..., "y": ..., "record_id": ...}`。不写耗时、token（重放时会变）。
- `step()`：本步（上一次 `step()` 之后）的 `{"priced": [本步定上价的单元，按定价次序], "settled": 本步结算的条数, "weight": weight()}`。
- `report()`：`{"priced": 定价的单元数, "asked": 问过的单元数, "calls": 调用数, "brier": brier()}`。
- `manifest()`：`{"reference_rate": ref, "strength": PRIOR_STRENGTH}`。

### 6. 测试

新文件 `framework/tests/test_surprise_s10_prior.py`：用脚本传输（照 `gates/s10.py` 的 `Script`）覆盖：排序与分批、每次选择一次、问过不再问、坏回复（越界、非数、没问过的单元、被拒、被挡）；`pseudo` 与 `weight` 的公式（初始权重、满 20 条后的校准、`B_ref` 为 0 的边界）；只结算未探索区、已定价、有效的实验；证据的格式、确定性、空 readers；提示里没有 id；`build_roles({"roles": ["prior"], ...})` 拿到的 `RoleSet.prior` 就是它，`Hunter` 用它之后未探索区的 U 变了。

### 7. 真实调用（可选）

派发时给了你 `DEEPSEEK_API_KEY` 与 `SURPRISE_LLM_MAX_CALLS`。可以用几次真实调用确认提示在 `deepseek-flash` 上能拿到合法回复（例如给 `s10_cases.PRIOR_UNITS` 定价），缓存目录放 `.orch/tmp/` 下，不入库。全部真实调用不超过上限；报告里写明调用次数与结论。**不要用 strong 档**。

## 允许改动的路径

```allow-paths
framework/surprise/roles/prior.py
framework/tests/test_surprise_s10_prior.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（冻结）、`framework/surprise/` 里除上面两个文件以外的任何文件（`roles/` 的其他文件、`hunter/`、`experiments/`、`theory/`、`features/` 都不改：接口已经定死；觉得非改不可，写进报告，停下）。
- 不读、不引用项目自己的 bug 账本与复现目录（见第 4 节）。
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
python -m surprise.gates.s10 --only isolation     # 预期只因为别的角色模块还不存在而失败（"No module named 'surprise.roles.translator'" 之类）
python -m surprise.gates.s10 --only constants frozen library frame prior    # 5/5
python -m surprise.gates.s09 --only isolation wiring replay                 # 3/3
```

`switches` 组要六个角色都在才能过，不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-prior

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
