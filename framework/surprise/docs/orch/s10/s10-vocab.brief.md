角色：执行者

# 工作包 s10-vocab：词汇发明者（确认区反复意外通过时提议新的可执行特征；过留出验收才入表）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-vocab`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s10-frame`、`s10-harness`、`s10-prior`、`s10-oracle` 已合并）
- 所属会话：S10（Phase 5b：其余四个 LLM 角色，里程碑 M3），范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 依赖（已合并，直接用）：`surprise/roles/base.py`（`Role`、`RoleContext`、`Observed`）；`surprise/roles/runtime.py`（`build_roles` 会 `import surprise.roles.vocab_inventor` 并调用 `build(ctx)`）；网关；S5 的词表注册表 `surprise/features/registry.py`（`Registry.register` / `accept` / `save` / `load`，发明特征只支持 AST 层的正则定义）、`surprise/features/ast.py` 的 `extract_ast`（发明特征怎样被提取：`re.search(pattern, sql, re.IGNORECASE)`，`sql` 是 `full_query(case)`）、`surprise/features/vocabulary.py`（`FeatureDef`、`is_feature_id`）；冻结 harness 的 `surprise.harness.oracles.forms.full_query`；种子语料 `seeds.store.SeedCorpus.load(<framework>/seeds/corpus.json).seeds`（1092 条，每条的 `query`）；主循环的 `--vocabulary FILE`（`s10-frame` 已做：从头用扩展后的词表跑一次 run）。
- 先读：`framework/surprise/gates/s10.py` 的 `check_vocab_inventor`、`check_frame`（`--vocabulary` 那一段）、`check_switches` 与 `s10_cases.py` 的 `CONSTANTS`、`VOCAB_*`——**门槛就是接口规格**，与本说明不一致时以门槛为准，并写进报告；`surprise/roles/` 全部代码；`surprise/theory/hypothesis.py` 与 `theory.py`（`positives`、`contradictions`：确认区里的通过）；DECISIONS 的 S10 各条里"词表的迁移办法"一条（**按词表版本分段**：本次运行的理论不改，验收的特征写进文件，之后用 `--vocabulary` 起的运行才用它）。
- 与你并行的包 `s10-translator` 只写 `surprise/roles/translator.py`。你们不碰对方的文件。

## 目标

SESSIONS S10："词汇发明者：确认区反复意外通过时提议新的可执行特征；过留出验收才入表。"S6 / S7 记下的实机例子：手写的"EXCEPT ALL 且左侧有重复"遇到左右重复数相同的输入就通过，现有词表表达不了；`contradictions`（确认区里的通过）是"解释不了就由 LLM 发明新特征"的入口。S5 留的事："Registry 能登记空正则（对任何语句都命中），S10 定验收规则时把空正则和恒真正则挡掉"；"发明特征的正则在每次提取时对整条语句 `re.search`，没有超时，S10 接 LLM 词汇发明者时要防灾难性回溯的正则（验收前先在语料上跑一遍并计时）"。

LLM 不打标签：新特征只是理论的一个新词，验收全部是确定性的计算。

### 1. 注册表的一处修补（`surprise/features/registry.py`）

`_require_regex_definition` 额外拒绝"能匹配空串"的正则（`re.search(pattern, "")` 不为 None：空正则、`a*`、`(?:)` 之类都是恒真）。除此之外这个文件不改。改之前 grep 一遍 `tests/` 与 `gates/` 里登记的正则（现在用的 `x`、`marker`、`\bgate_marker\b` 都不匹配空串）。

### 2. 角色（新文件 `framework/surprise/roles/vocab_inventor.py`）

```python
def build(ctx: RoleContext) -> VocabInventor

class VocabInventor(Role):
    name = "vocab_inventor"
    vocabulary_path: Path               # ctx.llm_dir / "vocabulary.json"
    def observe(self, event) -> None    # remembers full_query(event.record.case) and the engine, in arrival order
    def after(self, wb, record, outcome) -> None
    def accepted(self) -> tuple[str, ...]
    def step(self) -> dict
    def report(self) -> dict
    def manifest(self) -> dict

def split_holdout(items: list) -> tuple[list, list]     # (train, held): held = the last ceil(n / VOCAB_HOLDOUT_DIVISOR)
def vocab_prompt(*, hypothesis, train_positives, train_contradictions, registry) -> str
```

