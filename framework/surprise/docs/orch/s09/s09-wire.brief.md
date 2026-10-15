角色：执行者

# 工作包 s09-wire：把 LLM 角色接进 Hunter 与主循环（开关接入；全关时与 S8 逐行相同）

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s09-wire`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s09`（`s09-gateway` 合并之后）
- 所属会话：S9（Phase 5a），范围见 `framework/surprise/docs/SESSIONS.md` 的 S9 一节
- 依赖：S8 的 `surprise.hunter`（`Hunter`、`Candidate`）与 `surprise.experiments.loop`（全部读一遍）；`surprise.roles` 的网关一层（已合并）。与你并行的包 `s09-roles` 在 `surprise/roles/` 里写 `runtime.py`（`build_roles`、`RoleSet`、`ImplementerSource`），**你的 worktree 里没有它**；双方只靠下面写死的接口对接。
- 先读：`framework/surprise/gates/s09.py` 的 `check_wiring`、`check_replay`、`check_isolation` 与 `s09_cases.py` 的 `OFF_PREFIX`、`LOOP_RUN`；`framework/surprise/gates/s08.py`（`no_llm`、`lanes`、`determinism`、`check_rows`、`code_digests`）。门槛就是接口规格；与本说明不一致时以门槛为准，并写进报告。

## 目标

用户在 S8 验收时定下（HANDOFF"下一会话的起点：S9"）："LLM 角色放进新目录；`hunter/`、`diagnoser/`、`experiments/` 只做接线所需的最小改动，角色由开关接入，关掉时行为与 S8 相同。"PLAN 第 1 节原则 4："LLM 角色一次接一个，每个都能开关，对上消融表。"

"关掉时行为与 S8 相同"的验收标准（门槛 `wiring` 组）：不开任何角色时，同种子 40 条的短跑，每一行进度去掉 `elapsed_s` 之后与 S8 长跑的前 40 行完全相同（哈希钉在 `OFF_PREFIX`），行的键与 S8 相同，`config.json`、`report.json`、run manifest 里都没有 `llm`，进程里没有加载任何 `surprise.roles` 模块。

### 1. Hunter（`surprise/hunter/hunter.py`）

- `Hunter.__init__` 加一个关键字参数 `sources=()`（放在最后），存成元组。每个来源是有 `candidates(wb, *, index: int, round: int) -> list[Candidate]` 方法的对象。
- `candidates(self, wb, *, round: int = 1)`：在现有三段（细化/泛化、迁移、探索）之后，按 `sources` 的次序追加 `source.candidates(wb, index=self._index, round=round)` 的结果。`choose` 每一轮调用 `self.candidates(wb, round=rounds)`。
- 来源给的候选车道可能是 `"implement"`、`"bet"` 等新名字：`choose` 里数车道改成 `pool[lane] = pool.get(lane, 0) + 1`。`pool` 的初始键（四条车道与三个 `rejected_*`）不变。来源的候选与其余候选走完全相同的过滤（已做过、坏 setup、新颖性）与打分；探索保底位照旧只看 `"explore"` 车道。
- `sources` 为空时，`Hunter` 的一切行为（随机数的消耗次序、候选次序、`pool`、`manifest()`）必须与现在逐位相同。`LANES` 常数不改，`constants.py` 不改。
- `surprise/hunter/` 不得导入 `surprise.roles`。

### 2. 主循环（`surprise/experiments/loop.py`）

- `run(..., echo=False, llm=None)`：`llm` 为 None 时一切照旧。否则是 dict，键只能是 `roles`（`"implementer"`、`"conjecturer"` 的非空、无重复子集，列表或元组）、`cache`（非空字符串）、`max_calls`（非负整数或 None，默认 None）、`network`（布尔，默认 True）、`transport`（可选，任何对象，给库调用方与门槛用）；其余键、类型不对 → `UsageError`。
- 命令行加：`--llm ROLE`（可重复，取值 `implementer` / `conjecturer`）、`--llm-cache DIR`、`--llm-max-calls N`、`--llm-offline`。给了 `--llm` 就必须给 `--llm-cache`；没给 `--llm` 却给了另外三个之一 → 参数错误（退出码 2）。由命令行组出 `llm = {"roles": [...], "cache": DIR, "max_calls": N 或 None, "network": not offline}`。
- 构造角色（只在 `llm` 不为 None 时）：模块级函数
  ```python
  def _build_roles(config, *, run_dir, extract, registry, engines, seed):
      from surprise.roles.runtime import build_roles   # imported here, never at module level
      return build_roles(config, run_dir=run_dir, extract=extract, registry=registry, engines=engines, seed=seed)
  ```
  在 `_prepare` 里：先开 φ 提取器，再 `state.roles = _build_roles(llm, run_dir=directory, extract=state.extractor.extract, registry=default_registry(), engines=state.engines, seed=state.seed)`，再建 `Hunter(..., sources=state.roles.sources)`。你的测试用 `monkeypatch.setattr(loop, "_build_roles", ...)` 换成假的 `RoleSet`。
