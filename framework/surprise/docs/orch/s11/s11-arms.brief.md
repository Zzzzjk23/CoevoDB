角色：执行者

# 工作包 s11-arms：主循环的消融开关——冻结理论、冻结 Diagnoser、随机 Hunter、跨代配对

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s11-arms`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s11`（已合并 `s11-fixes`：`experiments/loop.py` 在运行出错时写 `error.txt`；`s11-purellm`。`s11-runmetrics`（`surprise/metrics/` 的新模块）与你并行开发，与本包无关）
- 所属会话：S11（Phase 6 评估管线），范围见 `framework/surprise/docs/SESSIONS.md` 的 S11 一节
- 依赖：`s11-fixes`（已合并）。与你并行的还有 `s11-grid`（`experiments/grid.py`、`baselines/`）；文件不重叠。

## 目标

RQ5（协同进化：两侧是否真的在互相推动）的两类实验要靠主循环的开关产生账本（框架文档"评估设计"一节）：

- **分层冻结消融**："分别冻结理论内容、词汇、诊断过程，以及把 Hunter 换成随机出题"，看哪一侧的进化在推动发现。
- **跨代交叉配对**："新 Hunter 配旧理论、旧 Hunter 配新理论，看产出如何变化。"在本框架里 Hunter 自己不学东西，它出题完全由它参照的理论决定，所以"第 j 代的 Hunter"= 用第 j 代理论选题的 Hunter。配对实验因此要能让 Hunter 用一份理论选题、而本次运行的标签、惊讶与学习用另一份理论。

"冻结词汇"不需要代码：词表本来就只在用 `--vocabulary` 起的下一次运行才变，一次运行内不变；网格配置里不开词汇发明者、不给 `--vocabulary` 就是冻结词汇。

门槛 `gates/s11.py` 的 `arms` 组验收本包。**先把它完整读一遍，它就是验收标准。**

### `experiments/loop.py`：`run()` 新增四个关键字参数（命令行同名开关）

| 参数 | 命令行 | 取值 | 含义 |
|---|---|---|---|
| `freeze=None` | `--freeze {theory,diagnoser}` | None / `"theory"` / `"diagnoser"` | 见下 |
| `hunter="value"` | `--hunter {value,random}` | `"value"` / `"random"` | 选题方式 |
| `theory_from=None` | `--theory-from RUN_DIR@GEN` | 字符串 | 本次运行的理论从别的运行的某一代开始 |
| `select_from=None` | `--select-from RUN_DIR@GEN` | 字符串 | Hunter 用别的运行某一代的理论选题 |

