角色：执行者

# 工作包 s10-oracle：oracle 发明者（提议改写模板，多引擎一致才进入 Equivalent query 的改写规则库）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-oracle`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s10-frame`、`s10-harness` 已合并，harness 已由编排者重新冻结）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖（已合并，直接用）：
  - `surprise/roles/base.py`（`Role`、`RoleContext`、`Observed`）；`surprise/roles/runtime.py`（`build_roles` 会 `import surprise.roles.oracle_inventor` 并调用 `build(ctx)`；`RoleSet.rewrite_rules()` 调你的 `rules()`，Hunter 用它给 `equivalent_query` 加候选规则；`RoleSet.rewrite_library` 是 `ctx.llm_dir / "rewrites.json"`，主循环在运行期间把环境变量 `SURPRISE_REWRITE_LIBRARY` 指向它）。
  - 冻结 harness 的第二层（`surprise/harness/oracles/rewrites.py`）：`LIBRARY_RULE_PREFIX`、`LIBRARY_KINDS`、`LIBRARY_SCHEMA`、`template_problem(kind, template)`、`apply_template(query, kind, template)`、`load_library(path)`、`RULES`（冻结三条，每条有 `"proof"`）。**验收时套用模板一律用 `apply_template`**，与 harness 判定时是同一段代码。
  - 引擎：`surprise.harness.oracles.registry.runner_factory_for("duckdb" | "datafusion")`；SQLite 与 PostgreSQL 用 `surprise.harness.oracles.cross_dbms.default_reference_factories("duckdb")` 里的工厂。比较结果多重集用旧代码 `oracles.db_runner.bags_equal`（与 `EquivalenceOracle` 相同）。超时用 `surprise.harness.constants.QUERY_TIMEOUT_S`。
  - 种子语料：`seeds.store.SeedCorpus.load(<framework>/seeds/corpus.json).seeds`（文件次序），每条有 `setup_sqls` 与 `query`。
- 先读：`framework/surprise/gates/s10.py` 的 `check_oracle_inventor`、`check_library`、`check_switches` 与 `s10_cases.py` 的 `CONSTANTS`、`ORACLE_*`、`LIBRARY*`——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；`surprise/roles/` 全部代码；`harness/oracles/rewrites.py` 与 `equivalent_query.py` 的第二层。
- 与你并行的包 `s10-prior` 只写 `surprise/roles/prior.py`。你们不碰对方的文件。

## 目标

SESSIONS S10："oracle 发明者：提议等价改写或蜕变关系；多引擎一致才进入 Equivalent query 的改写规则库，判定代码不变。"PLAN 决策 9："oracle 发明者先只用多引擎一致，证明器后续再接。"用户在 S10 开工时批准了 harness 的小范围解冻，第二层改写规则库只收两种模板（`query_wrap` 的 `{q}`、`predicate_wrap` 的 `{p}`），harness 机械套用、判定前另要求参照引擎一致。本包是写这个库的那一方。LLM 不打标签：你只提议与验收模板，标签由 harness 判。

新文件 `framework/surprise/roles/oracle_inventor.py`：

```python
def build(ctx: RoleContext) -> OracleInventor

class OracleInventor(Role):
    name = "oracle_inventor"
    library_path: Path                 # ctx.llm_dir / "rewrites.json"
    def after(self, wb, record, outcome) -> None
    def rules(self) -> tuple[str, ...] # accepted rule ids, in acceptance order
    def step(self) -> dict
    def report(self) -> dict
    def manifest(self) -> dict

def oracle_prompt(*, library: dict, engines) -> str
def accept_template(kind: str, template: str, *, engines=None, scan_max=None) -> dict
```

### 1. 什么时候调用

