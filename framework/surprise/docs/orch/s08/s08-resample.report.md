# 报告 · s08-resample

## 改了哪些文件
- `framework/surprise/hunter/constants.py`：新增 `EMPTY_ROUNDS = 20`（int），注释一行，格式与本文件其他常数相同。
- `framework/surprise/hunter/hunter.py`：`_explore` 先按语料次序去掉 setup 已报错的种子，再抽样；该引擎一个不剩就跳过，不调用 `sample`。`choose` 每次选择只定一次 `index` 与 `slot`，最多抽 `EMPTY_ROUNDS` 轮；某一轮的选择范围非空就在该轮里按原规则选定。`pool` 的车道与三类拒绝计数是各轮合计，`scored` 与 `scored_pool` 只取选出结果的那一轮，并多一个键 `rounds`。同一轮内的键去重不跨轮。
- `framework/tests/test_surprise_s08_hunter.py`：坏 setup 不再被抽到（过滤后的种子表保持语料次序）；第一轮被新颖性抽签滤空、第二轮同一候选通过时 `rounds == 2` 且计数是两轮合计；连续 `EMPTY_ROUNDS` 轮为空返回 `None`；正常选择 `rounds == 1`。原有的 `pool` 键集合断言加上 `rounds`。

提交：`085513e` `feat(s08-resample): redraw an empty choice and skip seeds with a failed setup`，分支 `grok/s08-resample`。

## 跑了哪些命令

### `cd framework; python -m pytest -q testing tests`
退出码：0

```
........................ss..................................s........... [ 11%]
........................................................................ [ 23%]
........................................................................ [ 35%]
........................................................................ [ 46%]
........................................................................ [ 58%]
........................................................................ [ 70%]
........................................................................ [ 81%]
........................................................................ [ 93%]
........................................                                 [100%]
613 passed, 3 skipped in 115.52s (0:01:55)
```

### `cd framework; python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism`
退出码：0

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
[PASS] constants: 12 hunter and 2 diagnoser constants as planned; BETA = 1.0 (pre-experiment families per run: {'0.5': {'9001': 1, '9002': 3, '9003': 3}, '1.0': {'9001': 3, '9002': 3, '9003': 3}, '2.0': {'9001': 3, '9002': 3, '9003': 3}, '4.0': {'9001': 3, '9002': 5, '9003': 1}}) (0s)
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (49s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (28s)
S08 GATE [only: no_llm, constants, scoring, operators, candidates, lanes, determinism]: PASS (7/7 groups passed)
```

### `cd framework; python -m surprise.gates.all`
退出码：1（s08 的四组按说明允许失败；s01–s07 全部 PASS）

末 20 行：

```
[PASS] scoring: U untested 0.498 bits, adjacent 0.758; pending 0.455 after 50 probes, adjacent unexplored 1.365 at beta 2, confirmed 0 (0s)
[PASS] operators: 29 mutants of a three-statement case (4 deletions); oracle options filtered as planned (0s)
[PASS] candidates: after F1 and DF-A: {'refine': 4, 'generalize': 4, 'migrate': 2, 'explore': 81} candidates, all traceable; chose refine at 0.909 (11s)
[PASS] lanes: 32 records; executed {'bootstrap': 2, 'explore': 23, 'generalize': 3, 'refine': 4}; offered {'refine': 30, 'generalize': 31, 'migrate': 139, 'explore': 2474}; 4 families opened, 2 edits (48s)
[PASS] determinism: seed 31 twice in separate processes: 26 identical rows, labels and final theory; seed 32 differs (28s)
[FAIL] longrun: s08_runs.json has no 'longrun' entry yet
[FAIL] sawtooth: s08_runs.json has no 'longrun' entry yet
[FAIL] duplicates: s08_runs.json has no 'longrun' entry yet
[FAIL] recall: s08_runs.json has no 'recall' entry yet
S08 GATE: FAIL (7/11 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
GATES: FAIL (7/8 passed)
```

s08 失败的四组是 `longrun`、`sawtooth`、`duplicates`、`recall`，原因是 `s08_runs.json` 还没有对应条目。其余七组 PASS。

## 与说明的偏差
- `test_choose_explore_slot_ties_and_filter_counts` 末尾的 `assert blocked.pool["rejected_bad_setup"] >= 1` 没有改写、没有放宽。这条断言原来靠探索车道抽出坏 setup 再被 `choose` 滤掉。按本包的新规则，探索不再抽这些种子，而该测试在此之前没有假设，细化 / 泛化 / 迁移都是空的，计数会变成 0。因此在最后一次 `choose` 之前，用这段已经报错的 setup 观察并登记了一个父本，让细化 / 泛化车道的变异体仍然经过 `choose` 里保留的坏 setup 过滤。断言原文仍在。
- `EMPTY_ROUNDS` 的注释写在常数上一行，与 `constants.py` 里其余常数一致。说明里的代码块把同一句注释写在行尾。

## 未决问题
无。
