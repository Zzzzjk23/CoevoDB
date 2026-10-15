角色：执行者

# 工作包 s08-eval：S8 的指标与对照（惊讶曲线与锯齿、家族重复率、已知 bug 召回、旧系统 no_llm 按墙钟预算运行）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s08-eval`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s08`（`s07-done-r2` 之后加了 S8 的门槛 `framework/surprise/gates/s08.py` 与 `s08_cases.py`）
- 所属会话：S8（Phase 4：Hunter 与无 LLM 闭环，里程碑 M2），范围见 `framework/surprise/docs/SESSIONS.md` 的 S8 一节
- 依赖：冻结的 `surprise.harness`（`Ledger`、`ExperimentRecord`、`certify`、`surprise.harness.cve.shape.behavior_shape`）、S6/S7 的 `surprise.theory`（`surprise_bits`、`Workbench.open`、`Workbench.families()`、`Workbench.partition()`）。先读 `framework/surprise/harness/ledger.py`、`harness/contracts.py`、`theory/workbench.py`（`families`、`partition`、`family_of`）、`theory/hypothesis.py`（`new_family` 怎样从第 3 档画像取身份）
- 同时有另一个执行者在做 `s08-hunter`（`surprise/hunter/`），主循环在之后的 `s08-loop` 包里做；本包只读运行目录，不依赖它们的代码

## 目标

S8 门槛 `framework/surprise/gates/s08.py` 的 `sawtooth`、`duplicates`、`recall` 三组读编排者跑出来的产物，用的就是本包的函数；本包交付这些函数、两个命令行，以及跑旧系统基线的驱动。门槛的那三组在你的 worktree 里会因为产物还不存在（`s08_runs.json` 没写）而失败，这是预期的；你按第 6 节用合成数据与小规模真实运行验证。先把 `gates/s08.py` 里 `check_sawtooth`、`check_duplicates`、`check_recall` 读一遍，下面的名字、参数、返回值照写。

一个**运行目录**（主循环在下一个包里写出）里有：`ledger.sqlite`（冻结 harness 的 `Ledger`，一个 run）、`theory/`（S7 的 `TheoryStore`，`Workbench.open` 打开）、`progress.jsonl`、`report.json`。本包只依赖前两个。

框架文档的定义（本包照它实现）：

- "RQ2 的核心图是惊讶曲线：每 100 次执行的平均惊讶。预期它呈锯齿形——发现新家族时冲高，理论吸收后回落。"
- "重复率：报告中被判定为已有 bug 的比例。"
- 已知 bug 召回使用 DuckDB 1.1.3 等旧版本基准。

### 1. 惊讶曲线与锯齿（`surprise/metrics/curve.py`，纯函数）

```python
def record_surprise(record: ExperimentRecord) -> float | None
    # label.y == "invalid" 或 record.p_t is None 时为 None；否则 surprise_bits(record.p_t, record.label.y)
def surprise_curve(records: Sequence[ExperimentRecord], window: int = 100) -> list[float | None]
    # 按给定次序切成连续的整窗（第 k 窗是 records[k*window:(k+1)*window]），末尾不满一窗的丢掉；
    # 每窗取其中 record_surprise 不为 None 的平均值，一个都没有时为 None。window < 1 为 ValueError
def teeth(curve: Sequence[float | None], amplitude: float = 0.25, width: int = 5) -> list[int]
```

`teeth` 返回"齿"的下标（升序）。下标 k 是齿，当且仅当：`curve[k]` 不是 None；`L` = 下标在 `[k - width, k - 1]` 内（越界的不算）且不为 None 的值，`R` = 下标在 `[k + 1, k + width]` 内且不为 None 的值，两者都非空；`curve[k] > max(L)` 且 `curve[k] >= max(R)`（平台取最左边那个）；`curve[k] - min(L) >= amplitude - 1e-12` 且 `curve[k] - min(R) >= amplitude - 1e-12`。意思是：一个局部最高点，在 width 个窗之内先升了至少 amplitude 比特、后降了至少 amplitude 比特。

### 2. 身份键与重复率（`surprise/metrics/dups.py`）

