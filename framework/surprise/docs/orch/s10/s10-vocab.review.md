# 审查包 · s10-vocab

- 生成时间：2026-10-15T22:57:26+11:00
- 基线：`session/s10`（68525582afb0）
- 分支：`grok/s10-vocab` @ 153e045a58cf，基线之上 2 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 34m07s
- grok：grok 1.0.46 (2765805b9442)；会话 `31c2526f-b823-4832-be1f-60c85f2ddc84`

## 红旗汇总

- 门槛未通过（退出码 1）

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s10..grok/s10-vocab
git diff -M --stat session/s10..grok/s10-vocab
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/vocab_inventor.py`、`framework/surprise/features/registry.py`、`framework/tests/test_surprise_s10_vocab_inventor.py`、`framework/tests/test_surprise_s10_registry_regex.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/features/registry.py` |  |
| A | `framework/surprise/roles/vocab_inventor.py` |  |
| A | `framework/tests/test_surprise_s10_registry_regex.py` |  |
| A | `framework/tests/test_surprise_s10_vocab_inventor.py` |  |

提交：

- 57fd2db Junke: feat(s10-vocab): refuse regexes that match the empty string
- 153e045 Junke: feat(s10-vocab): accept an AST feature only after a hold-out check

## 2. diff 统计

```text
 framework/surprise/features/registry.py            |   3 +
 framework/surprise/roles/vocab_inventor.py         | 585 +++++++++++++++++++++
 .../tests/test_surprise_s10_registry_regex.py      |  63 +++
 .../tests/test_surprise_s10_vocab_inventor.py      | 484 +++++++++++++++++
 4 files changed, 1135 insertions(+)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，3m01s；passed 747，skipped 3

```text
........................ss..................................s........... [  9%]
........................................................................ [ 19%]
........................................................................ [ 28%]
........................................................................ [ 38%]
........................................................................ [ 48%]
........................................................................ [ 57%]
........................................................................ [ 67%]
........................................................................ [ 76%]
........................................................................ [ 86%]
........................................................................ [ 96%]
..............................                                           [100%]
747 passed, 3 skipped in 180.61s (0:03:00)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，18m15s

```text

