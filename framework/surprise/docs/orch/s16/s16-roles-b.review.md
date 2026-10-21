# 审查包 · s16-roles-b

- 生成时间：2026-10-22T00:31:15+11:00
- 基线：`session/s16`（25f958058366）
- 分支：`grok/s16-roles-b` @ 890fe4df5db4，基线之上 1 个提交
- 运行：共 1 轮（返工 0 轮），最近一轮退出码 0，用时 15m52s
- 执行者：codex codex-cli 0.163.0；会话 `01a15e98-8fe4-7e22-b2ae-508354727217`

## 红旗汇总

- 门槛未通过（退出码 1）
- 派发以来有 2 处 tag 变化或 ref 被删：确认是编排者自己做的，不是执行者

自动检查只是筛子，结论要等读完完整 diff 再下：

```bash
git diff session/s16..grok/s16-roles-b
git diff -M --stat session/s16..grok/s16-roles-b
```

## 1. 改动文件（相对基线，已识别重命名）

允许路径（取自派发时的 brief）：`framework/surprise/roles/sources_map.py`、`framework/surprise/roles/source.py`、`framework/surprise/roles/runtime.py`、`framework/surprise/roles/prior.py`、`framework/surprise/roles/conjecturer.py`、`framework/surprise/roles/implementer.py`、`framework/tests/test_surprise_s16_roles.py`
禁区：`framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`

| 状态 | 路径 | 标记 |
|---|---|---|
| M | `framework/surprise/roles/conjecturer.py` |  |
| M | `framework/surprise/roles/implementer.py` |  |
| M | `framework/surprise/roles/prior.py` |  |
| M | `framework/surprise/roles/runtime.py` |  |
| M | `framework/surprise/roles/source.py` |  |
| M | `framework/surprise/roles/sources_map.py` |  |
| A | `framework/tests/test_surprise_s16_roles.py` |  |

提交：

- 890fe4d Junke: feat(roles): add optional pinned PostgreSQL source evidence

## 2. diff 统计

```text
 framework/surprise/roles/conjecturer.py    |  48 +++++++-
 framework/surprise/roles/implementer.py    |   5 +
 framework/surprise/roles/prior.py          |  28 +++--
 framework/surprise/roles/runtime.py        |   7 +-
 framework/surprise/roles/source.py         |  35 ++++++
 framework/surprise/roles/sources_map.py    |  43 +++++++
 framework/tests/test_surprise_s16_roles.py | 184 +++++++++++++++++++++++++++++
 7 files changed, 337 insertions(+), 13 deletions(-)
```

## 3. 独立复跑（在 worktree 里，环境里去掉了 DEEPSEEK_API_KEY）

