角色：执行者

# 工作包 s11-dedup：离线去重对比（σ 对执行前成员检验）与 CVE 覆盖度量（重放上游回归测试）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-dedup`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（已合并 `s11-fixes` 与 `s11-runmetrics`：`surprise/metrics/rq.py` 有 `label_key(record)`，`surprise/metrics/rundata.py` 有 `RunData`）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节、`PLAN.md` 第 3 节"标签流程"最后一段与第 5 节 Phase 6
- 依赖：上面两个已合并的包；旧代码 `framework/diagnosis/signature.py`（只调用，不改）。

## 目标

两个新模块，都只**测量**，不参与打标签（PLAN："CVE 的另一半（测量 oracle 覆盖哪些缺陷：召回基准、上游回归测试重放）归 Phase 6 评估，不参与打标签"）。门槛 `gates/s11.py` 的 `dedup` 与 `coverage` 两组验收。**先把这两组的代码完整读一遍，它们就是验收标准；下文与门槛代码不一致时以门槛为准，并在报告里写明。**

### 1. `framework/surprise/metrics/dedup.py`：离线去重对比

PLAN 第 5 节："离线去重对比改为原 CoevoDB 的 σ 去重 vs 执行前成员检验"。在同一批失败上比较两种"这条失败是不是已知 bug 的重复"的判断，真值是完整 CVE 画像给出的身份（S8 的重复率裁判口径）。

`compare_dedup(run_dir, *, limit=None, reprofile=True) -> dict`：

- 失败：该运行账本里 `y == "fail"` 的记录，按 seq；`limit` 给了就只取前 `limit` 条。
- 每条失败一行 `row`：
  - `record_id`、`seq`；
  - `zone`：该记录 progress 行的 `zone`（执行前理论给的预测区）；
  - `member_dup`：`zone == "confirmed"`——执行前的成员检验判它是已知家族的重复（确认区内）；
  - `profile`：用于 σ 与真值的画像。记录自己的 `label.cve["profile"]` 是 `status == "ran"` 时就用它，`reprofiled = False`；否则（第 2 档只做了归属测试的失败）在本进程里对 `record.case` 重新 `certify(case, oracle, diagnose=True, rewrite_rule=该记录 progress 行的 rule)`，用新标签的 profile，`reprofiled = True`（`reprofile=False` 时不重做，这一行的真值与 σ 为 None，并计入 `skipped`）。重做之前核对：运行 manifest 记录的目标引擎版本与本解释器里的版本一致，不一致抛 `ValueError`（版本一变，画像就不是同一个东西）。重新画像只读不写：不写账本、不写运行目录；
  - `truth_key`：`surprise.metrics.rq.label_key` 的口径（`identity_key(engine, fix_set, fail_kind, error_class, behavior_shape)`），重画像时用新标签算；
  - `truth_dup`：`truth_key` 在本表前面的行里出现过；
  - `minimal`：最小化后的用例 dict（所用标签 `cve["minimize"]["status"] == "ran"` 时就是 `cve["minimize"]["case"]`，键为 engine / setup / query / predicate；否则是 `record.case.to_dict()`）；
  - `error_class`：所用标签的 `identity.error_class`；
  - `sigma_key`：原 CoevoDB 的 σ 键，**用旧代码算**：`diagnosis.signature.SignatureEngine(runner_factory=lambda: None, checker=None)._signature(fix_kind=profile["fix_kind"], fix_set=profile["fix_set"], plan_diff=profile["plan_diff"], nu=profile["version_ladder"], executions=profile["executions"], candidate=SimpleNamespace(r1_summary=None, r2_summary=None, notes=error_class or "", schema_sqls=[], inserts=[], q1="", q2=""), minimal={"schema_sqls": list(minimal["setup"]), "inserts": [], "q1": minimal["query"], "q2": minimal["predicate"] or ""})["key"]`。这样 σ 的身份规则（fix set 加 plan diff；定位不到时退回错误类别加用例摘要）原样来自旧代码，不重写；
  - `sigma_dup`：`sigma_key` 在前面的行里出现过；
  - `reprofiled`。
