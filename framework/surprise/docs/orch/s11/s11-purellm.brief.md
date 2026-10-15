角色：执行者

# 工作包 s11-purellm：对照组"纯 LLM 生成"——LLM 直接写 SQL，交给同一套 oracle 与 CVE

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-purellm`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（门槛 `framework/surprise/gates/s11.py` 与 `s11_cases.py` 已经写好）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节、`PLAN.md` 第 5 节 Phase 6（对照组）
- 依赖：S9 的 LLM 网关（`surprise/roles/gateway.py`、`cache.py`、`schema.py`、`transport.py`）；harness 的 `evaluate_final`；φ 提取（`surprise.hunter.PhiExtractor` 或 `surprise.features.extract`）。与你并行的有 `s11-fixes`（会给 `roles/constants.py` 加一个常数、改 `roles/transport.py`）与 `s11-runmetrics`（`metrics/` 新模块）；你不改这些文件。

## 目标

评估设计里的对照组之一："纯 LLM 生成：LLM 直接写 SQL 交给同一套 oracle，没有理论、没有惊讶，回答'LLM 本身能走多远'。" 新建 `framework/surprise/baselines/pure_llm.py`（一个模块，含命令行入口），门槛 `gates/s11.py` 的 `pure_llm_script` 组与 `constants` 组（pure_llm 部分）验收它；`pure_llm` 组重放编排者之后用真实调用录下的缓存（在你的 worktree 里会因为缺录制而失败，这是预期的）。**先把这三组的代码完整读一遍，它们就是验收标准。**

### 常数（模块级，门槛钉住）

```python
PURE_LLM_TIER = "fast"
PURE_LLM_TEMPERATURE = 0.8
PURE_LLM_MAX_TOKENS = 16000
PURE_LLM_CASES_PER_CALL = 8
PURE_LLM_TOPICS = ( ... )   # 至少 8 个不同的 SQL 主题短语（英文），例如
                            # "set operations with ALL", "window functions with PARTITION BY and frames",
                            # "outer joins and NULL handling", "correlated subqueries", "GROUP BY with
                            # aggregates and HAVING", "CTEs and recursive CTEs", "type casts and numeric
                            # edge values", "string functions and collations", "ORDER BY / LIMIT / OFFSET",
                            # "DATE and TIMESTAMP arithmetic", ...