- `after()` 每被调用一次就数一次（第 n 次）。当 `"equivalent_query"` 在 `ctx.oracles` 里、`(n − 1) % ORACLE_EVERY == 0`、且本次运行已调用的次数 `< ORACLE_CALLS_PER_RUN` 时，调用一次网关：`ctx.gateway.call("oracle_inventor", prompt, tier=ORACLE_TIER, seed=ctx.seed, temperature=ORACLE_TEMPERATURE, max_tokens=ORACLE_MAX_TOKENS)`。所以第 1、101、201 条实验之后各一次。`ctx.oracles` 里没有 `equivalent_query` 时从不调用。
- 你不读 `wb`、`record`、`outcome` 的内容（门槛传进来的是简单对象）。

### 2. 提示（`oracle_prompt`，纯函数，英文）

- 任务：发明保持结果多重集不变的 SQL 改写，用来做蜕变测试；在 bag 语义、NULL 三值逻辑、重复行下都要成立；在下列引擎上都要成立：`ORACLE_ACCEPT_ENGINES`。
- 已有的冻结规则：`RULES` 的三个名字与各自的 `proof`。
- 两种模板的写法与约束（与 `template_problem` 一致）：`query_wrap` 恰好一个 `{q}`（整条语句）；`predicate_wrap` 1–3 个 `{p}`（顶层 WHERE 的谓词，套用时会加括号）；不许分号、注释、写操作关键字、别的花括号；给两三个例子。
- 已经收进库的规则（`library` 里的 `rule_id`、`kind`、`template`，按收录次序），要求不要重复。
- 每次最多 `ORACLE_RULES_PER_CALL` 条。
- JSON 形状：`{"rules": [{"name": "snake_case", "kind": "query_wrap" 或 "predicate_wrap", "template": "...", "argument": "为什么等价"}], "prediction": [{"rule": "名字", "equivalent_on": ["duckdb", ...], "why": "..."}]}`；"只回一个 JSON 对象"。
- 不得包含记录号、假设号、运行号、时间、随机数、绝对路径。

### 3. 处理回复与验收

- 网关的 `status` 不是 `ok`：记一行，什么都不收。
- 逐条看 `rules`（超过 `ORACLE_RULES_PER_CALL` 的记 `over_max`）。每条按次序检查，第一处不过就记下原因（门槛核对原因的名字）：
  1. `name`：字符串且匹配 `^[a-z0-9_]{1,36}$`；`rule_id = LIBRARY_RULE_PREFIX + name`。
  2. `template`：`kind` 与 `template` 是字符串，`template_problem(kind, template)` 为 None。
  3. `duplicate`：`rule_id` 已经在库里，或同样的 `(kind, template)` 已经在库里。
  4. `argument`：非空字符串。
  5. 验收（`accept_template`）：`disagree` 或 `too_few_instances`。
- `accept_template(kind, template)`：按语料次序看最多 `ORACLE_SCAN_MAX` 条种子。对每条：`Q = seed.query`，`Q2 = apply_template(Q, kind, template)`，为 None 就跳过。对 `ORACLE_ACCEPT_ENGINES` 的每个引擎：新建 runner，跑 `setup_sqls`（任何一条报错 → 这个引擎记 `skipped`），在同一个 runner 上跑 `Q`（报错 → `skipped`）与 `Q2`（`Q` 成功、`Q2` 报错 → `error`），两边都成功时 `bags_equal` 相等记 `agree`、不等记 `disagree`；跑完关掉 runner。
  - 任何一个实例出现 `disagree` → 立即不收，原因 `disagree`。
  - 一个实例"算数"：`agree` 的引擎至少 `ORACLE_ACCEPT_MIN_ENGINES` 个，并且原查询在这些引擎上的结果都至少 2 行（只有 0 行或 1 行的结果分辨不出 `LIMIT`、`DISTINCT` 这类不等价）。
  - 凑够 `ORACLE_ACCEPT_INSTANCES` 个算数的实例就收；看完 `ORACLE_SCAN_MAX` 条还不够 → `too_few_instances`。
  - 返回 `{"accepted": bool, "reason": None 或原因, "instances": [{"seed": 语料下标, "query_sha256": ..., "agree": [引擎...], "error": [...], "skipped": [...]} ...（只列算数的实例；出现 disagree 时最后一个是那个实例，带 "disagree": [引擎...]）], "engines": [...], "scanned": 看过的种子数}`。