- `RoleSet` 的接口（`s09-roles` 实现，你只调用）：`sources`（元组）、`observe(phi, label, record_id)`、`after(wb, record, outcome)`、`step() -> dict`、`manifest() -> dict`、`report() -> dict`、`close()`。
- 一次实验（`_execute`）在开着角色时多做三件事，次序固定：`evaluate_final` → `wb.observe` → `hunter.record` → Diagnoser 的 `after` 与 `periodic`（这些照旧）→ `state.roles.observe(step.phi, record.label, record.record_id)` → `state.roles.after(state.wb, record, outcome)` → 进度行。进度行在 `_PROGRESS_KEYS` 的全部键之后多一个键 `"llm": state.roles.step()`。
- 开着角色时：`config.json` 多一个键 `"llm"`，值为 `{"roles": list, "cache": str, "max_calls": int 或 None, "network": bool}`（不含 `transport`）；run manifest 多一节 `manifest["llm"] = state.roles.manifest()`（与 `manifest["hunter"]` 并列，在 `start_run` 之前放进去）；`report.json` 多一个键 `"llm": state.roles.report()`（出错的 run 也写，能写多少写多少）；`_close` 里调 `state.roles.close()`（与其余资源一样，第一个异常最后再抛）。
- 关着角色时：以上全部不出现；`surprise.roles` 不被导入；`_PROGRESS_KEYS`、`_config`、`_write_report` 的输出与现在逐位相同。`surprise/experiments/` 不得在模块顶层导入 `surprise.roles`。
- `code_digests()` 不改（它会把你改过的文件算进去，这是预期的：编排者之后会重跑 S8 长跑并重钉哈希）。

### 3. 测试

`framework/tests/test_surprise_s09_wire.py`：

- `Hunter`：`sources=()` 与不传时，同种子 `choose` 若干次的结果、`pool` 完全相同；一个假来源的候选进入打分、被选中时 `Choice` 带着它、车道计数里有它的新车道；`round` 与 `index` 正确传给来源。
- 主循环：用假的 `RoleSet`（`monkeypatch` 换掉 `_build_roles`）跑一个几条实验的短 run（DuckDB），核对：调用次序（observe 在 after 之前，都在 Diagnoser 之后）、进度行的 `"llm"`、`config.json` / manifest / report 的 `llm`、出错时也 `close()`；关着角色时 `config.json`、行的键、report 的键与 S8 相同、`sys.modules` 里没有 `surprise.roles.runtime`。
- 命令行：`--llm` 的四个参数的组合与错误（退出码 2）。
- 不做任何真实调用，不需要密钥。

## 允许改动的路径

```allow-paths
framework/surprise/hunter/hunter.py
framework/surprise/experiments/loop.py
framework/tests/test_surprise_s09_wire.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）、`framework/surprise/roles/`、`framework/surprise/theory/`、`framework/surprise/features/`、`framework/surprise/diagnoser/`、`framework/surprise/metrics/`、`framework/surprise/baselines/`，以及 `hunter/` 里除 `hunter.py` 以外的文件。觉得其中哪个非改不可，写进报告，停下。
- 不改任何常数；不改 S8 的规则（车道、打分、保底位、新颖性、Diagnoser）。
- 旧代码（`framework/surprise/` 以外）本包不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest；旧测试一个都不改。某个测试确实该改，就写进报告的"未决问题"，停下。
- 不做任何 LLM 调用；密钥只走环境变量 `DEEPSEEK_API_KEY`，不打印，不写进代码、配置、日志、提交或报告。
- 不跑超过 15 分钟的 run，不往 `framework/results/` 写东西。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`；测试产生的临时文件只放 pytest 的 `tmp_path`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器，不要换别的。你的 shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，需要靠输出判断时用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests       # 通过数不少于网关包合并后的数目（先在起点跑一次记下），skip 仍是 3
python -m surprise.gates.s08 --only no_llm scoring operators candidates lanes determinism    # 6/6，约 8 分钟
python -m surprise.gates.s09 --only wiring     # 预期失败，且失败信息必须是 "No module named 'surprise.roles.runtime'"（角色包还没合并）；
                                               # 在那之前的部分（全关的 40 条与 S8 逐行相同）必须已经通过，更早的失败要修
```

`s08` 的 `longrun` 组会因为代码摘要变了而失败，这是预期的，不用跑；`python -m surprise.gates.all` 也不用跑。在报告里注明。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），按下面的格式。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s09-wire

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
