# 报告 · s11-arms

提交 `e973b5d`（`e973b5ddde457eda06e319d34d55c24dbc9ae8b1`），分支 `grok/s11-arms`。允许路径里的 `framework/surprise/theory/store.py` 没有改：从给定理论创建走 `Workbench.create(..., theory=)`。

## 改了哪些文件

- `framework/surprise/experiments/loop.py`：修改。`run` 与命令行增加 `--freeze`、`--hunter`、`--theory-from`、`--select-from`。四个参数都是默认值时不写 `arm`、不加 `select_p`。`freeze=theory` 不调用 `observe` 与 Diagnoser；`freeze=diagnoser` 只做按代 checkpoint。`select_from` 用选题工作台选题，再用本次理论重预测。
- `framework/surprise/hunter/hunter.py`：修改。`Hunter(..., select="value")`；`random` 在本轮 `scope` 里用 `self.rng` 均匀抽取。新增 `remember_case`，供跨运行的正例父 SQL 使用；空的借用表不改变原有选题。
- `framework/surprise/diagnoser/diagnoser.py`：修改。新增 `checkpoint_only`；`periodic` 正文未改。
- `framework/surprise/theory/workbench.py`：修改。`create` 增加可选 `theory`。给出理论时把它存成活状态，journal、编辑历史与第 0 代保持新建存储的样子。
- `framework/tests/test_surprise_s11_arms.py`：新增。11 个测试，覆盖四个开关、各种 `UsageError`、默认运行逐行相同，以及 `select_from` 时 `p_t` 来自本次理论。

## 跑了哪些命令

工作目录均为 `framework/`。下面是各条命令的退出码和输出全文（每条都短于 20 行）。

### `python -m pytest -q testing tests`

退出码 0

```
........................ss..................................s........... [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
........................................................................ [ 44%]
........................................................................ [ 53%]
........................................................................ [ 62%]
........................................................................ [ 71%]
........................................................................ [ 80%]
........................................................................ [ 88%]
........................................................................ [ 97%]
..................                                                       [100%]
807 passed, 3 skipped in 258.48s (0:04:18)
```

### `python -m surprise.gates.s11 --only arms`

退出码 1

```
[FAIL] arms: the selecting theory's hypotheses drive refine/generalize: {'explore'}
S11 GATE [only: arms]: FAIL (0/1 groups passed)
```

### `python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`

