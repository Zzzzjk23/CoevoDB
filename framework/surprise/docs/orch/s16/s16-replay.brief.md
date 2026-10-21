角色：执行者

# 工作包 s16-replay：EXPERIMENT §8 的回放工具

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s16-replay`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s16`
- 所属会话：S16（PostgreSQL 目标，解冻 harness 第一批），范围见 `framework/surprise/docs/SESSIONS.md` 的 S16 一节；回放检查的规则见 `framework/surprise/docs/EXPERIMENT.md` §8
- 依赖：无（只用现有的 `metrics/rundata.py`、`harness/cve`、`harness/manifest.py`）

## 目标

每次解冻 harness 之后，要用新 harness 回放旧账本里的一批记录，确认 DuckDB 等已有目标的标签没有变（EXPERIMENT §8："按 oracle 与标签分层抽 2000 条，`y`、oracle、身份证据、CVE 各档结果要逐条相同；本来就标成重跑不稳定或超时的记录只要求仍是 `invalid`。有一条不同就停下来查"）。本包写这个工具。

新文件 `framework/surprise/metrics/replay.py`，命令行：

```
python -m surprise.metrics.replay RUN_DIR --sample N --seed S --out FILE [--workers K]
```

1. 读：`RunData.open(RUN_DIR).iter_records(keep_detail=False)`（流式，不要一次读进全部记录）。
2. 分层抽样：层的键是 `f"{record.label.oracle}|{record.label.y}"`。按各层记录数按比例分配 N（最大余数法），每个非空层至少 1 条，总数恰好是 N（记录不足 N 条就全取）。层内用 `random.Random(S)` 抽，结果按 `record.seq` 排序。同样的 RUN_DIR、N、S 必须抽出同样的记录。
3. 回放每条：`surprise.harness.cve.certify(record.case, record.label.oracle, diagnose=<原记录 cve.profile.status == "ran">, rewrite_rule=<原记录 spec["rule"]，没有则 None>)`，其余参数用默认值（进程隔离、默认 factory 与参照）。不传假设：第 2 档（归属测试）要用当时的理论重建假设，本工具不回放它。
4. 比对：
   - 原记录 `invalid_reason` 是 `unstable_rerun` 或 `timeout` 的：只要求回放结果 `y == "invalid"`（记进 `invalid_kept`）。
   - 其余：`y`、`oracle`、`fail_kind`、`invalid_reason`、`identity`（`switches`、`error_class`、`behavior` 整个）必须相同；`cve` 的 `rerun`、`premise` 两档必须相同；原记录第 3 档跑过（`profile.status == "ran"`）时 `minimize`、`profile` 也必须相同；原记录跑过第 2 档（`attribution.status == "ran"`）的，`attribution`、`tier` 以及因归属而跳过的 `minimize`/`profile` 不比，计入 `attribution_not_replayed`。`detail` 不比（§8 没有要求，里面有引擎版本等会随环境变的内容）。
   - 回放本身抛异常：算作不同，`fields` 里记 `{"exception": "<类名>: <消息>"}`。
5. `--workers K`（默认 1）：用 K 个子进程并行回放；输出与 K 无关（按 `seq` 排序）。
6. 输出 `--out` 的 JSON（`sort_keys`、ASCII）：
   ```json
   {"schema": 1,
    "harness": "<harness_hash()['hash']>",
    "source": {"run_dir": "<RUN_DIR 在 framework/ 下时写相对 framework/ 的 POSIX 路径，否则绝对路径>",
               "ledger_sha256": "<manifest.file_digest(ledger.sqlite)>", "records": <记录总数>},
    "sample": N, "seed": S, "sampled": <实际抽到的条数>,
    "strata": {"<oracle>|<y>": {"records": <层内记录数>, "sampled": <抽到数>}},
    "same": <相同条数>, "invalid_kept": <只要求仍 invalid 且确实 invalid 的条数>,
    "attribution_not_replayed": <条数>,
    "different": [{"record_id": "...", "seq": n, "oracle": "...", "fields": {"<字段>": [<原>, <新>]}}],
    "elapsed_s": <秒>}
   ```
   `different` 为空表示通过；进程退出码：没有不同 0，有不同 1，用法错误 2。终端打印一行 ASCII 摘要。
7. 测试 `framework/tests/test_surprise_s16_replay.py`：在临时目录里用主循环跑一个很小的 DuckDB 运行（`surprise.experiments.loop.run(..., engines=("duckdb",), max_experiments=…)`，LLM 全关）当素材，验证抽样的分配与确定性（同 seed 同结果、不同 workers 同结果）、回放无差异时退出码 0、人为篡改账本里一条记录的标签（复制一份账本再改，不要改原件）之后报出那一条且退出码 1、`unstable_rerun`/`timeout` 的放宽规则、`run_dir` 的相对路径写法。

## 背景

- 门槛 `s16.py --only replay` 会用它回放 `framework/results/s08/longrun`（S8 长跑，DuckDB 1.5.5，9400 条，解冻前的 harness 跑出的；worktree 里没有这个目录，只在编排者的检出里有）：现场抽 200 条（`--seed 16 --workers 2`）要求无差异，另核对编排者入库的 2000 条全量回放记录。worktree 里跑不了这一组，你只需要让测试覆盖上面的规则。
- 原记录的 `cve` 结构见 `harness/cve/certify.py`（`_skipped_cve`、`_tier1`、第 2 / 3 档的写法）；`ExperimentRecord` 见 `harness/contracts.py`。
- 主循环对没有假设的候选用 `diagnose=True`，有假设的用 `hypothesis=...`（`experiments/loop.py` 的 `_execute`）；所以"原记录第 3 档跑过"等价于 `profile.status == "ran"`。

## 允许改动的路径

```allow-paths
framework/surprise/metrics/replay.py
framework/tests/test_surprise_s16_replay.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`.codex/`、`tools/orch/`、`framework/surprise/harness/`（冻结）。
- 不改 `framework/results/` 下任何东西（钉住的产物）。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。这一条管基线里已有的测试与门槛：其中某个测试确实该改，就写进报告的"未决问题"，停下。本包新写的测试照常修改，只要改完仍检查这份说明要求的东西。
- 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。
- 标签路径上不调用 LLM；本包不需要任何 LLM 调用。密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
pytest -q testing tests                                  # 基线通过数上只增不减，skip 不增加
pytest -q tests/test_surprise_s16_replay.py              # 全部通过
python -m surprise.metrics.replay --help                 # 退出码 0
```

不用跑 `python -m surprise.gates.all`：worktree 里没有 `framework/results/s08/` 和 `.orch/sqlancer/`，S08、S11、S15 的几组与 S16 的 `replay` 组都过不了；S10 的 `frozen`、S19 的 `scope` 会因为本会话改了 harness 而失败，这是已知的。合并后编排者在主检出区跑全部门槛。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s16-replay

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
