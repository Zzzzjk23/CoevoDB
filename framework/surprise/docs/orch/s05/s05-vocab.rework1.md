# 审查意见 · s05-vocab · 第 1 轮返工

独立复跑：pytest 293 passed / 3 skipped；S01–S04 通过；S05 的 `vocab spec units` 三组通过。编排者另做的探测（词表层级、开放族边界、登记的每条拒绝理由、规格核对对照独立读法 400 组、单元 600 组）全部通过。词表、注册表的查询与登记、规格核对、单元投影都不要动。

下面三处要改，都很小。

## 1. `Phi.from_dict` 不校验

文件：`framework/surprise/features/phi.py`。

φ 会存进账本（`ExperimentRecord.phi`），S6 之后从账本读回来。现在 `from_dict` 对任何 dict 都照单全收：多余的键、`schema` 不是 1、`features` 是字符串或没排序、`layers` 缺键，都不报错。

改成读入时做结构校验，不需要注册表，任何一条不满足抛 `ValueError`：

- 键恰好是 `schema`、`engine`、`features`、`layers`、`vocab`，`schema == 1`；
- `engine`、`vocab` 是非空字符串；
- `features` 是字符串列表，严格升序（也就排除了重复）；
- `layers` 的键恰好是 `ast`、`plan`、`data`，取值范围与 `make_phi` 相同。

直接构造 `Phi(...)` 的行为保持现状；`make_phi` 不变。

## 2. `Registry.load` 不校验

文件：`framework/surprise/features/registry.py`。

`load` 只检查 id 没和已有的重复，文件里写什么就收什么：`source="base"`、`kind="class"`、编译不了的正则、父类不存在，都能进注册表。这个文件以后由 S10 的词汇发明者写。

改成对文件里的每一项用与 `register` 相同的规则校验（id 写法、未被认识、叶子、非 base 来源、层一致、父类是同层已登记的 class、regex 定义能编译）。与 `register` 唯一的不同是验收状态可以已经有了：`accepted` 为真时 `acceptance` 必须是非空 dict，为假时必须是 `None`。任何一项不合格整个 `load` 抛 `ValueError`。`save` 写出的文件必须能原样读回。

## 3. S4 测试夹具的进程退出方式（不属于本包原范围，本轮额外放行）

文件：`framework/tests/test_surprise_s04_runners.py`。本轮允许改这个文件，只做下面这件事。

你在报告里提到 S4 门槛隔离组偶发失败一次。编排者查了：夹具用 `os._exit(77)` 退出时，DuckDB 的工作线程还在运行，进程在卸载库的过程中约 0.5% 的概率以访问冲突（退出码 0xC0000005）而不是 77 结束；重跑比较退出码，于是判成不稳定。实测 400 次里 2 次。换成立即终止（不跑任何退出处理）后 600 次退出码全部是 77。正常的子进程 600 次没有一次异常，harness 没有问题。门槛的夹具编排者已经改了；`tests/test_surprise_s04_runners.py` 里的 `ExitingRunner`、`ZeroExitRunner`、`ExitingReference` 是同样的写法，全套测试因此有同样的偶发失败。

改成：加一个模块级函数，立即结束当前进程并给出指定退出码，三个夹具都用它代替 `os._exit`：

```python
def die(code: int) -> None:
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess.restype = ctypes.c_int
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    else:
        os.kill(os.getpid(), signal.SIGKILL)
    os._exit(code)
```

注意 `restype` 与 `argtypes` 必须像上面这样写：不写的话 64 位下伪句柄被截成 32 位，`TerminateProcess` 静默失败，等于没改。不要改这个文件里别的东西，不要改 `test_surprise_s04_pipeline.py` 里的断言。

## 测试

- 第 1、2 条各补测试：每一种不合格输入都被拒绝；合格的往返不变。
- 第 3 条不需要新测试。

## 验收

在 worktree 里，`python` 与 `pytest` 用现成的：

```powershell
cd framework
python -m pytest -q testing tests                       # 0 failed，不少于 293 passed，skip 不多于 3
python -m surprise.gates.s01
python -m surprise.gates.s02
python -m surprise.gates.s03
python -m surprise.gates.s04
python -m surprise.gates.s05 --only vocab spec units
```

都是退出码 0。范围、禁区、报告格式仍以 `.orch/brief.md` 为准，本轮额外允许改 `framework/tests/test_surprise_s04_runners.py`（只限第 3 条）。`.orch/tmp` 里的文件不要删。改完提交到当前分支，更新 `.orch/report.md`（保留第一轮内容，在后面加"第 1 轮返工"一节）。