```

（`max_tokens` 用 16000：S9/S10 实测 `deepseek-flash` 把推理 token 算进 `max_tokens`，8000 会截断。）

### 运行

`run(out, *, seed, engine="duckdb", oracles=ORACLE_IDS, max_experiments=None, max_minutes=None, cache=None, max_calls=None, offline=False, run_id=None, transport=None) -> dict`

- `max_experiments` 与 `max_minutes` 至少给一个（否则抛 `ValueError`）；`out` 必须不存在或是空目录（与 `experiments/loop.py` 一样）。
- `run_id` 默认 `f"pure-s{seed}"`。
- 网关：`Gateway(cache_dir=cache or out/"llm"/"cache", ledger_path=out/"llm"/"calls.jsonl", max_calls=max_calls, transport=...)`。`transport` 参数给了就用它（测试与门槛用脚本替身）；没给且 `offline` 为假时用 `DeepSeekTransport()`；`offline` 为真时不建传输（网关只从缓存回答，缺失即 miss）。仿照 `surprise/roles/runtime.py` 里现有角色建网关的写法。
- 账本：`out/ledger.sqlite`，`Ledger.start_run(run_id, manifest)`，manifest 用 `build_manifest(run_id)`（同 loop 的做法）再加 `"baseline": "pure_llm"` 与 `"pure_llm": {常数与参数}`。
- 循环：第 b 批（b 从 0 起）：
  1. 主题 = `PURE_LLM_TOPICS` 中由 `random.Random(seed)` 依次抽出的一项（每批抽一次，确定）；
  2. 提示（英文）写明：目标引擎（名字与版本，例如 `importlib.metadata.version("duckdb")`；注意仓库根有同名目录会遮蔽包，不要 `import duckdb` 取版本）、可用的 oracle 列表及每个 oracle 一句话的含义与对用例的要求（例如 TLP 与 NoREC 需要一个 WHERE 谓词放在 `predicate` 字段、`query` 本身不带 WHERE；Cross-DBMS 要求语句在 DuckDB、DataFusion、SQLite、PostgreSQL 上都能写成同样的 SQL；等等——读 `surprise/harness/oracles/` 了解各 oracle 的前提，写对即可）、本批主题、批号、`seed`、要写 `PURE_LLM_CASES_PER_CALL` 个用例、目标是找出数据库的逻辑错误，以及回复的 JSON 格式（下面）。**提示里不能有随运行时间而变的东西**（时间戳、耗时、记录号），否则缓存重放失效；同一 seed 的提示序列必须完全相同（门槛检查）；
  3. `gateway.call("pure_llm", prompt, tier=PURE_LLM_TIER, seed=seed, temperature=PURE_LLM_TEMPERATURE, max_tokens=PURE_LLM_MAX_TOKENS)`；
  4. 回复 JSON：`{"prediction": "<一句话：预计会发现什么>", "cases": [{"setup": ["CREATE ...", "INSERT ..."], "query": "SELECT ...", "predicate": null 或 "...", "oracle": "<oracle 名>", "expect": "pass" 或 "fail"}, ...]}`。网关已经要求回复是带 `prediction` 的 JSON 对象，缺了就拒收（status `rejected`）。
  5. 逐个校验 `cases`：`setup` 是字符串列表、`query` 是非空字符串、`predicate` 是 None 或字符串、`oracle` 在本次运行的 `oracles` 里、`expect` 是 pass / fail（不合格的整条跳过并计数，不执行）。
  6. 合格的用例按回复顺序执行：`SqlCase(engine=engine, setup=..., query=..., predicate=...)` → `evaluate_final(case, oracle, ledger=..., run_id=..., purpose="pure_llm", spec={"batch": b, "index": i, "expect": expect, "topic": topic}, phi=φ.to_dict(), theory_version=None, p_t=None, diagnose=True)`。`diagnose=True`：每个失败都走 CVE 第 3 档（最小化 + 画像），这样它的身份键与其他臂同一口径。φ 用与 loop 相同的提取器（`PhiExtractor`，用完关闭）。**标签只来自 harness**：LLM 的 `expect` 只是它的预测，记进 spec，不影响标签。
  7. 每执行一条，`progress.jsonl` 写一行：`{"seq", "record_id", "batch", "index", "topic", "oracle", "y", "kind": 失败类别或无效原因或 None, "expect", "elapsed_s"}`。
  8. 每次调用在 `llm/pure_llm.jsonl` 写一行：`{"batch", "topic", "status": 网关回复的状态（ok / rejected / error / blocked / miss）, "cases": 合格并将执行的条数, "skipped": 不合格的条数, "reasons": {原因: 条数}}`。
- 停止：执行条数达到 `max_experiments`（可以在一批中途停）→ `"budget_experiments"`；墙钟超过 `max_minutes` → `"budget_minutes"`；网关回复 `blocked`（到上限）或 `miss`（离线缓存缺失）→ `"llm_exhausted"`。回复 `rejected` 或 `error` 时记一行、继续下一批（不会死循环：每批都消耗一次调用，上限兜底）。运行出异常 → `"error"`，照 loop 的做法写 `report.json` 后抛出（并把 traceback 写进 `error.txt`）。
- 结束写 `config.json`（运行前写：seed、engine、oracles、max_experiments、max_minutes、run_id、`"llm": {"cache", "max_calls", "network": not offline}`）与 `report.json`：`{"run_id", "seed", "engine", "oracles", "status", "experiments", "calls", "started_at", "finished_at", "wall_s", "labels": {y: 条数}, "llm": gateway.totals()}`。`run()` 返回这个 dict。

### 命令行

`python -m surprise.baselines.pure_llm --out DIR --seed N [--engine duckdb] [--oracle NAME]... [--max-experiments N] [--max-minutes M] [--llm-cache DIR] [--llm-max-calls N] [--llm-offline] [--run-id ID]`；用法错误退出码 2；正常 0。

### 门槛 `pure_llm_script` 组的要点（照它写测试）

- 三次脚本回复：第一次 2 条合格 + 2 条不合格（oracle 不在列表、setup 不是列表）；第二次缺 `prediction`（被拒收）；第三次 2 条合格；`max_calls=3`、`max_experiments=10` → 执行 4 条、3 次调用、第 4 次被上限挡下，`status == "llm_exhausted"`；`pure_llm.jsonl` 三行的 status 依次 ok / rejected / ok，第一行 `cases == 2`、`skipped == 2`。
- 同一 seed 再跑一次，提示序列完全相同；第一、二批的提示不同；提示里含引擎名与 oracle 名。
- `max_experiments=1` 时在第一批中途停，`status == "budget_experiments"`。
- 每条记录 `purpose == "pure_llm"`、`p_t is None`、`theory_version is None`、`phi` 不是 None、spec 含 `batch`、`index`、`expect`；manifest 的 `baseline == "pure_llm"`。

## 允许改动的路径

```allow-paths
framework/surprise/baselines/pure_llm.py
framework/tests/test_surprise_s11_pure_llm.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `roles/`、`experiments/`、`metrics/` 等任何已有模块；旧代码不碰。
- **不做任何真实 LLM 调用**：测试一律用脚本替身传输；不要设置或读取 `DEEPSEEK_API_KEY`（你的进程里也没有它）。真实回复由编排者在合并后录制。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                        # 通过数不少于 774，0 failed
python -m surprise.gates.s11 --only pure_llm_script      # PASS
python -m surprise.gates.s11 --only constants            # 预期 FAIL：缺 metrics.constants 与 REQUEST_DEADLINE_S（别的包交付）；报告里贴出失败行
python -m surprise.gates.s11 --only pure_llm             # 预期 FAIL：缺录制（gates/s11_llm/pure_llm）
```

新测试放在 `framework/tests/test_surprise_s11_pure_llm.py`，覆盖上面"门槛要点"的每一条，外加：离线缓存缺失时 `llm_exhausted`、`max_minutes` 预算、用法错误。测试总时长控制在 3 分钟以内（每条用例要过 CVE，失败还要做第 3 档；测试里的用例尽量写成 pass 的普通查询，失败的只放一两条）。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-purellm

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
