# 报告 · s10-oracle

## 改了哪些文件

- `framework/surprise/roles/oracle_inventor.py`：新增。oracle 发明者按实验节奏向网关提议 `query_wrap` / `predicate_wrap` 模板，多引擎一致才写入 `rewrites.json`。

- `framework/tests/test_surprise_s10_oracle_inventor.py`：新增。覆盖调用节奏、提示纯度、每种拒收原因、真实引擎验收、`load_library`、`rules()` 与 `certify`。

提交：`c63aeb2`，分支 `grok/s10-oracle`。

## 跑了哪些命令

下面每段是命令、退出码、输出的最后 20 行（不足 20 行则整段）。未跑 `python -m surprise.gates.s10` 的 `isolation` 与 `switches`（要六个角色都在），也未跑 `python -m surprise.gates.all`。说明要求本包不跑这两项。

### 起点全套

```
cd framework
python -m pytest -q testing tests
```

退出码：0

```
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[33ms[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 10%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 20%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 30%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 40%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 50%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 60%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 70%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 80%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m [ 90%]
[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m    [100%][0m
[32m[32m[1m714 passed[0m, [33m3 skipped[0m[32m in 169.13s (0:02:49)[0m[0m
```

### 本包测试

```
cd framework
python -m pytest -q tests/test_surprise_s10_oracle_inventor.py
```

退出码：0

```
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                              [100%][0m
[32m[32m[1m11 passed[0m[32m in 2.80s[0m[0m
```

### S10 门槛（指定的五组）

```
cd framework
python -m surprise.gates.s10 --only constants frozen library frame oracle_inventor
```

