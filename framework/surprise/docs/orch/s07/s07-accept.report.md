# 报告 · s07-accept

## 改了哪些文件
- `framework/surprise/theory/edits.py`：新增。提案、声明、指纹、押注、留出样本和接受检验。
- `framework/surprise/theory/workbench.py`：新增。在用的理论：观察、提议、押注兑付、回滚、负记忆、MDL、归属与家族。
- `framework/surprise/theory/__init__.py`：修改。导出本包的新名字，`Workbench` 放在最后导入。
- `framework/surprise/theory/store.py`：修改。日志序号缓存在实例上；`append_journal`、`last_seq`、`close_generation` 不再读日志。
- `framework/tests/test_surprise_s07_edits.py`：新增。提案校验、声明、指纹、押注、留出样本。
- `framework/tests/test_surprise_s07_workbench.py`：新增。五种拒绝、押注、回滚、级联、重开、归属、按代惊讶。
- `framework/tests/test_surprise_s07_mdl.py`：新增。合并、收紧、拆分候选，以及 `compress()` 的不动点。
- `framework/tests/test_surprise_s07_store_seq.py`：新增。打开已有日志后，追加不再读 jsonl，重新打开后续上序号。

提交：`6f454c7`（理论）、`d8a9361`（测试）。`git status` 干净。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests --tb=line`
退出码：0

```
........................ss..................................s........... [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
.................................................                        [100%]
550 passed, 3 skipped in 45.16s
```

### `cd framework; python -m surprise.gates.s07; echo EXIT:$LASTEXITCODE`
退出码：0

```
[PASS] constants: 4 new constants beside the nine of S6, all in the manifest; a change is reported by name (0s)
[PASS] length: hypothesis = 8.0 + 7.4 x |S| bits; theory = sum (0s)
[PASS] theory_api: remove, reserve_id, passes, next_id; common_conjunction agrees with generalize on 81 pairs (0s)
[PASS] store: one file per hypothesis, save/load is the identity, 22 damaged stores refused, logs append-only (0s)
[PASS] generations: closing a generation snapshots its last state and leaves the live state alone; snapshots load, predict and are checked (0s)
[PASS] imports: 16 theory files import no model and no old code; 5 import orders load in fresh processes (1s)
[PASS] edits: 20 malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic (0s)
[PASS] accept: hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not (0s)
[PASS] rollback: a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback (0s)
[PASS] journal: reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail (0s)
[PASS] mdl: merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself (1s)
[PASS] families: fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber (0s)
[PASS] ciao: mean surprise of the old records by generation: 0.537, 0.074, 0.074 bits (0s)
[PASS] replay: 74 experiments, 11 hypotheses; confirmed fail: 48, confirmed pass: 5, pending fail: 13, unexplored fail: 4, unexplored pass: 1; 47/54 repeats predicted before execution, 47 at tier 2; wrong edit e1 rolled back by s07-replay:49; compress applied [], declined ['merge:h6+h10:holdout', 'merge:h9+h11:holdout']; absorbed twice: [] (216s)
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (55s)
S07 GATE: PASS (15/15 groups passed)
EXIT:0
```

`--only` 的 13 组都在这次完整 S7 门槛里，每一组都是 PASS。

### `cd framework; python -m surprise.gates.all *> .orch/tmp/gates-all.txt; echo EXIT:$LASTEXITCODE`
退出码：0。控制台只有 `EXIT:0`。下面是程序输出的最后 20 行。

```
[PASS] imports: 16 theory files import no model and no old code; 5 import orders load in fresh processes (1s)
[PASS] edits: 20 malformed proposals refused; claims and fingerprints ignore ids and evidence; bets match by spec; held-out sample is deterministic (0s)
[PASS] accept: hand-written h2 accepted on length alone and both bets kept; a held-out pass, the trigger record, no gain, no bets each refuse an edit; only refutations enter the negative memory; 4 unexplained failures pay for a hypothesis, 1 does not (0s)
[PASS] rollback: a lost bet rolls back the edit and replays what was observed since; the claim enters the negative memory and is refused under any kind; a settled edit survives contradictions; later edits cascade without blame; manual rollback (0s)
[PASS] journal: reopening reproduces the workbench and it continues identically; the journal alone reproduces the theory; labels are kept without detail (0s)
[PASS] mdl: merge when nothing separates two hypotheses of one identity, not when a known pass lies between them; tighten after 16 contradictions, split after 40, neither earlier; compress() reaches a fixed point and does not undo itself (1s)
[PASS] families: fix-set families span oracles; a hypothesis without a fix set is its own family; owner = opened, attributed, or first absorber (0s)
[PASS] ciao: mean surprise of the old records by generation: 0.537, 0.074, 0.074 bits (0s)
[PASS] replay: 74 experiments, 11 hypotheses; confirmed fail: 48, confirmed pass: 5, pending fail: 13, unexplored fail: 4, unexplored pass: 1; 47/54 repeats predicted before execution, 47 at tier 2; wrong edit e1 rolled back by s07-replay:49; compress applied [], declined ['merge:h6+h10:holdout', 'merge:h9+h11:holdout']; absorbed twice: [] (214s)
[PASS] ledger: 24 adjudicated failures in 10 manual families: new framework 11 families, ARI 0.974, pair F1 0.976 (P 1.00 R 0.95); sigma 19 families, ARI 0.425, pair F1 0.444 (P 1.00 R 0.29); merged against the ledger: []; split against it: ['DF-D|DF-D_where'] (55s)
S07 GATE: PASS (15/15 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
GATES: PASS (7/7 passed)
```

## 与说明的偏差
无。

## 未决问题
无。