`cd framework && python.exe -m pytest -q testing tests` → 退出码 0，7m53s；passed 1236，skipped 3

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 34%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 63%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 92%]
........................................................................ [ 98%]
...............                                                          [100%]
1236 passed, 3 skipped in 472.63s (0:07:52)
```

`cd framework && python.exe -m surprise.gates.all` → 退出码 1，30m00s

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (2s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (11s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (57s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (51s)
S09 GATE: PASS (12/12 groups passed)
=== gate s10 ===
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (18s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (148s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (9s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (4s)
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
- 日志 `.orch/logs/s16-roles-b.jsonl` 与 stderr 中疑似密钥行数：0

## 5. worktree 之外的变化

执行者只应动自己的分支和自己的 worktree；下面两项应当都能对上编排者自己的操作。

派发以来其他 ref 的变化：

- 删除 `refs/heads/grok/s16-core`（原 572cad1e0d7b）
- 新增 `refs/heads/grok/s16-oracles` @ 34a7cc32a5c0
- 删除 `refs/heads/grok/s16-replay`（原 572cad1e0d7b）
- 移动 `refs/heads/session/s16` 25f958058366 → bb3fe5283187

主检出区当前未提交的改动（`git status --porcelain`）：

```text
（干净）
```

## 6. 执行日志摘要

`.orch/logs/s16-roles-b.jsonl`：83 条事件（item.completed 44，item.started 34，orch.exit 1，orch.start 1，thread.started 1，turn.completed 1，turn.started 1）；各轮合计 codex：1 轮，输入 3302652 token（其中缓存 3209600），输出 21024（其中推理 5660），codex 不报美元。

被 deny 规则（grok）或 execpolicy 规则（codex，记在 stderr）拦下的调用 0 次（拦下是规则在起作用；要看的是执行者之后有没有换写法绕过去）：

- 无

最后几条：

```text
text: 验收全部通过：`1236 passed, 3 skipped`，比基线新增 31 个通过测试，skip 数未增加；S16 roles、S09、S10 均为 PASS。现在提交当前分支，并把验证输出补入报告。
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git add -- framework/surprise/roles/sources_map.py framework/surprise/roles/source.py framework/surprise…
exec [exit 0]: warning: in the working copy of 'framework/tests/test_surprise_s16_roles.py', LF will be replaced by CRLF the next time Git touches it [grok/s16-roles-b 890fe4d] feat(roles): add …
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@' from pathlib import Path import subprocess root = Path('.orch') def tail(name): data = (root / name).…
exec [exit 1]: Traceback (most recent call last): File "<stdin>", line 22, in <module> File "<stdin>", line 6, in tail File "D:\anaconda3\Lib\pathlib\_abc.py", line 625, in read_bytes with self.…
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@' from pathlib import Path import subprocess root = Path('.orch') def tail(name): path = root / name if…
exec [exit 0]: report written: .orch/report.md commit: 890fe4df5db47f248a40a42542568a8ee4eede5e git status --short: clean
exec: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; Get-Content -Encoding UTF8 .orch/report.md | Select-Object -First 8; Get-Content -En…
exec [exit 0]: # 报告 · s16-roles-b Commit: `890fe4df5db47f248a40a42542568a8ee4eede5e` on `grok/s16-roles-b`. ## 改了哪些文件 - `framework/surprise/roles/sources_map.py`：新增可选 PostgreSQL 16.15 检出常量、22 个干…
text: 工作包已完成，提交为 `890fe4d`，工作区干净。 - 测试：1236 passed，3 skipped。 - 门槛：S16 roles、S09、S10 全部 PASS。 - 无范围偏差或未决问题。 报告：[.orch/report.md](D:/CoevoDB/.claude/worktrees/s16/.worktrees/s16-roles-b/…
end: tokens in=3302652 cached=3209600 out=21024 reasoning=5660
orch.exit: {"pkg": "s16-roles-b", "run": 1, "at": "2026-10-22T00:29:31+11:00", "exitCode": 0, "timedOut": false, "error": null}
```

## 7. 执行者报告（`.orch/report.md`，自述，未经核实）

````markdown
# 报告 · s16-roles-b

Commit: `890fe4df5db47f248a40a42542568a8ee4eede5e` on `grok/s16-roles-b`.

## 改了哪些文件

- `framework/surprise/roles/sources_map.py`：新增可选 PostgreSQL 16.15 检出常量、22 个干预的源码文件映射及 11 条特征规则。
- `framework/surprise/roles/source.py`：新增 `open_extra_sources` 和 `readers_for`，缺失或 commit 不符时输出一行 ASCII 提示；原有 `source_roots`、`open_sources` 未改。
- `framework/surprise/roles/runtime.py`：按目标引擎调用 `readers_for(engines)`。
- `framework/surprise/roles/prior.py`：PostgreSQL 证据只读取固定检出的 `doc/src/sgml/release-16.sgml`，不扫描相邻文档。
- `framework/surprise/roles/conjecturer.py`：新增 PostgreSQL fix set 与特征选片段分支，保留 DuckDB、DataFusion 分支原文。
- `framework/surprise/roles/implementer.py`：新增 PostgreSQL 16 方言和事务、search_path、角色及非超级用户限制提示。
- `framework/tests/test_surprise_s16_roles.py`：新增 31 个离线测试，覆盖真实源码检出、commit 校验、证据来源、映射与预算，并写死改动前计算的 10 组旧引擎输出 SHA-256。

## 跑了哪些命令

### `pytest -q tests/test_surprise_s16_roles.py 2>&1 | Tee-Object -FilePath ../.orch/test-s16-roles.log; exit $LASTEXITCODE`

Exit code: 2

```text

=================================== ERRORS ====================================
______________ ERROR collecting tests/test_surprise_s16_roles.py ______________
ImportError while importing test module 'D:\CoevoDB\.claude\worktrees\s16\.worktrees\s16-roles-b\framework\tests\test_surprise_s16_roles.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda3\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_surprise_s16_roles.py:12: in <module>
    from diagnosis.bisect import POSTGRES_GUC_INTERVENTIONS
E   ModuleNotFoundError: No module named 'diagnosis'
=========================== short test summary info ===========================
ERROR tests/test_surprise_s16_roles.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.20s
```

### `python -m pytest -q tests/test_surprise_s16_roles.py 2>&1 | Tee-Object -FilePath ../.orch/test-s16-roles-final.log; exit $LASTEXITCODE`

Exit code: 0

```text
...............................                                          [100%]
31 passed in 1.28s
```

### `pytest -q testing tests 2>&1 | Tee-Object -FilePath ../.orch/test-all.log; exit $LASTEXITCODE`

Exit code: 0

```text
........................ss..................................s........... [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
........................................................................ [ 23%]
........................................................................ [ 29%]
........................................................................ [ 34%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 63%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 92%]
........................................................................ [ 98%]
...............                                                          [100%]
1236 passed, 3 skipped in 532.07s (0:08:52)
```

### `python -m surprise.gates.s16 --only roles 2>&1 | Tee-Object -FilePath ../.orch/gate-s16-roles.log; exit $LASTEXITCODE`

Exit code: 0

```text
python : optional source checkout unavailable for postgres: missing directory or commit mismatch
所在位置 行:2 字符: 1
+ python -m surprise.gates.s16 --only roles 2>&1 | Tee-Object -FilePath ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (optional source...commit mismatch:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
[PASS] roles: optional postgres checkout 7d3e000c5961 (roles constants unchanged); 8 release-note evidence lines; memoize -> ['src/backend/executor/nodeMemoize.c']; dialect hint present (1s)
S16 GATE [only: roles]: PASS (1/1 groups passed)
```

### `python -m surprise.gates.s09 2>&1 | Tee-Object -FilePath ../.orch/gate-s09.log; exit $LASTEXITCODE`

Exit code: 0

```text
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (2s)
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] reject: 9 replies parsed as planned; refusals replay as refusals; the implementer refuses before phi (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
[PASS] implementer: accepted, retried with feedback, unmet, bad case, replayed, blocked (0s)
[PASS] conjecturer: selection picks datafusion/expr/src/logical_plan/builder.rs for DF-A and src/optimizer/filter_pushdown.cpp for ('filter_pushdown',); registered with a revise whose bets are its predictions; settled by experiments; refusals, drops, not covering, blocked (12s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (68s)
[PASS] implementer_report: phi-check pass rate 0.97 at the first try, 1.00 after 2 tries (30/30); boundary 10/10, core 10/10, whole 10/10 (1s)
[PASS] dfa: mechanism: LogicalPlanBuilder::intersect_or_except implements EXCEPT ALL as a LeftAnti hash join with NullEqualsNull, so it removes every left row having any match instead; trigger ['ast:set_op:except_all', 'ast:stmt:select', 'data:setop:left_has_dups']; 4 predictions (fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_null+data:setop:right_has_null+data:table:has_null+data:type:integer without data:setop:left_has_dups+data:table:dup_rows; fail on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:setop:left_has_null+data:setop:right_has_null+data:table:dup_rows+data:table:has_null+data:type:integer; pass on ast:set_op:except_all+ast:stmt:select+data:setop:left_has_dups+data:table:dup_rows+data:table:empty+data:type:integer without data:setop:left_has_null+data:setop:right_has_null+data:table:has_null); proposed as e1, accepted (0s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (64s)
S09 GATE: PASS (12/12 groups passed)
```

### `python -m surprise.gates.s10 2>&1 | Tee-Object -FilePath ../.orch/gate-s10.log; exit $LASTEXITCODE`

Exit code: 0

```text
[PASS] isolation: 4 role modules load no model client; loop, Hunter, Diagnoser and harness never import the roles (1s)
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (6s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (26s)
[PASS] switches: all on: calls {'implementer': 4, 'conjecturer': 1, 'prior': 3, 'translator': 1, 'vocab_inventor': 1, 'oracle_inventor': 1}; each role off: no call, no ledger line, plugin module not loaded (191s)
[PASS] prior: 20 units priced in 2 calls; evidence from the checkouts (40 lines); bad prior weight -> 0.0 after 20; useful prior weight 0.490 (1s)
[PASS] translator: DF-A family -> DuckDB translated once; settled {'tr-match': ('kept', 'match'), 'tr-mismatch': ('kept', 'mismatch'), 'tr-broken': ('broken', None), 'tr-void': ('void', None)}; bad switch refused; unmet spec retried (10s)
[PASS] vocab_inventor: accepted ast:set_op:except_all_two_tables on held-out records; refused {'empty': 'pattern', 'long': 'pattern', 'catastrophic': 'scan', 'everything': 'scan', 'no_exclusion': 'train', 'train_only': 'holdout'} and a data-layer id; prompt hides the held-out records (21s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
[PASS] translator_real: F2 (duckdb) -> datafusion: status ok, expect pass, switches []; label pass; settled kept identity None (5s)
[PASS] m3: 32 experiments and 43 calls replayed from the cache, identical; calls {'conjecturer': 2, 'oracle_inventor': 1, 'implementer': 36, 'prior': 4}; DF-B (shape|datafusion|wrong_result|-|extra_only) reached at experiment 3 via bet (bet from c1 on h1); lanes {'bootstrap': 1, 'generalize': 2, 'bet': 7, 'refine': 4, 'implement': 18} (109s)
S10 GATE: PASS (12/12 groups passed)
```

### `git diff --check 2>&1 | Tee-Object -FilePath .orch/diff-check.log; exit $LASTEXITCODE`

Exit code: 0

```text

```

### `git commit -m "feat(roles): add optional pinned PostgreSQL source evidence" 2>&1 | Tee-Object -FilePath .orch/commit.log; exit $LASTEXITCODE`

Exit code: 0

```text
[grok/s16-roles-b 890fe4d] feat(roles): add optional pinned PostgreSQL source evidence
 7 files changed, 337 insertions(+), 13 deletions(-)
 create mode 100644 framework/tests/test_surprise_s16_roles.py
```

### Offline runtime manifest check

```powershell
@'
import tempfile
from pathlib import Path
from surprise.roles.constants import SOURCE_COMMITS, SOURCE_DIRS
from surprise.roles.runtime import build_roles
from surprise.roles.sources_map import EXTRA_SOURCE_COMMITS, EXTRA_SOURCE_DIRS
legacy = {engine: {'dir': directory, 'commit': SOURCE_COMMITS[engine]} for engine, directory in SOURCE_DIRS.items()}
with tempfile.TemporaryDirectory(dir='../.orch', prefix='runtime-check-') as tmp:
    for engine in ('duckdb', 'datafusion', 'postgres'):
        root = Path(tmp) / engine
        roles = build_roles({'roles': ['implementer'], 'network': False, 'cache': root / 'cache', 'max_calls': 0}, run_dir=root, extract=None, registry=None, engines=(engine,), seed=0)
        try:
            expected = dict(legacy)
            if engine == 'postgres':
                expected['postgres'] = {'dir': EXTRA_SOURCE_DIRS['postgres'], 'commit': EXTRA_SOURCE_COMMITS['postgres']}
            assert roles.manifest()['sources'] == expected
            assert roles._gateway.totals()['network'] == 0
            print(engine + ' runtime source manifest and zero network calls: PASS')
        finally:
            roles.close()
'@ | python - 2>&1 | Tee-Object -FilePath ../.orch/runtime-check.log; exit $LASTEXITCODE
```

Exit code: 0

```text
duckdb runtime source manifest and zero network calls: PASS
datafusion runtime source manifest and zero network calls: PASS
postgres runtime source manifest and zero network calls: PASS
```

### Initial runtime diagnostic script

```powershell
@'
import tempfile
from pathlib import Path
from surprise.roles.constants import SOURCE_COMMITS, SOURCE_DIRS
from surprise.roles.runtime import build_roles
from surprise.roles.sources_map import EXTRA_SOURCE_COMMITS, EXTRA_SOURCE_DIRS
legacy = {engine: {'dir': directory, 'commit': SOURCE_COMMITS[engine]} for engine, directory in SOURCE_DIRS.items()}
with tempfile.TemporaryDirectory(dir='../.orch', prefix='runtime-check-') as tmp:
    for engine in ('duckdb', 'datafusion', 'postgres'):
        root = Path(tmp) / engine
        roles = build_roles({'roles': ['implementer'], 'network': False, 'cache': root / 'cache', 'max_calls': 0}, run_dir=root, extract=None, registry=None, engines=(engine,), seed=0)
        try:
            expected = dict(legacy)
            if engine == 'postgres':
                expected['postgres'] = {'dir': EXTRA_SOURCE_DIRS['postgres'], 'commit': EXTRA_SOURCE_COMMITS['postgres']}
            assert roles.manifest()['sources'] == expected
            assert roles._gateway.totals()['calls'] == 0
            print(engine + ' runtime source manifest and zero calls: PASS')
        finally:
            roles.close()
'@ | python -
```

Exit code: 1

```text
Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
KeyError: 'calls'
```

### Static invariance checks

Compared source_roots/open_sources ASTs and the original DuckDB/DataFusion selection block with HEAD before commit. Exit code: 0.

```text
source_roots/open_sources unchanged: PASS
DuckDB/DataFusion selection branches unchanged: PASS
```

### `git status --short`

Exit code: 0

```text
```

Validation notes: the initial standalone pytest invocation omitted the project import path normally added by testing/conftest.py; python -m pytest passed all 31 new tests. The initial extra smoke script used a nonexistent gateway totals field; correcting the diagnostic to network passed. Neither issue required production or baseline-test changes. S16 stderr is the expected optional-checkout warning from its empty-root check.

## 与说明的偏差

无。未修改已有测试、冻结常量、harness 或文档；未连接服务器，未调用真实 LLM，未打 tag、合并或推送。

## 未决问题

无。
````

## 8. 结论（编排者填）

合并 / 返工 / 推翻 / 升级，理由：
