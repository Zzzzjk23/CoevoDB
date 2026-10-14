# 返工意见 · s08-hunter · 第 1 轮

你报告的三处未决问题都成立，原因在编排者的说明与门槛，不在你的实现。处理如下。

## 编排者已经做的

- 门槛已在会话分支改好（提交 `e2d9a5b`），并由编排者合进了你的分支（合并提交 `b4bfb93`，不要回退、不要 rebase）。你的 worktree 里的 `framework/surprise/gates/s08.py` 现在是新的：
  - `operators` 组：用例里第 1、2 行相同，删其中任一得到同一个用例，按去重只留第一次；门槛现在期望 `s:drop_row[1][0]`、`s:drop_row[1][1]`、`s:drop_insert[1]`、`s:drop_insert[2]` 四个。你的实现不用为此改动。
  - `candidates` 组：泛化的判定改了，见下面第 1 条。

## 要你改的

1. **泛化 = 换成 S 里还没有的同类取值**（`framework/surprise/hunter/hunter.py` 的 `_refine_generalize`）。说明第 5 节原来写的 `swapped = [(l, s) for l in missing for s in registry.siblings(l) if s in closure]` 太宽：查询里另有一个比较（同类的另一个取值本来就在 S 里）时，删掉一个比较也被算成"换值"，结果 F1 与 DF-A 之后一个细化都没有。改成：

   ```python
   swapped = [(lit, sib) for lit in missing for sib in self._registry.siblings(lit)
              if sib in closure and sib not in hypothesis.specific]
   ```

   其余不变：有 `swapped` 是 `generalize`，否则 `refine`；目标规格的 `required` 是"S 里不在 missing 中的"加上 `swapped` 里的 `sib`，`forbidden` 是 `sorted(missing)`。编排者用你的代码核对过：F1 的假设下待定区的变体有 2 个细化、5 个泛化，DF-A 的有 3 个细化、1 个泛化。
   相应地改 `framework/tests/test_surprise_s08_hunter*.py` 里涉及这个判定的测试，并加一条：父本里两个比较、变异删掉其中一个（另一个仍在 S 里）时是 `refine`；把一个比较换成 S 里没有的另一种比较时是 `generalize`。

2. **`framework/tests/test_surprise_s06_constants.py`**：本轮把这个文件加进允许路径，只做一件事：在 `EXPECTED` 里加上 `"BETA": 1.0`（S7 加常数时也是这样改的）。别的断言一个字不动。这是编排者派发时漏放的路径。

## 允许改动的路径（本轮）

原说明的三条，加上：

```allow-paths
framework/tests/test_surprise_s06_constants.py
```

## 本轮的验收命令

```powershell
cd framework
python -m pytest -q testing tests       # 0 failed，skip 仍是 3，通过数不少于 575
python -m surprise.gates.s08 --only scoring operators candidates     # 3/3
python -m surprise.gates.s06            # 12/12
python -m surprise.gates.all            # s01–s07 全部 PASS；s08 只允许 no_llm constants lanes determinism longrun sawtooth duplicates recall 失败（属于别的包与编排者）
```

报告照原格式更新 `.orch/report.md`（覆盖写），"跑了哪些命令"贴本轮的输出。
