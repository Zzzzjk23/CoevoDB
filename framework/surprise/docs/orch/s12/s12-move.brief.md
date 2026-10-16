角色：执行者

# 工作包 s12-move：旧主循环移入 `surprise/baselines/coevodb_v1/`，`coevo/` 与 `repair_bench/` 归档到 `archive/`

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s12-move`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s12`（含门槛 `framework/surprise/gates/s12.py` 与 `s12_cases.py`）
- 所属会话：S12（Phase 7 收尾），范围见 `framework/surprise/docs/SESSIONS.md` 的 S12 一节
- 依赖：无。另一个包 `s12-docs` 同时在改 README 与文档，与本包的文件不重叠。

## 目标

纯移动。用户为 S12 选定"方案 A"：新框架（`surprise/`）直接或间接导入的旧文件是**共用原语**，留在原位、只保留一份；旧主循环只把**独用**的部分移进 `framework/surprise/baselines/coevodb_v1/`，从原位置导入共用原语；`coevo/` 与 `repair_bench/` 归档到 `framework/archive/`。

验收标准是门槛 `framework/surprise/gates/s12.py` 的 `layout`、`moves`、`imports`、`isolation`、`old_arm` 五组（`docs` 组归 `s12-docs`，本包里预期失败）。**先把 `s12.py` 与 `s12_cases.py` 完整读一遍：`MOVES`、`ANCHORS`、`IMPORT_EDITED`、`NEW_INITS` 等表就是逐项的规格。** 下文与门槛不一致时以门槛为准，并在报告里写明。

### 1. 移动（一律用 `git mv`，保留历史）

路径相对 `framework/`；`V1` = `surprise/baselines/coevodb_v1`。

| 原路径 | 新路径 |
|---|---|
| `main.py` | `V1/main.py` |
| `evolution/bandit.py`、`co_evolution.py`、`coverage.py`、`playbook.py` | `V1/evolution/` 下同名 |
| `agents/bug_hunter.py` | `V1/agents/bug_hunter.py` |
| `guidelines/__init__.py`、`llm_guideline.py` | `V1/guidelines/` 下同名 |
| `coverage/__init__.py`、`features.py`、`store.py` | `V1/coverage/` 下同名 |
| `coevo/` 下 8 个文件 | `archive/coevo/` 下同名 |
| `repair_bench/` 下 9 个文件（含 `cases/`、`src_pristine/`） | `archive/repair_bench/` 下同样的相对路径 |

**留在原位、一个字节都不改**（共用原语）：`evolution/dce.py`、`agents/__init__.py`、`agents/base_agent.py`、`agents/bug_fixer.py`、`agents/json_utils.py`、`llm/`、`oracles/`、`targets/`、`diagnosis/`、`seeds/`、`util/`、`scripts/cross_engine.py`。`evolution/__init__.py` 留在原位，只改一行导入（见第 3 节）。

### 2. 新文件

- `V1/__init__.py`、`V1/evolution/__init__.py`、`V1/agents/__init__.py`、`archive/__init__.py`：每个只有一个说明这个包是什么的 docstring（一两句英文），没有别的语句。`V1/guidelines/__init__.py` 与 `V1/coverage/__init__.py` 是移过来的原文件，不是新文件。
- `archive/README.md`：几行英文，说明这里归档了什么（`coevo/`：早期的 verified co-evolution 原型，它的新进程重跑与 flaky 判定已被 S4 的 harness 吸收；`repair_bench/`：补丁 / 定位基准，论文不再需要）、什么时候归档（S12），以及它们仍可导入（`archive.coevo` 被 `evolution/__init__.py` 与 `tests/test_verified_loop.py` 用到）。必须出现 `coevo` 与 `repair_bench` 两个词。
- `framework/main.py`（原路径上的新文件）：只做转发，让 `python main.py ...`（S01 门槛、`surprise/baselines/old_no_llm.py` 的命令、`scripts/gate2.py`、`scripts/coevo_curve.py`、README）照旧可用。内容逐字如下：

```python
"""Forwarder: the old CoevoDB main loop now lives in surprise/baselines/coevodb_v1/main.py (moved in S12)."""
import runpy

if __name__ == "__main__":
    runpy.run_module("surprise.baselines.coevodb_v1.main", run_name="__main__", alter_sys=True)
```

V1 与 archive 两棵树里**只能**有上面这些文件（门槛 `layout` 组按集合精确比对），不要加别的。

### 3. 只允许的改动：导入路径与位置锚点

被移动的文件、以及下表里留在原位的文件，只允许改**导入语句里的模块路径**（导入的名字、顺序、位置、别名都不变）。另外三处"按自身位置算路径"的锚点要改成指向移动前同一个目录（门槛 `ANCHORS` 表逐字核对）：