两套系统的"报告"用同一个裁判比：**冻结的 harness 第 3 档画像给出的身份**。有 fix set 的按（引擎，fix set）认，没有的按（引擎，失败类别，错误类别，行为形状）认。

```python
def identity_key(engine: str, fix_set: Iterable[str], fail_kind: str | None, error_class: str | None,
                 behavior_shape: str | None) -> str
    # fix_set 非空："fix|<engine>|" + ",".join(sorted(fix_set))
    # 否则："shape|<engine>|<fail_kind or '-'>|<error_class or '-'>|<behavior_shape or '-'>"
def new_families(store_dir: str | Path) -> list[dict]
def old_reports(bugs_jsonl: str | Path) -> list[dict]
def duplicate_rate(keys: Sequence[str]) -> float | None
    # n = len(keys)；n == 0 为 None；否则 (n - len(set(keys))) / n
```

`new_families(store_dir)`：`wb = Workbench.open(store_dir)`；`families = wb.families()`（家族名 → 假设编号，S7 的定义：有 fix set 的假设按（引擎，fix set）跨 oracle 成一个家族，没有的一个假设一个家族）。每个家族一项 dict：`family`（家族名）、`hypotheses`（编号表）、`engine`、`key`（用家族里**第一个**假设的 `engine`、`interventions`、`fail_kind`、`error_class`、`behavior_shape` 算 `identity_key`）、`first_record`（`wb.partition()` 里最早归到这个家族的失败记录编号；没有则 None）。次序：先按 `first_record` 在 `partition()` 里出现的先后，`first_record` 为 None 的排在最后、按 `families()` 的次序。

`old_reports(bugs_jsonl)`：旧系统 `framework/main.py` 一次 run 的 `bugs.jsonl`，每行一个旧系统报告的 bug（σ 家族）。每行一项 dict：`root_key`、`engine`（`signature.engine`，没有 signature 时为 `"duckdb"`）、`fix_kind`、`fix_set`（列表）、`origin`、`iteration`、`kind`（`candidate.kind`）、`key`：`signature` 存在、`fix_kind` 在 `("single", "minimal_set")` 里、`fix_set` 非空时为 `identity_key(engine, fix_set, None, None, None)`，否则为 `"sigma|" + root_key`（旧系统没有给出可比的身份，只能当作独一份，这对旧系统是有利的）。基线进程是到点强杀的，最后一行可能只写了一半：**只有最后一行**解析失败时跳过它（返回值里不出现），中间的行解析失败抛 `ValueError`。空行跳过。

命令行 `python -m surprise.metrics.dups --new RUN_DIR --old OLD_DIR [--out FILE]`：`RUN_DIR/theory` 交给 `new_families`；`OLD_DIR/old_run.json`（第 4 节）的 `run_dir` 是相对 `OLD_DIR` 的路径，读其中的 `bugs.jsonl`；输出 JSON `{"new": {"families": [...], "rate": ...}, "old": {"reports": [...], "rate": ...}}`（`--out` 写文件，否则打印到 stdout），`ensure_ascii=True`。

### 3. 已知 bug 召回（`surprise/metrics/recall.py`）

```python
def known_bugs(items: Sequence[Mapping]) -> dict
def score(known: Mapping, store_dir: str | Path) -> dict
```

`known_bugs(items)`：每个 item 有 `name`、`case`（`SqlCase.to_dict()`）、`oracle`、`rule`（可为 None）。**在当前解释器里**逐个 `certify(SqlCase.from_dict(case), oracle, diagnose=True, rewrite_rule=rule)`（`surprise.harness.cve.certify`，默认参数）。结果 `{"engines": {"duckdb": importlib.metadata.version("duckdb"), "datafusion": importlib.metadata.version("datafusion")}, "items": [...]}`，每项 `{"name", "oracle", "y", "fail_kind", "invalid_reason", "fix_set", "key"}`：`fix_set` 是第 3 档画像（`label.cve["profile"]`，`status == "ran"`）的 `fix_set` 列表，没有画像为 None；`key` 只在 `y == "fail"` 且有画像时给出：`identity_key(case.engine, fix_set, label.fail_kind, label.identity.error_class, behavior_shape(label.identity.behavior))`（`behavior_shape` 来自 `surprise.harness.cve.shape`，与理论层 `new_family` 取身份的方式相同），否则为 None。版本号用 `importlib.metadata`，不要 `import duckdb` 取 `__version__`（仓库根有同名的目录会冒充模块）。