退出码 0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (13s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (58s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (35s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### `python -m surprise.gates.s09 --only wiring replay`

退出码 0

```
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (50s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (46s)
S09 GATE [only: wiring, replay]: PASS (2/2 groups passed)
```

### `python -m surprise.gates.s10 --only frame switches m3`

退出码 0

```
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (19s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (136s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (94s)
S10 GATE [only: frame, switches, m3]: PASS (3/3 groups passed)
```

### `python -m surprise.gates.s06`

退出码 0

```
[PASS] constants: 9 constants as frozen; magnitudes 6.64, 4.32, 1.00, 0.07, 0.01 bits, split at 0.5 and 2.0; features and theory import in either order (1s)
[PASS] language: 10 reductions, 13 coverage checks, 8 generalisations, 12 specialisations; 7 malformed calls rejected (0s)
[PASS] vspace: 5 sequences (25 steps) reach the expected S and G; positions incl. undetermined and out of scope; G capped at 64; invariants hold over 480 random steps (0s)
[PASS] hypothesis: contract keeps S2-era objects and round-trips the new fields; 4 families started from profiles, one with earlier passes replayed; 2 attribution requests accepted by the harness parser (0s)
[PASS] identity: 17 hypothesis / label pairs judged: harness test first, then fix set, then the three profile fields (0s)
[PASS] residual: prior 0.01, counts and rate per unit, round trip; the rate never reaches 0 or 1 (0s)
[PASS] validity: prior 0.1; counts, reasons and rate per (class, oracle); round trip (0s)
[PASS] predict: surprise 6.64 / 4.32 / 1.00 / 0.07 / 0.01 bits; 6 zone predictions with precedence confirmed > pending > residual; per-unit rho and per-class K^v (0s)
[PASS] triage: 14 (label, bits) pairs incl. both thresholds; the six rows of the framework document; 8 bad calls rejected (0s)
[PASS] theory: 9 scripted experiments: 6.64 -> family, 1.00 x 2 -> G moves and a second family, 0.07 duplicate, 4.32 unexpected pass, 0.01 no information, invalid, unexplained failure; replay, reload and determinism; 4 drifted-residual cases; 6 bad calls rejected (0s)
[PASS] manifest: theory section: 9 constants, 16 theory files and 12 feature files hashed, vocabulary and limits; harness part and the S4 freeze verify unchanged; stored with a run; tampering reported (1s)
[PASS] walkthrough: DF-A 6.64 bits opens h2; two predictions at 1.00 bit: left_has_dups enters G, INTERSECT ALL fails with another identity and opens h3; surprises 6.64, 1.00, 1.00, 0.07, 4.32, 0.01; 6 records, surprise recomputed from the ledger (24s)
S06 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s07`

退出码 0

```
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (0s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
[PASS] imports: 16 theory files import no model and no old code; 5 import orders load in fresh processes (2s)
[PASS] edits: 20 malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic (0s)
[PASS] accept: hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not (0s)
[PASS] rollback: a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback (0s)
[PASS] journal: reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail (0s)
[PASS] mdl: merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself (1s)
[PASS] families: fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber (0s)
[PASS] ciao: mean surprise of the old records by generation: 0.537, 0.074, 0.074 bits (0s)
[PASS] replay: 74 experiments, 11 hypotheses; confirmed fail: 48, confirmed pass: 5, pending fail: 13, unexplored fail: 4, unexplored pass: 1; 47/54 repeats predicted before execution, 47 at tier 2; wrong edit e1 rolled back by s07-replay:49; compress applied [], declined ['merge:h6+h10:holdout', 'merge:h9+h11:holdout']; absorbed twice: [] (264s)
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (70s)
S07 GATE: PASS (15/15 groups passed)
```

另：`python -m pytest -q tests/test_surprise_s11_arms.py` 退出码 0，`11 passed in 45.67s`（已包含在上面的 807 里）。

## 与说明的偏差

- `select_from` 会把源运行账本里、选题理论正例对应的 SQL 记进本次 Hunter（`remember_case`）。理论存储只复制 Theory 本身，journal 与编辑历史仍为空。父用例不标成已做，也不消耗 `rng`。记录 id 与本次运行相撞时，借来的用例优先。原因：细化 / 泛化要父语句，语句在账本里，不在 Theory 里。影响：pending 区还开着时可以细化 / 泛化（新测试 `test_theory_from_and_select_from` 通过）；pending 区已经被 S 吃完时，候选池里没有这两条车道。
- S8 的 `longrun` 按说明没有跑。

## 未决问题

`python -m surprise.gates.s11 --only arms` 未通过。失败点是 `gates/s11.py` 里 `lanes & {"refine", "generalize"}`。同一函数里更早的检查已经通过：默认运行没有 `arm` / `select_p`、随机 Hunter 确定且与 value 不同、冻结理论不变、冻结 Diagnoser 仍开家族且无编辑、`theory_from` 的第一条记录用源理论版本、`select_from` 的 `p_t` 等于空理论的预测、且至少有一条 `select_p` 与 `p_fail_valid` 不同。

复现的是门槛自己的基线：`ARMS_RUN`，seed 61，duckdb，oracle `plan_variant` / `tlp` / `norec`，12 条实验，bootstrap F1 / plan_variant。基线 head 有 1 条假设，版本 `T-e21629599c6b`，oracle `plan_variant`，正例 `loop-s61:1`、`loop-s61:2`、`loop-s61:8`，`|S|=25`。账本 13 条，3 个正例都已记入 Hunter。这些正例的一步变异，用 Hunter 同一套 `phi` / registry / `position` 统计：`confirmed` 119、`undetermined` 19、`outside` 5，`pending` 0。随后 `choose` 的池子是 `refine` 0、`generalize` 0、`migrate` 0、`explore` 20。基线自己的车道是 `bootstrap`、`explore`、`generalize`：边界在运行早期还开着，跑满 12 条之后一步邻域已被 S 吸收。选题理论不再 `observe`，正例不会再变，所以 12 次选择都落在 `explore`。

这是现有 pending 过滤下的结果。放宽过滤会改默认车道，S8 `lanes` / `determinism` 与 S9 `wiring` 已经按原行为通过。本包不能改 `framework/surprise/gates/`。编排者若要这条断言在 `ARMS_RUN` 上成立，需要另定门槛：缩短这条运行，使源理论 head 仍有 pending 变异；或只在源理论还有 pending 变异时要求 `refine` / `generalize`。