#### 什么时候调用

`after(wb, record, outcome)`：只在 `outcome.observation.triage == "unexpected_pass"` 时看。按 `wb.theory.hypotheses` 的次序找 `record.record_id` 在其 `contradictions` 里的假设 `h`；对每个这样的 `h`（家族 `wb.family_of(h.hypothesis_id)`）：

- 这个家族已经试过 `VOCAB_ATTEMPTS_PER_FAMILY` 次 → 跳过；
- 正例 = `h.positives` 里你记住了语句的，按你记住它们的次序；矛盾通过 = `h.contradictions` 里你记住了的，同样次序；
- 矛盾通过不到 `VOCAB_TRIGGER_CONTRADICTIONS` 条、或正例不到 `VOCAB_MIN_POSITIVES` 条 → 跳过（不算一次尝试）；
- 否则算一次尝试，调用一次网关：`ctx.gateway.call("vocab_inventor", prompt, tier=VOCAB_TIER, seed=ctx.seed, temperature=VOCAB_TEMPERATURE, max_tokens=VOCAB_MAX_TOKENS)`。

门槛的例子（`s10_cases.VOCAB_RECORDS`）：五条记录，第 5 条（第二条意外通过）之后调用一次，之前不调用。

#### 留出

`split_holdout`：`k = ceil(n / VOCAB_HOLDOUT_DIVISOR)`，最后 `k` 个留出，其余是训练。正例与矛盾通过各自分。**留出的语句一律不进提示**（门槛查：留出记录的 SQL 不在提示里）。

#### 提示（纯函数，英文，不含任何记录号、假设号、家族号、运行号）

任务；假设的 `S`（特征 id 加一行说明）；训练正例逐条编号 `P1`、`P2`…（语句全文）；训练矛盾通过 `C1`、`C2`…；要求：给一个新的 AST 层特征，用 Python 正则定义，匹配方式就是 `re.search(pattern, statement, re.IGNORECASE)`；必须命中每一条 P、至少漏掉一条 C；不超过 `VOCAB_MAX_PATTERN_CHARS` 个字符；不要嵌套量词那类会灾难性回溯的写法；不能匹配空串；父类只能从下面列出的 AST 类里选（`ctx.registry` 里 `kind == "class"`、`layer == "ast"` 的全部 id 加说明，按 id 排序）；id 写成 `<父类 id>:<小写 token>`。JSON 形状：`{"feature": {"id": "...", "parent": "...", "description": "...", "pattern": "..."}, "prediction": {"matches": ["P1", ...], "excludes": ["C1", ...], "why": "..."}}`；"只回一个 JSON 对象"。

#### 验收（按次序，第一处不过就以那一步为原因拒收；门槛核对原因的名字）

1. `definition`：`feature` 是对象，四个字段都是非空字符串（`pattern` 可以是空串，留给下一步）；`parent` 是 `ctx.registry` 里 layer 为 `ast` 的类；`id` 合法（`is_feature_id`）、以 `parent + ":"` 开头、`ctx.registry` 里还没有它（也不在你已经收下的特征里）。
2. `pattern`：能编译；不超过 `VOCAB_MAX_PATTERN_CHARS` 个字符；`re.search(pattern, "", re.IGNORECASE)` 为 None。
3. 登记：在一份**草稿注册表**里（`ctx.registry` 的副本：`Registry.load` 你的 `vocabulary.json`，没有就 `default_registry()`；**绝不改 `ctx.registry`**）`register(FeatureDef(feature_id=id, kind="leaf", parent=parent, layer="ast", description=..., source="llm:vocab_inventor", definition={"kind": "regex", "pattern": pattern}, accepted=False, acceptance=None))`；抛异常 → `definition`。
4. `scan`：在一个子进程里（`sys.executable`，不用 shell）对种子语料全部语句与你记住的全部语句跑 `re.search(pattern, s, re.IGNORECASE)`，数语料里命中多少；`VOCAB_SCAN_TIMEOUT_S` 秒没跑完就杀掉子进程，拒收（`scan`，详情 `timeout`）；语料命中比例超过 `VOCAB_MAX_CORPUS_SHARE` → `scan`（详情 `corpus_share`）。语句经 stdin 以 JSON 传，结果经 stdout 以 JSON 回。门槛的 `(\w+\s?)+$` 在语料上实测超过 60 秒，必须在时限内被杀掉。
5. `train`：用与提取器相同的代码判断命中——在草稿注册表的一份副本里把它 `accept` 之后，`extract_ast(语句, 引擎, 那份副本)` 的结果里有没有这个 id。必须命中全部训练正例、至少漏掉一条训练矛盾。
6. `holdout`：同样的判断，必须命中全部留出正例（留出的矛盾通过不作要求）。

