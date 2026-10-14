角色：执行者

# 工作包 s08-loop：无 LLM 的 Diagnoser 与新主循环（Hunter → 执行与 CVE 标注 → 惊讶 → 分诊 → Diagnoser → 接受或回滚 → 更新 T）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s08-loop`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s08`（`s08-hunter` 与 `s08-eval` 两个包合并之后）
- 所属会话：S8（Phase 4：Hunter 与无 LLM 闭环，里程碑 M2），范围见 `framework/surprise/docs/SESSIONS.md` 的 S8 一节
- 依赖（都已合并，直接用）：`surprise.hunter`（`Hunter`、`PhiExtractor`、`Choice`、`Scored`、`operators.case_digest`、`constants`）、`surprise.metrics.curve`（`surprise_curve`、`teeth`）、`surprise.metrics.dups`（`new_families`）、S7 的 `surprise.theory`（`Workbench`、`Proposal`、`default_bets`、`common_conjunction`、`reduce_conjunction`、`attribution_request`、`extend_manifest`）、冻结的 `surprise.harness`（`evaluate_final`、`Ledger`、`build_manifest`）。先读 `framework/surprise/hunter/` 的全部代码、`framework/surprise/gates/s08.py`（尤其 `run_loop`、`open_run`、`check_rows`、`check_lanes`、`check_determinism`、`_normal`、`code_digests`）、`framework/surprise/gates/s07.py` 的 `replay()`（一次实验在主循环里的调用顺序就是那样写的）
- 本包做完，S8 门槛里除了 `constants`（等编排者的 β 预实验）与四个产物组（`longrun`、`sawtooth`、`duplicates`、`recall`，等编排者的长跑）之外的七组都应当通过

## 目标

依据 SESSIONS 的 S8 一节："新主循环入口：Hunter → 执行与 CVE 标注 → 惊讶 → 分诊 → Diagnoser（无 LLM：ddmin + bisect + 版本空间规则）→ 接受或回滚 → 更新 T"；"不做：任何 LLM 调用"。PLAN 第 1 节总原则 5："每次执行都留账（含通过、无效、被拒绝的提议）；所有指标只从账本计算"。

ddmin（最小化）与 bisect（fix set）由冻结 harness 的 CVE 第 3 档做，版本空间规则由 S6 的 `Theory.observe` 做，接受与回滚由 S7 的 `Workbench` 做；本包把它们接起来，并补上无 LLM 的 Diagnoser 的两件事。全部不调用任何模型，不导入 `agents`、`llm`、`guidelines`、`evolution.co_evolution`、`openai`、`httpx`。同样的参数与种子，换一个进程重跑得到同样的实验、同样的标签、同样的理论（只有墙钟字段不同）。

### 1. Diagnoser（`surprise/diagnoser/`）

`surprise/diagnoser/constants.py`，写法照 `theory/constants.py`（每个一行注释、`as_dict()`）：

```python
COMPRESS_EVERY = 100     # run the MDL compress() after every this many experiments
CHECKPOINT_EVERY = 100   # close a generation after every this many experiments
```

`surprise/diagnoser/diagnoser.py`，`Diagnoser(*, phi, registry)`：`phi` 是 `SqlCase -> Phi` 的可调用对象（主循环传 `hunter.phi`，经常驻子进程提取），`registry` 是词表（主循环传 Hunter 用的那个默认词表）。

- `after(wb, record, outcome) -> tuple[TheoryEdit, ...]`：只在 `outcome.observation.opened` 不为 None 时做事，否则返回空元组。取 `m = record.label.cve.get("minimize")`；`m` 是 dict、`m.get("status") == "ran"`、`m.get("reproduced") is True`、`m.get("case")` 非空才继续，否则返回空。`h = wb.theory.get(opened)`（`KeyError` 说明这个家族已经因回滚不在了，返回空）。`phi_min = self.phi(SqlCase.from_dict(m["case"]))`；`new_s = common_conjunction(h.specific, reduce_conjunction(phi_min.features, registry), registry)`；`new_s` 为空、或等于 `reduce_conjunction(h.specific, registry)` 时返回空。否则提议并返回 `(wb.propose(p),)`：
  ```python
  template = dataclasses.replace(h, specific=new_s, source="diagnoser")
  p = Proposal(kind="revise", proposer="diagnoser", removes=(h.hypothesis_id,), adds=(template,),
               bets=default_bets((h,), (template,), registry), trigger=(record.record_id,),
               rationale=f"the minimised reproduction of {record.record_id} keeps {len(new_s)} of the {len(h.specific)} literals of S")
  ```
  是否接受完全交给 S7 的接受检验；被拒的提议照样留在编辑日志里。
- `periodic(wb, done) -> tuple[TheoryEdit, ...]`：`done` 是到此为止做完的实验条数（含引导实验）。`done % COMPRESS_EVERY == 0` 时 `edits = wb.compress()`，否则空；然后 `done % CHECKPOINT_EVERY == 0` 时 `wb.checkpoint(f"after {done} experiments")`。返回 `edits`。

`surprise/diagnoser/__init__.py` 导出 `constants`、`Diagnoser`。