`score(known, store_dir)`：`fams = new_families(store_dir)`；`present` = `known["items"]` 里 `y == "fail"` 且 `key` 不为 None 的那些（保持次序）。某个 item 的 key 等于某个家族的 key 即为召回。返回 JSON 安全的 dict（只用 list、str、int、float、None）：`{"known": [present 的 name], "recalled": [被召回的 name], "missed": [没召回的 name], "recall": len(recalled) / len(present)（present 为空时 None）, "families": len(fams), "first": {name: 匹配到的第一个家族的 first_record}}`。门槛会把它与存下来的 `recall.json` 做相等比较，所以同一输入两次结果必须逐字相同。

命令行 `python -m surprise.metrics.recall known --cases FILE --out FILE`（`FILE` 是 items 的 JSON 列表）与 `python -m surprise.metrics.recall score --known FILE --run RUN_DIR --out FILE`（`RUN_DIR/theory`）。输出 `ensure_ascii=True`、`indent=1`。

### 4. 旧系统 no_llm 基线（`surprise/baselines/old_no_llm.py`）

"同执行预算"按同样的墙钟时间比：旧系统在进程里直接执行，新框架每次判定都起隔离进程，两边每次执行的花费不同，按墙钟比才公平。

```python
def run(out: str | Path, *, minutes: float, seed: int, python: str | None = None) -> dict
```

- `out` 不存在就建；存在且非空 `ValueError`。
- 命令：`[python or sys.executable, str(FRAMEWORK / "main.py"), "--engine", "duckdb", "--mode", "no_llm", "--iterations", "100000000", "--stagnation-limit", "100000000", "--seed", str(seed), "--results-root", str(out / "results"), "--label", f"s08_old_s{seed}"]`，`cwd=FRAMEWORK`（`framework/`），环境变量去掉 `DEEPSEEK_API_KEY`，stdout 与 stderr 一起写进 `out / "console.txt"`。
- 等到它自己结束或满 `minutes * 60` 秒；到点还在跑就终止整棵进程树（Windows 上 `taskkill /T /F /PID <pid>`，其他平台 `kill`），再等它退出。
- `run_dir` = `out / "results"` 下唯一的子目录（旧 `main.py` 建的 `duckdb_no_llm_<时间>_s08_old_s<种子>`），存相对 `out` 的路径（正斜杠）；找不到或不止一个 `RuntimeError`。
- 写 `out / "old_run.json"` 并返回同样的 dict：`{"mode": "no_llm", "engine": "duckdb", "seed", "minutes", "started_at", "finished_at"（ISO 8601，UTC，带时区）, "wall_s"（实际经过的秒数，float）, "ended": "killed" 或 "exited", "returncode", "run_dir", "reports": old_reports(...) 的条数}`。
- 命令行 `python -m surprise.baselines.old_no_llm --out DIR --minutes M --seed S [--python PATH]`，结束时打印 `old_run.json` 的内容（ASCII）。
- 旧代码一个字不改，也不在本进程里导入旧 `main.py`、`agents`、`llm`（只作为子进程跑）。

### 5. 导出

`surprise/metrics/__init__.py` 与 `surprise/baselines/__init__.py` 已存在（空）。不要在 `__init__` 里导入会拉进 harness 或旧代码的东西；门槛按子模块导入（`surprise.metrics.curve`、`surprise.metrics.dups`、`surprise.metrics.recall`、`surprise.baselines.old_no_llm`）。导入这四个子模块不能导入 `openai`、`httpx`、`httpx2`、`agents`、`llm`、`guidelines`、`evolution.co_evolution`。

### 6. 测试与验证

新增 `framework/tests/test_surprise_s08_eval*.py`（可以分几个文件）。至少覆盖：