- `V1/main.py`：`PROJECT_DIR = Path(__file__).resolve().parent` → `PROJECT_DIR = Path(__file__).resolve().parents[3]`（仍指向 `framework/`，`config.yml`、`seeds/`、`results/` 的默认值因此不变）；
- `archive/repair_bench/run_bench.py`、`archive/repair_bench/run_localize.py`：`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` → `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`。`HERE = Path(__file__).resolve().parent` 不改（数据文件跟着一起移了）。

逐文件要改的导入（新前缀 `surprise.baselines.coevodb_v1` 记作 `NEW`）：

- `V1/main.py`：`agents.bug_hunter` → `NEW.agents.bug_hunter`；`coverage.store` → `NEW.coverage.store`；`evolution.bandit` / `evolution.co_evolution` → `NEW.evolution.…`；`guidelines.llm_guideline` → `NEW.guidelines.llm_guideline`；函数里的 `from evolution.playbook import Playbook` → `NEW.evolution.playbook`。`agents.bug_fixer`、`evolution.dce`、`diagnosis.*`、`llm.ledger`、`oracles.*` 不改（共用原语）。
- `V1/agents/bug_hunter.py`：`from .base_agent import BaseAgent` → `from agents.base_agent import BaseAgent`；`from .json_utils import call_llm_json` → `from agents.json_utils import call_llm_json`；函数里的 `from coverage.features import extract_cells` → `NEW.coverage.features`。
- `V1/coverage/__init__.py`：`coverage.features`、`coverage.store` → `NEW.coverage.…`。
- `evolution/__init__.py`：`from coevo.controller import CoEvolutionController` → `from archive.coevo.controller import CoEvolutionController`（不许删这一行：Hunter 经 `evolution.dce` 会执行它，删掉算改逻辑）。
- `archive/coevo/*`：内部都是相对导入，不用改。
- `campaigns/pg_coldstart.py`：`evolution.coverage` → `NEW.evolution.coverage`。
- `scripts/corpus_hunt.py`、`scripts/flaky_mine.py`、`scripts/llm_rule_gen.py`：`evolution.co_evolution` → `NEW.evolution.co_evolution`。
- `scripts/make_playbook_seed.py`、`scripts/make_playbook_seed_v2.py`：`evolution.playbook` → `NEW.evolution.playbook`；`repair_bench.run_bench` → `archive.repair_bench.run_bench`。**不要运行这两个脚本**（会真的调用 LLM）。
- `testing/test_new_components.py`：`evolution.bandit`、`coverage.features`、`coverage.store` → `NEW.…`。
- `tests/test_diagnosis_dce.py`：函数里的 `from evolution.bandit import CategoryBandit` → `NEW.evolution.bandit`。
- `tests/test_verified_loop.py`、`framework/test_simple.py`：`coevo.` → `archive.coevo.`。
- `tests/test_surprise_s11_grid.py`：第 676 行左右 `text = (FRAMEWORK / "main.py").read_text(encoding="utf-8")` 改成读 `FRAMEWORK / "surprise" / "baselines" / "coevodb_v1" / "main.py"`（它核对 `--mode` 的取值表，表跟着 `main.py` 搬走了）。同一个文件里的 `test_no_llm_command_is_unchanged` 前半段（命令行仍是 `FRAMEWORK / "main.py"`）**不改**：`old_no_llm.py` 照旧调用 `framework/main.py`，经转发跑新位置的代码。这是本包唯一允许改动的 `test_surprise_*` 文件，只改这一处路径。
- 仓库根 `.gitignore`：`framework/repair_bench/runs/` → `framework/archive/repair_bench/runs/`。

改完用 `git grep` 查一遍，仓库里不应再有导入 `coevo`、`guidelines`、`coverage`、`repair_bench`、`evolution.bandit|co_evolution|coverage|playbook`、`agents.bug_hunter` 旧位置的语句（门槛 `imports` 组静态查全部 `.py`）。注释、docstring、日志字符串里的旧路径不改。

## 背景