- 汇总：`{"run": run_dir 的绝对路径（str）, "failures": 行数, "skipped": 不能定真值的行数, "truth_duplicates": truth_dup 为真的行数, "sigma": {...}, "membership": {...}, "rows": [...]}`。`sigma` 与 `membership` 各为 `{"tp", "fp", "fn", "precision", "recall", "executions"}`：以 `truth_dup` 为真值、各自的 `*_dup` 为判断，tp / fp / fn 照常；precision = tp/(tp+fp)，recall = tp/(tp+fn)，分母为 0 时 None；`executions`：σ 是每行 `profile["executions"]` 之和（σ 必须执行之后做完整画像才能判断），成员检验是 0（它在执行之前就给出判断；归属测试的执行另记在 `attribution_executions`：各行所用标签 `cve["attribution"]` 里的执行次数之和，读一下 harness 的 attribution 记录格式，没有就记 0）。
- 只读：不改运行目录（门槛对目录取哈希比对）。
- 命令行：`python -m surprise.metrics.dedup RUN_DIR --out FILE [--limit N] [--no-reprofile]`。

### 2. `framework/surprise/metrics/coverage.py`：重放上游回归测试

`seeds/corpus.json` 是从上游回归测试解析出的种子（DuckDB 的 `test/sql/...`、`test/issues/...` 与 PostgreSQL 的 regress）。这些测试大多对应上游已经修好的缺陷。把它们按 oracle 重放到新旧两个版本上：旧版本上判 fail、新版本上判 pass 的，就是"我们的 oracle 能看见的、上游修过的缺陷"；新版本上也判 fail 的，要么是没修的缺陷、要么是 oracle 的误报——两者都是 oracle 覆盖度与精度的度量。

- `select(prefix="duckdb:test/", limit=None) -> list[dict]`：`seeds/corpus.json` 里 `source` 以 `prefix` 开头的条目（引擎由前缀决定，本包只做 DuckDB），保持文件顺序，取前 `limit` 条。用 `seeds/store.py` 或直接读 JSON 都行（只读）。
- `replay(seeds, oracles) -> dict`：对每个种子、每个 oracle（按给定顺序）：`SqlCase(engine="duckdb", setup=tuple(seed["setup_sqls"]), query=seed["query"], predicate=None)`，`surprise.harness.cve.certify.certify(case, oracle)`（默认参数：不画像，只要标签）；一项 `{"index": 种子在 select 结果里的位置, "source", "oracle", "y", "fail_kind", "invalid_reason"}`。返回 `{"engine": "duckdb", "version": 本解释器里 DuckDB 的版本（用 importlib.metadata，不要 import duckdb：仓库根有同名目录会遮蔽包）, "prefix", "limit", "oracles", "items": [...]}`。确定：同样的输入两次结果相同（门槛检查）。
- `compare(old, new) -> dict`：两份 `replay` 结果（旧版本、新版本，同样的 prefix / limit / oracles）。返回 `{"old_version", "new_version", "oracles": {oracle: {"old": {y: 条数}, "new": {y: 条数}, "fail_old_pass_new": [index...], "fail_both": [index...], "fail_new_only": [index...]}}}`。
- 命令行：
  - `python -m surprise.metrics.coverage run --out FILE [--prefix P] [--limit N] [--oracle NAME]...`（不给 `--oracle` 时用全部七类）；
  - `python -m surprise.metrics.coverage compare OLD.json NEW.json --out FILE`。
- 旧版本用 S8 建的 `.venvs/duckdb-1.1.3-full`（能跑整个新框架）：门槛用那个解释器执行 `python -m surprise.metrics.coverage run ...`。你的模块在 DuckDB 1.1.3 下也必须能导入、能跑（不要用 1.5.5 才有的东西）。

## 允许改动的路径

```allow-paths
framework/surprise/metrics/dedup.py
framework/surprise/metrics/coverage.py
framework/tests/test_surprise_s11_dedup.py
framework/tests/test_surprise_s11_coverage.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `metrics/` 下已有的文件，不改 `diagnosis/`、`seeds/` 等旧代码（只导入调用）。
- 两个模块都只测量：不写账本、不改运行目录、不调用 LLM。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 本包不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接（`.venvs/` 在主检出区，门槛经 git 公共目录找它，不用你处理）。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                 # 通过数不少于基线，0 failed
python -m surprise.gates.s11 --only dedup         # PASS
python -m surprise.gates.s11 --only coverage      # PASS（门槛经 git 公共目录找到主检出区的 .venvs/duckdb-1.1.3-full）
```

新测试覆盖：dedup 的每个字段与汇总（用一次很短的真实 `loop.run` 当夹具，带 F1 引导，几条实验）、`reprofile=False`、版本不符时报错、只读；coverage 的 `select` / `replay` / `compare`（`replay` 用两三个种子、一个 oracle）。测试总时长控制在 4 分钟以内。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-dedup

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