- `freeze="theory"`：理论内容冻结。`_execute` 不调用 `wb.observe`，也不调用 Diagnoser（`after` 与 `periodic` 都不调）；理论从头到尾是它的起点（空理论，或 `theory_from` 给的那一代），`wb.theory.version` 不变。预测、分层 CVE（有预测到的假设就做归属测试，否则 `diagnose=True`）、账本照旧。progress 行里依赖 observe 结果的字段取空值：`triage`、`opened`、`owner` 为 None，`rolled_back`、`edits`、`bets` 为空列表；`surprise` 改用 `surprise.theory.predict.surprise_bits(p_t, y)` 计算（invalid 为 None）。账本记录的 `theory_version` 照旧是执行前的理论版本。
- `freeze="diagnoser"`：诊断过程冻结。`wb.observe` 照旧（版本空间照规则泛化、特化、开新家族），但不提出任何理论编辑：`Diagnoser.after` 不调用，`periodic` 里的 MDL 压缩不做；**按代关闭（checkpoint，每 `CHECKPOINT_EVERY` 条）照做**（CIAO 要用代）。读 `diagnoser/diagnoser.py` 找出 `periodic` 里压缩与 checkpoint 两部分，在 loop 里只调后者需要的部分（可以给 `Diagnoser` 加一个只做 checkpoint 的方法；`diagnoser/` 在允许路径里，但默认行为一个字节都不能变）。
- 冻结与 LLM 角色：开了 `freeze` 时，只允许 `implementer` 与 `prior` 两个角色（它们不改理论）；开了别的角色抛 `UsageError`。
- `hunter="random"`：`Hunter.choose` 在本轮的候选范围（`scope`，保底名额的规则不变）里用 `self.rng` 均匀随机选一个，不按 value 取最大。候选的生成、过滤、打分（progress 里的 value / D / U）照旧。同一个 seed 结果确定。实现在 `hunter/hunter.py`：`Hunter(..., select="value")` 新参数，`"value"` 的行为一个字节都不能变。
- `theory_from="RUN_DIR@GEN"`：`RUN_DIR` 是一个运行目录（含 `theory/`）；`GEN` 是整数（已关闭的代，用 `TheoryStore.load_generation`）或 `head`（该存储当前保存的活理论，用 `Workbench.open(...).theory`）。本次运行的理论存储新建后，把那份理论作为起点存进去（需要的话给 `theory/workbench.py` 或 `theory/store.py` 加一个"从给定理论创建"的入口，例如 `Workbench.create(root, registry=None, theory=None)`；不能改变现有调用的行为）。那份理论的词表摘要必须等于本次运行的词表摘要，否则 `UsageError`。只带理论本身（假设、R、Kᵛ、记住的通过等 `Theory` 里的东西），不带源运行的观察日志与编辑历史。
- `select_from="RUN_DIR@GEN"`：同样的写法读出一份理论，放进本次运行目录下的 `select_theory/` 新建的一个存储里，作为只读的"选题工作台"。`Hunter.choose(选题工作台)`：候选（细化 / 泛化来自选题理论的假设）、打分都按选题理论。选中之后，主循环**用本次运行自己的理论**重新预测：`p_t`、预测区、要不要做归属测试 / 画像、`observe` 全按本次运行的理论；progress 行的 `p_fail_valid`、`p_invalid`、`zone`、`predicted` 也取本次运行理论的预测，另加一个键 `"select_p"`（选题理论给的 `p_fail_valid`，float；像 `llm` 键那样加在 `_PROGRESS_KEYS` 检查之后，检查本身不改）。Hunter 的 `record(...)`（探针计数）用本次运行理论的预测。选题工作台全程不变。
- 两个 `@` 参数格式不对、目录或代不存在 → `UsageError`；`freeze`、`hunter` 取值不对 → `UsageError`。命令行遇到 `UsageError` 退出码 2（照现有写法）。

### 记录

- 只要有一个参数不是默认值，`config.json` 与 `report.json` 就多一个键 `"arm"`：`{"freeze": ..., "hunter": ..., "theory_from": None 或 {"run": 源运行目录的绝对路径（str）, "generation": 整数或 "head", "version": 那份理论的 version}, "select_from": 同样格式}`；run manifest 的 `hunter` 一节也加同样的 `"arm"`。
- **四个参数都是默认值时，`config.json`、`report.json`、`progress.jsonl`、manifest 一个字节都不能变**（S8 的 `determinism` / `lanes`、S9 的 `replay`、S10 的 `m3` 都逐行比对它们）。`select_p` 只在 `select_from` 时出现。

## 允许改动的路径

```allow-paths
framework/surprise/experiments/loop.py
framework/surprise/hunter/hunter.py
framework/surprise/diagnoser/diagnoser.py
framework/surprise/theory/workbench.py
framework/surprise/theory/store.py
framework/tests/test_surprise_s11_arms.py
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改理论的规则与常数（`theory/constants.py`、版本空间、接受规则、预测、分诊）、Hunter 与 Diagnoser 的常数；默认路径的行为一个字节都不能变。旧代码不碰。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。
- 本包不需要 LLM 调用、不需要密钥。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                     # 通过数不少于基线，0 failed
python -m surprise.gates.s11 --only arms                              # PASS
python -m surprise.gates.s08 --only no_llm constants scoring operators candidates lanes determinism   # 全部 PASS（默认行为没变）
python -m surprise.gates.s09 --only wiring replay                     # 全部 PASS
python -m surprise.gates.s10 --only frame switches m3                 # 全部 PASS
python -m surprise.gates.s06 ; python -m surprise.gates.s07           # 全部 PASS（理论层没变）
```

S8 门槛的 `longrun` 组会因为本包改了 `hunter/`、`diagnoser/`、`experiments/` 的代码摘要而失败，这是预期的（编排者在全部合并后重跑长跑重钉），不用跑。

新测试放在 `framework/tests/test_surprise_s11_arms.py`，覆盖每个开关、每种 `UsageError`、默认行为不变（与不加参数的运行逐行相同）、`select_from` 时 p_t 来自本次运行的理论。测试总时长控制在 4 分钟以内（用两三个 oracle、十来条实验的短跑）。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s11-arms

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