- 为什么不整目录搬：S8 门槛核对钉住的 3 小时长跑的两份指纹——`surprise/hunter/`、`diagnoser/`、`experiments/` 的代码摘要，与 harness 的 `HASHED_PATHS`（`surprise/harness/manifest.py`，含 `agents/bug_fixer.py`）。动了其中任何一个文件，长跑就要重跑重钉。所以本包**不改** `surprise/` 下除 `V1/` 与上面那一处测试以外的任何文件，也不改 `HASHED_PATHS` 列出的旧文件。
- 门槛 `moves` 组拿 `s11-done-r2` 的每个旧 `.py` 与现在对应位置的文件比较：把导入换成绝对的、移动前的模块名之后，AST 必须完全相同；留在原位、又不在 `IMPORT_EDITED` 表里的文件必须逐字节相同（只按 CRLF/LF 归一）。所以连空行、注释的改动都会在不该改的文件上报错；被移动的文件里改注释不会报错，但也不要改。
- 仓库开着 `core.autocrlf`，工作区文件是 CRLF。用编辑工具改导入时保持原来的行尾即可，门槛按 LF 归一比较。
- `old_arm` 组会从 `s11-done-r2` 导出旧代码，在临时目录里跑一次 2 轮的 `no_llm`，再在新位置跑同样的命令，比较产物（去掉时间、路径类字段）；之后经 `old_no_llm` 跑 1 分钟的原 CoevoDB 臂。整组约几分钟。
- `imports` 组会运行 `python test_simple.py`（coevo 的离线冒烟，几秒）和三个脚本的 `--help`。

## 允许改动的路径

```allow-paths
.gitignore
framework/main.py
framework/surprise/baselines/coevodb_v1/**
framework/archive/**
framework/evolution/__init__.py
framework/evolution/bandit.py
framework/evolution/co_evolution.py
framework/evolution/coverage.py
framework/evolution/playbook.py
framework/agents/bug_hunter.py
framework/guidelines/**
framework/coverage/**
framework/coevo/**
framework/repair_bench/**
framework/campaigns/pg_coldstart.py
framework/scripts/corpus_hunt.py
framework/scripts/flaky_mine.py
framework/scripts/llm_rule_gen.py
framework/scripts/make_playbook_seed.py
framework/scripts/make_playbook_seed_v2.py
framework/testing/test_new_components.py
framework/tests/test_diagnosis_dce.py
framework/tests/test_verified_loop.py
framework/tests/test_surprise_s11_grid.py
framework/test_simple.py
```

（原路径上的条目是给 `git mv` 留下的删除用的。）

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`、`framework/surprise/harness/`（已冻结）。
- 不改 `surprise/hunter/`、`diagnoser/`、`experiments/`、`theory/`、`features/`、`roles/`、`metrics/`、`baselines/old_no_llm.py` 等任何已有的 `surprise/` 文件（上面那一处测试路径除外）。
- 旧代码只移动、不改逻辑：只改导入路径与上面三处锚点。不顺手修旧代码里的任何问题（看到了写进报告的"未决问题"）。
- 不改 README、`framework/AGENTS.md` 与其它文档（归 `s12-docs`）；`archive/README.md` 除外。
- 不靠改测试让测试通过：不新增 skip / xfail，不删断言、不放宽断言，不用宽泛的 try/except 吞掉失败，不改 conftest。除上面列出的导入路径与那一处文件路径，测试一个字不改。
- 本包不需要密钥，也不要运行任何会调用 LLM 的东西（`make_playbook_seed*.py`、`main.py --mode full` 等）。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`；不要清理 `.orch/tmp`。
- 不建指向 worktree 之外的链接或目录联接。

## 验收命令

在 worktree 里执行。`python` 和 `pytest` 已经指向项目解释器，不要换别的。shell 是 Windows PowerShell 5.1：没有 `&&`，多条命令用 `;` 连接；中文输出可能乱码，判断结果用 ASCII 关键字。

```powershell
cd framework
python -m pytest -q testing tests                                   # 935 passed, 3 skipped（与基线相同；0 failed）
python -m surprise.gates.s12 --only layout moves imports isolation old_arm   # 5/5 PASS
python -m surprise.gates.s01                                        # PASS（main.py --help 经转发、campaigns 的 --help）
python -m surprise.gates.s07                                        # PASS（导入 evolution.dce，会经过 archive.coevo）
python -m surprise.gates.s04 ; python -m surprise.gates.s08         # PASS（harness 指纹与长跑的代码摘要都没动）
```

`python -m surprise.gates.all` 全量约 50 分钟，跑不跑由你定；跑的话 `s12` 的 `docs` 组预期失败（归 `s12-docs`），其余应全部通过。

## 收尾

1. 把改动提交到当前分支（可以分多次提交，提交信息写清做了什么）；`git status` 应当是干净的。
2. 写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式见下；"改了哪些文件"一节附上 `git diff -M --stat session/s12..HEAD` 的输出。
3. 说明有矛盾、缺前置条件或做不完：把情况写进报告，停下。不要自行扩大范围，也不要为了交差降低要求。

### 报告格式（`.orch/report.md`）

```markdown
# 报告 · s12-move

## 改了哪些文件
- `路径`：一句话说明（新增 / 修改 / 移动自哪里）

## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴，不要概括）。

## 与说明的偏差
没有就写"无"。有就逐条写：偏差是什么、为什么、影响哪里。

## 未决问题
需要编排者或用户决定的事；发现的计划外问题（只记录，不修）。没有就写"无"。
```