- 收下的规则：追加进库文件 `ctx.llm_dir / "rewrites.json"`（每次整份重写：先写临时文件再 `os.replace`；格式就是 harness 的 `{"schema": LIBRARY_SCHEMA, "rules": [...]}`，每条 `{"rule_id", "kind", "template", "argument", "proposer": "oracle_inventor", "acceptance": accept_template 的返回值}`）。写完之后 `load_library(该文件)` 必须认得全部收下的规则（自己核一遍，不认就当作没收、记 `library_refused`）。`rules()` 按收录次序返回 `rule_id`。
- 库文件只在至少收下一条时才创建。

### 4. 记账与汇报

- 账本 `ctx.llm_dir / "rewrites.jsonl"`（每写一行就 flush）：每次调用一行 `{"type": "call", "status": ..., "reason": ..., "key": ...}`；每条提议一行 `{"type": "proposal", "rule_id": ... 或 None, "name": ..., "kind": ..., "template": ..., "status": "accepted" 或 "rejected", "reason": None 或原因, "acceptance": accept_template 的返回值或 None, "prediction": 回复里这条规则的预测或 None}`。不写耗时、token。
- `step()`：本步的 `{"proposed": [[rule_id 或 name, status, reason] ...]}`。
- `report()`：`{"calls": n, "proposed": n, "accepted": [rule_id...], "rejected": {原因: 条数}}`。
- `manifest()`：`{"engines": [...], "library": "rewrites.json"}`。

### 5. 测试

新文件 `framework/tests/test_surprise_s10_oracle_inventor.py`：用脚本传输（照 `gates/s10.py` 的 `Script`）覆盖调用节奏（第 1、101、201 次，上限 3 次，没有 `equivalent_query` 不调用）、提示内容与纯度、每种拒收原因、验收（用真实引擎：`SELECT * FROM ({q}) AS llm_sub` 收、`... LIMIT 1` 因 `disagree` 不收；可以用一个只给一两条种子的小语料测 `too_few_instances`——为此 `accept_template` 可以多一个只给测试用的语料参数）、库文件被 `load_library` 认得、`rules()`；`build_roles({"roles": ["oracle_inventor"], ...})` 之后 `RoleSet.rewrite_rules()` 就是 `rules()`；用库文件让 `certify(..., "equivalent_query", rewrite_rule=收下的规则)` 判 pass（环境变量用 `monkeypatch.setenv`）。PostgreSQL 在本机 `127.0.0.1:55432`（见 `framework/AGENTS.md`）。

### 6. 真实调用（可选）

派发时给了你 `DEEPSEEK_API_KEY` 与 `SURPRISE_LLM_MAX_CALLS`。可以用几次真实调用确认提示在 `deepseek-flash` 上能拿到合法回复、看看验收收下几条，缓存目录放 `.orch/tmp/` 下，不入库。全部真实调用不超过上限；报告里写明调用次数、模型提了哪些模板、各自的验收结论。**不要用 strong 档**。

## 允许改动的路径

```allow-paths
framework/surprise/roles/oracle_inventor.py
framework/tests/test_surprise_s10_oracle_inventor.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已重新冻结）、`framework/surprise/` 里除上面两个文件以外的任何文件。觉得哪个非改不可，写进报告，停下。
- 不自己写模板的套用代码：用 harness 的 `apply_template`；不改库文件的格式。
- 旧代码（`framework/surprise/` 以外）只读不改。
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
python -m surprise.gates.s10 --only constants frozen library frame oracle_inventor    # 5/5
python -m surprise.gates.s09 --only isolation wiring replay                            # 3/3
```

`isolation` 与 `switches` 组要六个角色都在才能过，不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-oracle

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