### 2. 主循环（`surprise/experiments/loop.py`）

命令行：

```
python -m surprise.experiments.loop --out DIR --seed N [--engine E]... [--oracle O]...
       [--max-experiments N] [--max-minutes M] [--beta B] [--bootstrap FILE] [--run-id ID]
```

- `--engine` 可重复，默认 `duckdb` 一个；`--oracle` 可重复，默认七类全部，次序 `tlp norec plan_variant index_presence equivalent_query version_differential cross_dbms`。
- `--max-experiments`：Hunter 选出的实验条数上限（**不含**引导实验）；`--max-minutes`：墙钟上限。至少给一个，否则参数错误退出码 2。每次选择之前检查：条数到了，状态 `budget_experiments`；时间到了，状态 `budget_minutes`。时间只用来停，不参与任何决定。
- `--beta`：不给就用 `surprise.theory.constants.BETA`（预实验时编排者会传别的值）。
- `--bootstrap FILE`：JSON 列表，每项 `{"case": SqlCase.to_dict(), "oracle": str, "rule": str 或 null}`；在 Hunter 之前按次序做完。
- `--run-id`：默认 `f"loop-s{seed}"`。
- `DIR` 不存在就建；存在且非空，参数错误退出码 2。

同样的东西也要能从 Python 调：`run(out, *, seed, engines=("duckdb",), oracles=<七类>, max_experiments=None, max_minutes=None, beta=None, bootstrap=(), run_id=None) -> dict`（返回 report）；`main(argv=None) -> int`；`if __name__ == "__main__": sys.exit(main())`。

**准备**：`extractor = PhiExtractor()`；`hunter = Hunter(engines=..., oracles=..., seed=..., beta=..., extractor=extractor)`；`registry = default_registry()`（只建这一个）；`diagnoser = Diagnoser(phi=hunter.phi, registry=registry)`；`wb = Workbench.create(DIR / "theory")`；`ledger = Ledger(DIR / "ledger.sqlite")`；manifest = `extend_manifest(build_manifest(run_id))`，再加一节 `manifest["hunter"] = {**hunter.manifest(), "diagnoser": diagnoser 常数的 as_dict(), "code": code_digests()}`，`ledger.start_run(run_id, manifest)`。`config.json` 写进 `DIR`（全部参数）。

`code_digests()`：`framework/surprise/hunter`、`framework/surprise/diagnoser`、`framework/surprise/experiments` 三个目录下（递归，跳过 `__pycache__`）每个 `.py` 文件，读字节、把 `b"\r\n"` 换成 `b"\n"` 后取 sha256 十六进制，键是相对 `framework/` 的路径（正斜杠），按路径排序。门槛 `gates/s08.py` 的 `code_digests()` 与它逐字相同，用来确认一次 run 是由当前代码跑出来的。

**一条实验**（引导实验与 Hunter 选的走同一段代码）：

1. 引导实验：`phi = hunter.phi(case)`；`prediction = wb.predict(phi, oracle)`；lane `"bootstrap"`、index 0、slot `"bootstrap"`，value 等打分字段为 None。Hunter 的：`choice = hunter.choose(wb)`（为 None 时状态 `exhausted`，停）；case、oracle、rule、phi、prediction 都取 `choice.scored`。
2. `options = {"diagnose": True}` 若 `prediction.hypothesis_id is None`，否则 `{"hypothesis": attribution_request(wb.theory.get(prediction.hypothesis_id))}`。
3. `record = evaluate_final(case, oracle, ledger=ledger, run_id=run_id, purpose=lane, spec=spec, phi=phi.to_dict(), theory_version=wb.theory.version, p_t=prediction.p_fail_valid, rewrite_rule=rule, **options)`。`spec` 是 JSON 安全的 dict：`lane`、`slot`、`index`、`hypothesis`（候选派生自的假设）、`parent`、`op`、`target`、`rule`、`zone`、`value`、`D`、`U`、`adjacent`、`probes`（引导实验时 `hypothesis`、`parent`、`target`、`value`、`D`、`U`、`adjacent`、`probes` 为 None，`op` 为 `"bootstrap"`）。
4. `outcome = wb.observe(phi, record.label, record.record_id, prediction=prediction)`。
5. `hunter.record(record, rule=rule, prediction=prediction)`。
6. `edits = diagnoser.after(wb, record, outcome) + diagnoser.periodic(wb, done)`（`done` 已含这一条）。
7. 向 `DIR/progress.jsonl` 追加一行并 flush（见下）。

**progress.jsonl** 每条实验一行，键恰好是：`seq`（`record.seq`）、`record_id`、`index`、`slot`、`lane`、`oracle`、`rule`、`case_digest`（`operators.case_digest(case)`）、`hypothesis`、`parent`、`op`、`target`、`zone`（`prediction.zone`）、`predicted`（`prediction.hypothesis_id`）、`p_fail_valid`、`p_invalid`、`D`、`U`、`adjacent`、`probes`、`value`、`y`、`kind`（`fail_kind` 或 `invalid_reason`，pass 时 None）、`surprise`（`outcome.observation.surprise`）、`triage`、`opened`、`owner`（`outcome.owner`）、`rolled_back`（列表）、`bets`（`outcome.bets` 转成列表的列表）、`edits`（每条 `{"edit_id", "kind", "proposer", "decision", "reason": edit.payload.get("reason")}`）、`pool`（`choice.pool`；引导实验为 `{}`）、`theory_version`（这一条做完之后的 `wb.theory.version`）、`elapsed_s`（从 run 开始的墙钟秒数，保留两位小数）。除 `elapsed_s` 之外都不能依赖墙钟、进程号、路径或集合的遍历次序。

