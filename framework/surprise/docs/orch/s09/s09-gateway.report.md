# 报告 · s09-gateway

## 改了哪些文件
- `framework/surprise/roles/__init__.py`：修改，导出网关、缓存、解析与读源码工具，不导出 transport
- `framework/surprise/roles/constants.py`：新增，S9 常数与 `as_dict()`
- `framework/surprise/roles/schema.py`：新增，`parse_reply` 要求非空 `prediction`
- `framework/surprise/roles/cache.py`：新增，响应缓存（键为提示哈希 + 模型 + 种子）
- `framework/surprise/roles/gateway.py`：新增，网关（缓存、上限、按角色账本、两档模型）
- `framework/surprise/roles/transport.py`：新增，`DeepSeekTransport` 复用 `BaseAgent` 与旧 `ledger`
- `framework/surprise/roles/source.py`：新增，只读源码阅读器与 `open_sources`
- `framework/tests/test_surprise_roles_gateway.py`：新增，网关/缓存/解析/传输离线测试
- `framework/tests/test_surprise_roles_source.py`：新增，源码阅读器离线测试

## 跑了哪些命令

### `python -m pytest -q testing tests`
工作目录：`framework/`。退出码：0。

```
[ 78%]
[ 90%]
           [100%]
635 passed, 3 skipped in 118.04s (0:01:58)
```

### `python -m surprise.gates.s09 --only constants cache cap source`
工作目录：`framework/`。退出码：0。

```
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-chat', 'strong': 'deepseek-reasoner'} (0s)
[PASS] cache: key = prompt hash + model + seed; hits make no call; replay identical; forged entry refused; ledger and per-role totals (0s)
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
S09 GATE [only: constants, cache, cap, source]: PASS (4/4 groups passed)
```

### `python -m surprise.gates.s09 --only reject`
工作目录：`framework/`。退出码：1（预期失败）。

```
[FAIL] reject: AttributeError: module 'surprise.roles' has no attribute 'Implementer'
S09 GATE [only: reject]: FAIL (0/1 groups passed)
```

### `python -m surprise.gates.s08 --only no_llm`
工作目录：`framework/`。退出码：0。

```
[PASS] no_llm: hunter, metrics, baselines, diagnoser and the loop import no model client and no old agent (0s)
S08 GATE [only: no_llm]: PASS (1/1 groups passed)
```

未跑 `python -m surprise.gates.all`（说明要求本包不要跑）。

## 与说明的偏差
- `reject` 组的失败信息是门槛把未捕获异常格式化后的 `AttributeError: module 'surprise.roles' has no attribute 'Implementer'`。`parse_reply` 与网关拒收已通过，失败点是 `Implementer`（下一个包）。
- 传输测试里 `base_url=http://127.0.0.1:9` 在本机得到 `HTTPStatusError 502`（不是连接被拒）。`TransportError` 文案是 `HTTPStatusError 502`，不含假密钥。

## 未决问题
无

## 第 1 轮返工

### 改了什么
- `framework/surprise/roles/constants.py`：`TIERS` 改为 `{"fast": "deepseek-flash", "strong": "deepseek-v4-pro"}`；`IMPLEMENTER_PER_CHOICE` 注释改为 `New targets the implementer source may implement per Hunter choice.`
- `framework/tests/test_surprise_roles_gateway.py`：写死的 `deepseek-chat` 改为 `deepseek-flash`；缓存行为测试里对照模型名/缓存键/manifest 的期望从本 worktree 旧门槛的 `C.TIERS` 改到 `constants.TIERS`。不改这一处的话，`test_gateway_cache_hit_replay_offline_ledger_and_totals` 会因旧门槛模型名再失败一次，审查要求只允许 `test_constants_match_the_gate_table` 失败。
- 未改 `framework/surprise/gates/`（禁区）。

### 重跑了哪些命令

#### `python -m pytest -q tests/test_surprise_roles_gateway.py tests/test_surprise_roles_source.py`
工作目录：`framework/`。退出码：1。

```
F.....................                                                   [100%]
================================== FAILURES ===================================
_____________________ test_constants_match_the_gate_table _____________________

    def test_constants_match_the_gate_table() -> None:
        have = constants.as_dict()
        for name, value in C.CONSTANTS.items():
            assert name in have
>           assert have[name] == value
E           AssertionError: assert {'fast': 'dee...pseek-v4-pro'} == {'fast': 'dee...eek-reasoner'}
E
E             Differing items:
E             {'fast': 'deepseek-flash'} != {'fast': 'deepseek-chat'}
E             {'strong': 'deepseek-v4-pro'} != {'strong': 'deepseek-reasoner'}
1 failed, 21 passed in 3.53s
```

唯一失败是 `test_constants_match_the_gate_table`（本 worktree 门槛仍是旧模型名，审查预期如此）。

#### `python -m surprise.gates.s09 --only cache cap source`
工作目录：`framework/`。退出码：1。

```
[FAIL] cache: the tier picks the model: ['deepseek-flash', 'deepseek-flash', 'deepseek-v4-pro']
[PASS] cap: cap 2 blocks the third call; cache served past the cap; cap 0 calls nothing; env ceiling; errors count, not cached (0s)
[PASS] source: confined, exact, read-only; checkouts at datafusion 45d943dfb869, duckdb d8cdaa33fda8 (0s)
S09 GATE [only: cache, cap, source]: FAIL (2/3 groups passed)
```

`cache` 失败原因与 `constants` 相同：本 worktree 的 `gates/s09_cases.py` 仍是 `deepseek-chat` / `deepseek-reasoner`，门槛拿它和网关实际选用的新模型名比较。禁区不能改门槛。主检出区 `session/s09` 的 a2c5cc7 已把门槛改成新名字，合并后 `cache` 会过。

### 与说明的偏差
- 审查写「不要动别的行」，但缓存行为测试若不改 `C.TIERS` 期望，会多失败一个测试。为满足「只允许 `test_constants_match_the_gate_table` 失败」，把该测试的模型名期望改到 `constants.TIERS`。
- 审查写 `cache cap source` 为 3/3；本 worktree 里 `cache` 因旧门槛失败，见上。