全过 → 收下：在草稿注册表里 `accept(id, acceptance)`，`acceptance = {"family": ..., "hypothesis_id": ..., "train": {"positives": n, "contradictions": n, "excluded": n}, "holdout": {"positives": n, "matched": n, "contradictions": n, "excluded": n}, "corpus_share": 比例, "prediction_kept": bool}`（`prediction_kept`：模型说命中 / 漏掉的训练条目与实际是否一致，只记录，不影响验收），然后 `Registry.save` 写到 `vocabulary_path`（累积：之前收下的都在里面）。门槛用 `Registry.load(vocabulary_path)` 读回来核对。本次运行的理论与 `ctx.registry` 不变（按词表版本分段）。

### 3. 记账与汇报

- 账本 `ctx.llm_dir / "vocabulary.jsonl"`（每写一行就 flush）：每次提议一行 `{"type": "proposal", "family", "hypothesis_id", "status": "accepted" | "rejected" | 网关的状态（blocked / miss / error）, "reason": None 或第 2 节的原因名（网关拒收时为 "reply"）, "detail": ..., "feature_id", "pattern", "prediction_kept", "key"}`。不写耗时、token。
- `accepted()`：按收下的次序返回特征 id。
- `step()`：本步的 `{"proposed": [[family, status, reason] ...]}`。
- `report()`：`{"proposals": n, "accepted": [...], "rejected": {原因: 条数}}`。
- `manifest()`：`{"vocabulary": "vocabulary.json"}`。

### 4. 测试

新文件 `framework/tests/test_surprise_s10_vocab_inventor.py`：照门槛的 `vocab_run` 用手造的 φ 与合成标签喂一个工作台（不用跑引擎），覆盖调用时机（只在意外通过时、两个阈值、每个家族一次）、留出与提示（留出的 SQL 不在提示里、没有 id）、每一种拒收原因（含灾难性正则在时限内被杀）、收下后 `vocabulary.json` 能 `Registry.load` 且特征被 `extract_ast` 提取出来、累积写入、`ctx.registry` 没被改；`features/registry.py` 的修补另写在 `framework/tests/test_surprise_s10_registry_regex.py`：空正则与恒真正则被拒，原来能登记的仍能登记。`build_roles({"roles": ["vocab_inventor"], ...})` 拿得到它。

### 5. 真实调用（可选）

派发时给了你 `DEEPSEEK_API_KEY` 与 `SURPRISE_LLM_MAX_CALLS`。可以用几次真实调用确认提示在 `deepseek-flash` 上能拿到合法回复（例如门槛的五条记录），缓存目录放 `.orch/tmp/` 下，不入库。报告里写明调用次数、模型给的正则、验收结论。**不要用 strong 档**。

## 允许改动的路径

```allow-paths
framework/surprise/roles/vocab_inventor.py
framework/surprise/features/registry.py
framework/tests/test_surprise_s10_vocab_inventor.py
framework/tests/test_surprise_s10_registry_regex.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（冻结）、`framework/surprise/` 里除上面列出的以外的任何文件（`theory/`、`hunter/`、`experiments/`、`features/` 的其他文件、`roles/` 的其他文件都不改；觉得非改不可，写进报告，停下）。`features/registry.py` 只做第 1 节那一处修补。
- 不在运行中改 `ctx.registry` 或理论（按词表版本分段）。
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
python -m surprise.gates.s05             # 通过（注册表的旧行为不变）
python -m surprise.gates.s10 --only constants frozen library frame prior oracle_inventor vocab_inventor    # 7/7
python -m surprise.gates.s09 --only isolation wiring replay                                                # 3/3
```

`isolation`、`switches` 要六个角色都在才能过，`translator_real` 与 `m3` 要编排者录的回复，都不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s10-vocab

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
