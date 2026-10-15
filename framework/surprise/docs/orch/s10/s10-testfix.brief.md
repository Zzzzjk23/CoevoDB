角色：执行者

# 工作包 s10-testfix：`test_build_roles_knows_six_names_and_loads_only_the_ones_on` 不再依赖哪些角色模块已经存在、哪些测试先跑

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s10-testfix`）。只做这一个工作包；这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`session/s10`（`s10-frame`、`s10-harness` 已合并）
- 所属会话：S10，范围见 `framework/surprise/docs/SESSIONS.md` 的 S10 一节
- 先读：`framework/tests/test_surprise_s10_frame.py` 全文；`framework/surprise/roles/runtime.py` 的 `build_roles` 与 `_load_plugins`；`framework/surprise/roles/base.py` 的 `PLUGINS`（`runtime.py` 用 `from .base import PLUGINS` 拿到的是同一个 dict 对象）。

## 问题

`tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on` 有两处依赖环境：

1. 它对 `prior`、`translator`、`vocab_inventor`、`oracle_inventor` 逐个断言 `build_roles` 抛 `ValueError("... not available ...")`，前提是这四个模块都不存在。并行的角色包一合并（`surprise/roles/prior.py` 已经写好、等着合并），这一段就失败（实测：`DID NOT RAISE ValueError`）。
2. 后半段断言 `"surprise.roles.vocab_inventor" not in sys.modules`、`"surprise.roles.oracle_inventor" not in sys.modules`，前提是同一个 pytest 进程里没有别的测试先导入过它们。角色包的测试一合并，这两条就会因执行次序而失败（S9 的 `s09-testfix` 修过同一类问题）。

## 目标

只改这一个测试函数，让它测的东西不变、并且不因上面两件事失败，断言不放宽：

1. "开着却不存在的角色报 `not available`、不是 `unknown role`"：对四个名字中的每一个，用 `monkeypatch.setitem(base.PLUGINS, name, f"surprise.roles._s10_missing_{name}")` 把它指到一个**确实不存在**的模块路径（先断言这个路径不在 `sys.modules` 里，`importlib.util.find_spec` 找不到它），再断言 `build_roles` 抛 `ValueError` 且信息含 `not available`、不含 `unknown role`，并且那个路径仍不在 `sys.modules` 里。每个名字测完把 `PLUGINS` 恢复（`monkeypatch` 自己会恢复；如果你在同一个函数里还要用真模块路径，就用 `monkeypatch.context()` 包住这一段）。
2. "没开的角色不被导入"：在调用 `_roles(... ("translator", "prior", "prior") ...)` 之前，用 `monkeypatch.delitem(sys.modules, 模块名, raising=False)` 把 `surprise.roles.vocab_inventor`、`surprise.roles.oracle_inventor`（以及测试里用的假模块名）从 `sys.modules` 里拿掉（`monkeypatch` 会在测试结束后放回去），然后照原样断言它们不在 `sys.modules` 里。其余断言一条不改。

## 允许改动的路径

```allow-paths
framework/tests/test_surprise_s10_frame.py
```

只改上面那一个测试函数；文件里别的函数、辅助函数一个字都不改（如果确实要加一个小辅助函数，只能加，不能改已有的）。

## 禁止

- 不改任何别的文件；不改 `framework/surprise/` 下的任何代码；不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`。
- 不靠放宽断言让测试通过：不新增 skip / xfail，不删断言，不用宽泛的 try/except，不改 conftest。上面第 1、2 条描述的替换（把"四个模块都不存在"的前提换成"指到确实不存在的模块"；导入检查之前先从 `sys.modules` 拿掉）是唯一允许的改法。
- 不做任何 LLM 调用。
- 不打 tag，不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree；不改 `HANDOFF.md`、`DECISIONS.md`。
- 不建指向 worktree 之外的链接或目录联接；不要清理 `.orch/tmp`。

## 验收命令

在 worktree 里执行，全部通过才算完成。`python` 和 `pytest` 已经指向项目解释器。shell 是 Windows PowerShell 5.1（没有 `&&`，用 `;`）。worktree 里跑测试一律用 `python -m pytest`。

```powershell
cd framework
python -m pytest -q tests/test_surprise_s10_frame.py      # 全部通过
python -m pytest -q testing tests                          # 全部通过，skip 仍是 3
```

另外证明它不依赖角色模块是否存在：在 `.orch/tmp/` 下临时建一个只含 `def build(ctx): ...` 的假包目录不行（不能碰 `surprise/roles/`），所以改用这条命令（它在测试进程里预先导入一个名为 `surprise.roles.vocab_inventor` 的空模块，模拟别的测试先导入过）：

```powershell
python -c "import sys, types, pytest; sys.modules['surprise.roles.vocab_inventor'] = types.ModuleType('surprise.roles.vocab_inventor'); sys.exit(pytest.main(['-q', 'tests/test_surprise_s10_frame.py']))"
```

这条也必须全部通过。

## 收尾

1. 把改动提交到当前分支；`git status` 应当是干净的。
2. 写 `.orch/report.md`（不入库），格式：

```markdown
# 报告 · s10-testfix

## 改了哪些文件
## 跑了哪些命令
每条命令给出：命令本身、退出码、输出的最后 20 行（原样贴）。
## 与说明的偏差
## 未决问题
```