退出码：0

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
[PASS] frozen: harness changes since s09-done-r2: ['equivalent_query.py', 'rewrites.py']; re-frozen and verified; 12 frozen-rule outputs unchanged with and without a library (0s)
[PASS] library: 4 usable and 10 refused templates; 8 malformed libraries refused; judgements {'llm:wrap_sub': 'pass', 'llm:is_true': 'pass', 'llm:first_row': 'untrusted_rewrite/reference_disagrees', 'llm:octet': 'untrusted_rewrite/rewrite_error'}; frozen rule unchanged; no library, no trust (5s)
[PASS] frame: prior moves U 0.498 -> 1.000; extra rules offered; prepare once per round (1 rounds); vocabulary run extracts ast:set_op:except_all_two_tables (19s)
[PASS] oracle_inventor: accepted ['llm:wrap_sub'] on 5 instances; refused disagree, template, duplicate; 3 calls in 401 experiments; judged by the harness: pass (2s)
S10 GATE [only: constants, frozen, library, frame, oracle_inventor]: PASS (5/5 groups passed)
```

### S09 门槛（指定的三组）

```
cd framework
python -m surprise.gates.s09 --only isolation wiring replay
```

退出码：0

```
[PASS] isolation: roles load no model client until a transport is built; loop, Hunter, Diagnoser, harness never import them; transport reuses BaseAgent and the old ledger (1s)
[PASS] wiring: off: 40 rows identical to S8, no role loaded; on: 7 scripted calls, 0 implementer experiments meeting their specs; cap 0 completes (53s)
[PASS] replay: 21 experiments and 25 calls replayed from the cache, identical; lanes {'bootstrap': 1, 'generalize': 5, 'bet': 5, 'implement': 7, 'refine': 3}; book {'conjectures': 3, 'rejected': 0, 'predictions': 12, 'open': 4, 'kept': 6, 'broken': 2} (50s)
S09 GATE [only: isolation, wiring, replay]: PASS (3/3 groups passed)
```

### 改完之后的全套

```
cd framework
python -m pytest -q testing tests
```

退出码：1

```
================================== FAILURES ===================================
[31m[1m_________ test_build_roles_knows_six_names_and_loads_only_the_ones_on _________[0m

tmp_path = WindowsPath('D:/CoevoDB/.worktrees/s10-oracle/.orch/tmp/pytest-of-91484/pytest-3/test_build_roles_knows_six_nam0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000002C44BA0BE70>

    [0m[94mdef[39;49;00m[90m [39;49;00m[92mtest_build_roles_knows_six_names_and_loads_only_the_ones_on[39;49;00m(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> [94mNone[39;49;00m:[90m[39;49;00m
        [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33munknown role[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
            _roles(tmp_path / [33m"[39;49;00m[33mbad[39;49;00m[33m"[39;49;00m, ([33m"[39;49;00m[33mdiagnoser[39;49;00m[33m"[39;49;00m,))[90m[39;49;00m
        [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33mnon-empty[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
            _roles(tmp_path / [33m"[39;49;00m[33mempty[39;49;00m[33m"[39;49;00m, ())[90m[39;49;00m
        [94mfor[39;49;00m name [95min[39;49;00m ([33m"[39;49;00m[33mprior[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33mtranslator[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33mvocab_inventor[39;49;00m[33m"[39;49;00m, [33m"[39;49;00m[33moracle_inventor[39;49;00m[33m"[39;49;00m):[90m[39;49;00m
>           [94mwith[39;49;00m pytest.raises([96mValueError[39;49;00m, match=[33m"[39;49;00m[33mnot available[39;49;00m[33m"[39;49;00m) [94mas[39;49;00m caught:[90m[39;49;00m
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^[90m[39;49;00m
[1m[31mE           Failed: DID NOT RAISE ValueError[0m

[1m[31mtests\test_surprise_s10_frame.py[0m:249: Failed
[36m[1m=========================== short test summary info ===========================[0m
[31mFAILED[0m tests/test_surprise_s10_frame.py::[1mtest_build_roles_knows_six_names_and_loads_only_the_ones_on[0m - Failed: DID NOT RAISE ValueError
[31m[31m[1m1 failed[0m, [32m724 passed[0m, [33m3 skipped[0m[31m in 169.74s (0:02:49)[0m[0m
```

## 与说明的偏差

1. `oracle_prompt` 比说明里的签名多一个可选关键字参数 `call: int | None = None`。传入时，提示最后一行是 `This is proposal round {call} of {ORACLE_CALLS_PER_RUN}.`。角色每次调用都传 `call=self._calls + 1`。原因：网关按提示文本缓存回复。第 1 次调用若没有收下规则，第 2 次与第 3 次的库相同，提示文本相同，传输不会再次执行，而门槛要 `len(script.calls) == 3`。这一行是调度轮次，回放时稳定，不是记录号、假设号或运行号。不传 `call` 时，提示正文与说明第 2 节一致。影响：`s10 --only oracle_inventor` 能计满 3 次调用并通过；省略这一行时该组会计成 1 次调用并失败。

2. 第 6 节的可选真实调用没有做。调用次数 0，模型没有提出模板，验收结论无。缓存目录未使用。验收由脚本传输、本包测试和上面的门槛覆盖。

3. 起点那次全套是在 `test_surprise_s10_oracle_inventor.py` 被收集之前跑的，结果 714 passed、3 skipped、退出码 0。`oracle_inventor.py` 在那次运行中途才出现；套件仍以 0 退出，说明 `test_surprise_s10_frame.py` 里那条「角色尚不存在」的断言当时已经跑完。改完后的全套是 724 passed、3 skipped、1 failed。

## 未决问题

`framework/tests/test_surprise_s10_frame.py::test_build_roles_knows_six_names_and_loads_only_the_ones_on` 对 `prior`、`translator`、`vocab_inventor`、`oracle_inventor` 逐个期望 `ValueError` 且消息匹配 `not available`。本 worktree 里前三个模块文件不存在，第四个 `framework/surprise/roles/oracle_inventor.py` 已存在，所以循环在 `oracle_inventor` 上得到 `Failed: DID NOT RAISE ValueError`（`tests/test_surprise_s10_frame.py:249`）。同函数后面「`surprise.roles.oracle_inventor` 不在 `sys.modules`」的断言没有执行到。这条测试不在允许改动的路径里，本包没有改它，也没有把模块做成不可导入（那样 S10 的 `oracle_inventor` 组过不了）。因此 `python -m pytest -q testing tests` 的退出码是 1。通过数 724，不少于起点 714；skip 仍是 3。本包 11 条测试、S10 指定的 5 组和 S09 指定的 3 组都是退出码 0。另一分支 `grok/s10-testfix` 的 `5451d74` 已把这条断言改成「指向磁盘上不存在的模块再期望 not available」。该提交不是本分支的祖先，本包没有把它合并进来。
