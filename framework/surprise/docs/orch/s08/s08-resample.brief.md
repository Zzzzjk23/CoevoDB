角色：执行者

# 工作包 s08-resample：Hunter 一轮抽空时重抽，探索只从 setup 没坏过的种子里抽

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s08-resample`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s08`（`s08-hunter`、`s08-eval`、`s08-loop` 三包都已合并，门槛在 3110d6e 为本包改过）
- 所属会话：S8（Phase 4：Hunter 与无 LLM 闭环），范围见 `framework/surprise/docs/SESSIONS.md` 的 S8 一节
- 依赖：先读 `framework/surprise/hunter/hunter.py`（`choose`、`_explore`）、`framework/surprise/hunter/constants.py`、`framework/surprise/experiments/loop.py`（`_drive` 里 `choose` 返回 None 时记 `exhausted` 并停）、`framework/surprise/gates/s08.py` 的 `check_candidates`

## 为什么要改

编排者在 DuckDB 1.1.3 上的召回 run 跑了 326 条实验就以 `exhausted` 停了（预算是 60 分钟）：某一次选择抽到的候选恰好全被过滤掉（坏 setup、新颖性抽签），`choose` 返回 None，主循环把它当成"再没有可做的实验"。DuckDB 1.5.5 上的长跑也看到了同样的苗头：第 429 次选择的 78 个探索候选里 71 个因为 setup 报过错被丢掉。种子语料里很多种子共用同一段 setup，一段 setup 报错就挡掉一大批种子，但现在 `_explore` 仍然从全部种子里抽，抽到的大半是坏的。

## 目标

1. **新常数**：`framework/surprise/hunter/constants.py` 末尾加（照现有格式带一行注释）：

   ```python
   EMPTY_ROUNDS = 20               # candidate rounds one choice may draw before the Hunter gives up
   ```

   类型 int。门槛 `gates/s08_cases.py` 已经钉了这个值。

2. **探索只从 setup 没坏过的种子里抽**（`Hunter._explore`）：对每个引擎，种子表先去掉 `tuple(seed.setup_sqls)` 在"坏 setup"集合里的那些（保持语料次序），再 `self.rng.sample(剩下的, min(EXPLORE_SEEDS_PER_STEP, len(剩下的)))`；剩下的为空就跳过这个引擎。其余不变（`choose` 里对坏 setup 的过滤保留，它还要挡住变异车道与迁移车道的候选）。

3. **一次选择可以抽多轮**（`Hunter.choose`）：`index` 与 `slot` 每次选择只定一次（不因重抽而变）。然后最多做 `EMPTY_ROUNDS` 轮：每轮 `raw = self.candidates(wb)`，照现在的规则过滤、打分、按 slot 定选择范围；范围非空就在这一轮里选（规则不变：最大 value，平分用 `self.rng.choice`），结束。范围为空就进入下一轮。`EMPTY_ROUNDS` 轮都为空才返回 None。
   - `pool` 的各项计数是**所有轮的合计**，另加一个键 `"rounds"`：这次选择用了几轮（≥ 1）。`scored` 是最后一轮（选出结果的那一轮）留下的个数，`scored_pool` 也只取最后一轮的。门槛 `candidates` 组要求 pool 的键恰好是四条车道、`rejected_known`、`rejected_bad_setup`、`rejected_novelty`、`scored`、`rounds`，并且 `scored == len(scored_pool)`。
   - 同一次选择的各轮之间，"同一轮里重复出现的键只留第一个"这条去重只在一轮之内做（各轮之间可以再出现，因为没有执行任何东西）。
   - 随机数的消耗次序照现有写法顺下来即可；同样的状态与种子必须得到同样的结果。

4. 不改主循环（`choose` 返回 None 记 `exhausted` 的语义不变，现在它只在连续 20 轮都抽空时才发生）。

5. **测试**：在 `framework/tests/test_surprise_s08_hunter*.py` 里补：(a) 坏 setup 的种子不再被抽到（给一个小语料，其中多数种子共用一段 setup，记一条该 setup 的 `setup_error` 之后，`candidates` 里不再有它）；(b) 第一轮全被过滤、第二轮有候选时，`choose` 返回第二轮的选择，`pool["rounds"] == 2`、计数是两轮的合计；(c) 连续 `EMPTY_ROUNDS` 轮都空时返回 None；(d) 正常情况下 `pool["rounds"] == 1`。可以用小语料、假的提取器与 monkeypatch 让某些轮为空。现有测试里对 `pool` 键集合的断言相应加上 `rounds`（这是说明要求的改动，不是放宽）。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/hunter/hunter.py
framework/surprise/hunter/constants.py
framework/tests/test_surprise_s08_hunter*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`、`framework/surprise/theory/`、`framework/surprise/metrics/`、`framework/surprise/baselines/`、`framework/surprise/diagnoser/`、`framework/surprise/experiments/`，以及 `hunter/` 里上面没列出的文件。觉得哪个非改不可，写进报告，停下。
- 不改任何已有常数的取值；不改打分、车道、过滤规则本身（只改上面两处）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 不调用任何 LLM；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不跑超过 15 分钟的实验，不往 `framework/results/` 写东西。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接。

```powershell
cd framework
python -m pytest -q testing tests       # 0 failed，skip 仍是 3，通过数不少于 610
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism     # 7/7，约 3 分钟
python -m surprise.gates.all            # s01–s07 全部 PASS；s08 只允许 longrun sawtooth duplicates recall 四组失败（等编排者的长跑）
```

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式同前：改了哪些文件、跑了哪些命令（命令、退出码、输出末 20 行原样）、与说明的偏差、未决问题。
3. 说明有矛盾、缺前置条件或做不完：写进报告，停下。