**结束**（预算到、`exhausted`、`KeyboardInterrupt` 记 `interrupted`、未预料的异常记 `error` 并在报告里带上异常的类型与消息）：写 `DIR/report.json`，然后关闭 extractor 与 ledger（`finally` 里关，异常照样向上抛，命令行退出码 1；`interrupted` 退出码 130）。`report.json`：

```
run_id, seed, engines, oracles, beta, status,
experiments  （账本里的记录数，含引导实验）
choices      （Hunter 选择的次数）
started_at, finished_at （ISO 8601，UTC）, wall_s,
labels   {y: 条数}, lanes {lane: 条数}, triage {分诊: 条数},
hypotheses （最后的假设数）, families （wb.families() 的个数）,
edits    {"accepted": n, "rejected": n, "rolled_back": n}   （按编辑日志里每条编辑最后的状态数）
curve    metrics.curve.surprise_curve(账本记录, 100)
teeth    metrics.curve.teeth(curve)       （默认 amplitude 0.25、width 5）
new_families  len(metrics.dups.new_families(DIR / "theory"))
extractor     extractor.stats
error         （只在 status == "error" 时有）
```

命令行运行时每条实验向 stdout 打一行 ASCII 的简报（序号、车道、oracle、标签、惊讶、分诊），结束时打印报告的状态与条数。不打印别的东西。

`surprise/experiments/__init__.py` 已存在（空）；不要在里面导入 `loop`。

### 3. 测试

新增 `framework/tests/test_surprise_s08_loop*.py`。至少覆盖：

- `Diagnoser.after`：手工的工作台（参考 `gates/s07.py` 的 `opened_bench`）加一个手工的、带 `minimize` 的标签和一个返回指定 φ 的假 `phi`，覆盖：提议并被接受、S 不变不提议、没有最小化 / 没复现不提议、家族已不在、被接受检验拒绝时仍然返回那条编辑；`periodic` 的两个节拍。
- 主循环真实跑一小段（引导 F1，`--max-experiments 4` 左右，控制在一分钟内）：账本、progress、report、manifest 的字段与相互对应；`--max-minutes` 停在时间上；空目录检查与参数错误；`code_digests` 与门槛的函数结果相同。
- 两个子进程（不同的 `PYTHONHASHSEED`）用同一种子跑同一小段，progress 去掉 `elapsed_s` 之后逐行相同。

## 背景

- 编排者的原型（不在仓库里）每步约 2.5 秒：φ 提取约 0.7 秒、`evaluate_final` 约 1.7 秒，其余可以忽略。门槛 `lanes` 跑 32 条、`determinism` 并行跑三次各 26 条，合计五六分钟。
- 理论的状态每条实验都要算一次版本号、存一次盘（S7 交接：1 万条通过时 `version` 约 47 毫秒、`save` 约 157 毫秒）。这是已知的，本包不优化它；如果你量到明显更慢，写进报告。
- 新家族开出时冻结 harness 已经做过最小化（`label.cve["minimize"]["case"]` 是最小化之后的用例）与完整画像；Diagnoser 只读它，不再执行任何东西（取 φ 除外）。
- worktree 里没有 `.venvs`，旧版引擎与 PostgreSQL 参照只在主检出区；门槛与 harness 会自己找到它们（PostgreSQL 已在运行）。如果某组因为连不上 PostgreSQL 或找不到旧版解释器而失败，不要去修环境：把报错原样写进报告，停下。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/diagnoser/**
framework/surprise/experiments/**
framework/tests/test_surprise_s08_loop*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`、`framework/surprise/theory/`、`framework/surprise/hunter/`、`framework/surprise/metrics/`、`framework/surprise/baselines/`。觉得其中哪个非改不可（比如 Hunter 的某个行为与门槛对不上），写进报告，停下。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不改任何常数的取值；`BETA` 由编排者的预实验决定，本包不动。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。主循环里"未预料的异常记进报告再抛出"是规定的行为，不算吞掉失败。
- 不调用任何 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不跑长时间的实验（超过 15 分钟的 run），不往 `framework/results/` 写东西；长跑与预实验是编排者的事。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于 597（两个前置包合并后的数目），skip 仍是 3。用 `python -m pytest`
python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism     # 6/6，约 8 分钟
python -m surprise.gates.s08 --only constants     # 预期失败，且失败信息必须是 "s08_runs.json is not written yet"（β 由编排者定）；其余原因的失败要修
python -m surprise.gates.all            # s01–s07 全部 PASS；s08 只允许 constants 与 longrun sawtooth duplicates recall 五组失败
```

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s08-loop

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