- `curve`：整窗切分、无效与没有 `p_t` 的记录、`teeth` 的每个条件（只升不降、只降不升、幅度差一点、平台、两侧越界、None 夹在中间）。用手工造的 `ExperimentRecord`。
- `dups`：`identity_key` 的两种形状；`duplicate_rate`；`new_families` 在一个手工喂过几条观察的 `Workbench` 上（可以参考 `gates/s07.py` 里 `opened_bench`、`settled_bench` 的造法，手工的 φ 与标签在 `gates/s06_cases.py`、`gates/s06.py`）；`old_reports` 读 `framework/surprise/docs/baseline/duckdb_no_llm_20261008_204923/bugs.jsonl`（空文件）与一个手写的、最后一行被截断的文件。
- `recall`：`score` 在手工的工作台上；`known_bugs` 用一条真实复现（`gates/s04.py` 的 `load("F1")`，`plan_variant`）在 DuckDB 1.5.5 上跑一次（约 3 秒），检查 `key` 是 `fix|duckdb|deliminator,filter_pushdown`。
- `old_no_llm`：真实跑一次 `minutes=0.5`（旧系统 30 秒，到点被杀），检查 `old_run.json` 的字段、`ended == "killed"`、`run_dir` 存在；再用一个会立刻退出的假命令验证 `ended == "exited"`（可以把命令构造抽成一个可替换的函数供测试用）。

## 背景

- 编排者的探测：旧系统 `main.py --mode no_llm --seed 0` 在 DuckDB 1.5.5 上 10 分钟跑了 39 轮，有两段各卡了约 3.5 分钟（某些种子建大表，旧 runner 的 setup 没有超时），报了 5 条 bug：三条 fix set 是 `deliminator, filter_pushdown`、两条是 `join_order`，σ 键各不相同（σ 把 plan diff 算进了键）。按第 2 节的身份键，重复率是 3/5。
- 旧系统强杀之后没有 `summary.json`，`bugs.jsonl` 是边跑边追加的，`old_reports` 只读它。
- worktree 里没有 `.venvs`，旧版引擎与 PostgreSQL 参照只在主检出区；`known_bugs` 用 plan variant 跑 F1 不需要它们（`certify` 的第 3 档画像里版本梯会找主检出区的旧版环境，找不到时记 `unavailable`，不影响 fix set）。PostgreSQL 已在运行。

## 允许改动的路径

只改下面这些路径（`**` 跨目录，`*` 不跨）。审查按这个清单逐个文件核对，清单以外的任何改动都算越界。

```allow-paths
framework/surprise/metrics/**
framework/surprise/baselines/**
framework/tests/test_surprise_s08_eval*.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/features/`、`framework/surprise/theory/`、`framework/surprise/hunter/`。
- 旧代码（`framework/surprise/` 以外，包括 `main.py`）一个字不改，只作为子进程运行或读它的输出。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。某个测试确实该改，就写进报告的"未决问题"，停下。
- 不调用任何 LLM；旧系统只用 `--mode no_llm` 跑，并且去掉 `DEEPSEEK_API_KEY`；密钥只走环境变量，不打印，不写进代码、配置、日志、提交或报告。
- 不做 Hunter、主循环、Diagnoser（另外两个包的事）。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`（旧系统的运行目录也放在那里，不要写进 `framework/results/`）。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于 550，skip 仍是 3。用 `python -m pytest`：直接敲 `pytest` 会让 `import surprise` 失败
python -c "import sys, surprise.metrics.curve, surprise.metrics.dups, surprise.metrics.recall, surprise.baselines.old_no_llm; bad=[m for m in ('openai','httpx','httpx2','agents','llm','guidelines','evolution.co_evolution') if m in sys.modules]; print('LLM-FREE' if not bad else bad)"
python -m surprise.baselines.old_no_llm --out ..\.orch\tmp\old-check --minutes 1 --seed 0     # 一分钟后打印 old_run.json；目录留着，不要删
```

`python -m surprise.gates.all` 在本包里会因为 S8 门槛的其余几组（属于别的包与编排者）而失败，这是预期的；S1–S7 的门槛必须全部通过：跑一遍 `python -m surprise.gates.all`，把输出末尾的汇总贴进报告，确认 s01–s07 都是 PASS。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s08-eval

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