[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (18s)
[FAIL] switches: ValueError: role 'translator' is not available: No module named 'surprise.roles.translator'
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[FAIL] translator: ModuleNotFoundError: No module named 'surprise.roles.translator'
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[FAIL] translator_real: ModuleNotFoundError: No module named 'surprise.roles.translator'
[FAIL] m3: gates/s10_llm/m3 is missing: the orchestrator records it with real calls after the merge
S10 GATE: FAIL (7/12 groups passed)
=== summary ===
s01: PASS
s02: PASS
s03: PASS
s04: PASS
s05: PASS
s06: PASS
s07: PASS
s08: FAIL (exit 1)
s09: PASS
s10: FAIL (exit 1)
GATES: FAIL (8/10 passed)
```

## 4. 扫描（只看相对基线新增或删除的行）

### 4.1 新增的 skip / xfail / 排除测试

- 无

### 4.2 测试里被删的断言

- 无

### 4.3 测试里被改写的断言（可能放宽）

- 无

### 4.4 新增的宽泛异常捕获

- 无

### 4.5 测试配置改动（conftest 等）

- 无

### 4.6 疑似密钥（值已打码）

- 无
- 日志 `.orch/logs/s10-vocab.jsonl` 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 移动 `refs/heads/grok/s10-translator` 68525582afb0 → dfdfe0532da7
- 移动 `refs/heads/session/s10` 68525582afb0 → a85568172011

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s10-vocab.jsonl`：4020 条事件（auto_compact_completed 1，auto_compact_started 1，available_commands 73，end 1，orch.exit 1，orch.start 1，text 762，thought 2419，tool_call 140，tool_call_update 555，usage 66）；各轮合计 66 个模型回合，grok 上报花费 1.4760 美元（没上报的轮次按 0 计）。

被 deny 规则拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
thought: 正在考虑是否需要记录首次闪存失败的情况。 决定完整记录两次闪存调用：首次失败的导入阶段，以及成功执行的调用。不编造此前会话中缺失的10测试尾部输出，也不补充基线737的原始结果。 基线737的原始尾部输出不在当前日志中，仅以“此前会话记录”引用。本次报告将如实写明基线为737 passed、3 skipped，后测套件为747 passed、3 skipp…
tool_call write: {"file_path": "D:\\CoevoDB\\.worktrees\\s10-vocab\\.orch\\report.md", "content": "# 报告 · s10-vocab\n\n## 改了哪些文件\n- `framework/surprise/features/registry.py`：修改。正则编译成功后，`re.search(…
tool_update [completed]: {"type": "SearchReplace", "EditsApplied": {"old_string": "", "new_string": "# 报告 · s10-vocab\n\n## 改了哪些文件\n- `framework/surprise/features/registry.py`：修改。正则编译成功后，`re.search(patter…
tool_call run_terminal_command: {"command": "git status --short; git check-ignore -v .orch/report.md .orch/tmp/vocab-flash-summary.json; git log -2 --oneline", "description": "Confirm report is ignored and the b…
tool_update [in_progress]: 
tool_update [in_progress]: .gitignore:16:.orch/.orch/report.md .gitignore:16:.orch/.orch/tmp/vocab-flash-summary.json
tool_update [in_progress]: .gitignore:16:.orch/.orch/report.md .gitignore:16:.orch/.orch/tmp/vocab-flash-summary.json 153e045 feat(s10-vocab): accept an AST feature only after a hold-out check
tool_update [completed]: exit: 0 .gitignore:16:.orch/.orch/report.md .gitignore:16:.orch/.orch/tmp/vocab-flash-summary.json 153e045 feat(s10-vocab): accept an AST feature only after a hold-out check 57fd2…
thought: 工作区干净，没有未提交的更改。
text: 工作包 `s10-vocab` 已完成，提交在分支 `grok/s10-vocab` 上，工作区是干净的。报告在 `.orch/report.md`。 - `57fd2db`：注册表拒绝能匹配空串的正则。 - `153e045`：词汇发明者与测试。意外通过在确认区达到阈值后提议一个 AST 正则特征，留出验收通过才写入 `vocabulary.json`。…
end: stopReason=end_turn turns=66 cost_usd=1.47603452
orch.exit: {"pkg": "s10-vocab", "run": 1, "at": "2026-10-15T22:57:14+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s10-vocab

## 改了哪些文件
- `framework/surprise/features/registry.py`：修改。正则编译成功后，`re.search(pattern, "")` 不为 None 就拒绝（空正则、`a*`、`(?:)` 这类恒真）。
- `framework/surprise/roles/vocab_inventor.py`：新增。确认区里的意外通过达到阈值后提议一个 AST 正则特征；留出验收通过才写入 `vocabulary.json`。本次运行的理论与 `ctx.registry` 不改。
- `framework/tests/test_surprise_s10_registry_regex.py`：新增。空正则与恒真正则被拒，原有能登记的正则仍能登记。
- `framework/tests/test_surprise_s10_vocab_inventor.py`：新增。调用时机、留出与提示、五种拒收原因（含灾难性正则在时限内被杀）、收下后的提取、累积写入、`build_roles`。

提交：`57fd2db`（注册表）、`153e045`（角色与测试），分支 `grok/s10-vocab`。未打 tag。

## 跑了哪些命令

改动前的全量测试（本会话日志里已没有那次输出的原文；当时记下的结果）退出码 0，摘要为 `737 passed, 3 skipped in 160.13s`。改动后的全量是 747 passed、3 skipped。

```text
cd framework
python -m pytest -q testing tests
```

退出码 0。输出最后 13 行（文件一共 13 行）：

```text
........................ss..................................s........... [  9%]
........................................................................ [ 19%]
........................................................................ [ 28%]
........................................................................ [ 38%]
........................................................................ [ 48%]
........................................................................ [ 57%]
........................................................................ [ 67%]
........................................................................ [ 76%]
........................................................................ [ 86%]
........................................................................ [ 96%]
..............................                                           [100%]
747 passed, 3 skipped in 180.64s (0:03:00)
EXIT:0
```

```text
cd framework
python -m surprise.gates.s05
```

退出码 0。输出最后 11 行（文件一共 11 行）：

```text
[PASS] vocab: 166 core entries (131 leaves) with hierarchy; open families; digest 1e001c14a030 stable across processes; invented feature registered, 8 bad ones rejected, saved and loaded; phi container (1s)
[PASS] spec: 12 hand-written phi / spec pairs judged as expected; 3 malformed specs rejected (0s)
[PASS] units: 23 hand-written feature sets project onto the expected units (0s)
[PASS] ast: 74 probes, 5 fallbacks, 3 invariance pairs; 12 families show their core features and are pairwise distinct (66 pairs) (0s)
[PASS] dynamic: 13 data probes on two engines, 6 measured plans; failing setup, ast-only and isolated extraction behave (2s)
[PASS] stable: 25 cases (12 families, 13 corpus seeds): two processes and this one agree (21s)
[PASS] distinguish: 12 families: pairwise distinct by statement text alone (66 pairs) and by phi; DF-A -> DF-B is one sibling swap; 11 measured units (0s)
[PASS] specs: 17 hand-written spec / SQL pairs, all judged correctly (0s)
[PASS] corpus: 1092 seeds in 76 units over 10 constructs; ast fallback 34, plan ok 480, data ok 483; top [('postgres|plain|none|unknown', 134), ('duckdb|plain|none|unknown', 83), ('duckdb|window|none|unknown', 56)]; 13s (27s)
S05 GATE: PASS (9/9 groups passed)
EXIT:0
```

```text
cd framework
python -m surprise.gates.s10 --only constants frozen library frame prior oracle_inventor vocab_inventor
```

退出码 0。输出最后 9 行（文件一共 9 行）：

```text
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (4s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (19s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
S10 GATE [only: constants, frozen, library, frame, prior, oracle_inventor, vocab_inventor]: PASS (7/7 groups passed)
EXIT:0
```

```text
cd framework
python -m surprise.gates.s09 --only isolation wiring replay
```

退出码 0。输出最后 5 行（文件一共 5 行）：

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (49s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (46s)
S09 GATE [only: isolation, wiring, replay]: PASS (3/3 groups passed)
EXIT:0
```

按说明没有跑：s10 的 `isolation` 与 `switches`、`translator_real`、`m3`、`python -m surprise.gates.all`。没有往 `framework/results/` 写东西（该目录在真实调用前后都不存在）。

可选真实调用：1 次，档位 fast，模型 `deepseek-flash`，`max_calls=1`。缓存与词表在 `.orch/tmp/vocab-flash-run/`，不入库。第一次辅助脚本在导入阶段退出码 1（`ModuleNotFoundError: No module named 'surprise'`），没有发出网络请求。改正导入路径后的命令：

```text
python .orch\tmp\vocab_flash.py
```

退出码 0。模型给出的正则（账本里的转义形式）：

`FROM\s+([A-Za-z_]\w*)\s+EXCEPT\s+ALL\s+SELECT\s+\w+\s+FROM\s+(?!\1\b)[A-Za-z_]\w*`

特征 id `ast:set_op:left_right_tables_differ`，父类 `ast:set_op`。验收收下。`prediction_kept` 为 true。训练：正例 2、矛盾 1、排除 1。留出：正例 1、命中 1、矛盾 1、排除 1。`corpus_share` 为 0.0。输出最后 20 行：

```text
    ],
    "rejected": {}
  },
  "proposals": [
    {
      "type": "proposal",
      "family": "datafusion|h1",
      "hypothesis_id": "h1",
      "status": "accepted",
      "reason": null,
      "detail": null,
      "feature_id": "ast:set_op:left_right_tables_differ",
      "pattern": "FROM\\s+([A-Za-z_]\\w*)\\s+EXCEPT\\s+ALL\\s+SELECT\\s+\\w+\\s+FROM\\s+(?!\\1\\b)[A-Za-z_]\\w*",
      "prediction_kept": true,
      "key": "3dd1b80d1ad70d0e1759ff4643ff7a5cbad016ad45614ce6b916acc2f6c00ae5"
    }
  ],
  "ledger_path": null
}
EXIT:0
```

## 与说明的偏差
- 特征 id 在 `is_feature_id` 和 `parent + ":"` 之外，还要求冒号后是一个 `[a-z0-9_]+`。不过则原因 `definition`、详情 `id`。说明正文要求「小写 token」，编号验收条款没有写字符类。门槛用的 id 能过；这次 flash 给出的 id 也能过。
- 训练判断用的注册表副本是 `Registry(dict(draft._defs))`。`Registry` 没有公开的复制方法。`accept` 替换副本里的条目，不改原来的定义，也不改 `ctx.registry`。
- 已经收下的 id，除了 `ctx.registry` 和本进程的 `accepted()`，也查 `vocabulary.json`。重复 id 的原因仍是 `definition`。
- 账本 `detail` 用的是实现里的短名字：`feature` / `fields` / `parent` / `id` / `known` / `register`，`compile` / `length` / `empty`，`timeout` / `corpus_share` / `error`，`missed_positive` / `no_exclusion`。门槛只核对原因名。
- 种子语料文件不存在时抛 `FileNotFoundError`，读出来是空的抛 `RuntimeError`。不把命中比例当成 0。
- 注册表挡空匹配用 `re.search(pattern, "")`，不带 `IGNORECASE`。发明者在登记前再用 `re.IGNORECASE` 查一次。两处都按说明各自的写法。

## 未决问题
无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：

合并。唯一的红旗是门槛：S10 其余组要等翻译者包与录制，S08 只差长跑重钉。注册表只加了"能匹配空串的正则拒绝"一处（S5 留的事）；S05 9/9。偏差（特征 id 冒号后只许 `[a-z0-9_]+`）接受。执行者 1 次真实调用，模型给的正则（左右两侧表名不同）过了留出验收。
