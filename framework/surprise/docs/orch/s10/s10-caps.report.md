# 报告 · s10-caps

## 改了哪些文件

- `framework/surprise/roles/constants.py`
  - `TRANSLATOR_MAX_TOKENS`：8000 → 16000
  - `VOCAB_MAX_TOKENS`：8000 → 16000
  - `ORACLE_MAX_TOKENS`：8000 → 16000
  - 三个常数的原注释下各加一行：`deepseek-flash counts reasoning tokens inside max_tokens, so 8000 truncated replies before JSON.`
  - `PRIOR_MAX_TOKENS` 仍为 8000。S9 的常数未改。

## 跑了哪些命令

### 1

```powershell
cd framework
python -m pytest -q testing tests
```

退出码：0

输出的最后 20 行：

```
........................ss..................................s........... [  9%]
........................................................................ [ 18%]
........................................................................ [ 27%]
........................................................................ [ 37%]
........................................................................ [ 46%]
........................................................................ [ 55%]
........................................................................ [ 64%]
........................................................................ [ 74%]
........................................................................ [ 83%]
........................................................................ [ 92%]
.........................................................                [100%]
774 passed, 3 skipped in 183.38s (0:03:03)
```

### 2

```powershell
cd framework
python -m surprise.gates.s10 --only constants
```

退出码：0

输出的最后 20 行：

```
[PASS] constants: 35 S10 constants as planned, S9 constants unchanged, library constants ['LIBRARY_ENV', 'LIBRARY_KINDS', 'LIBRARY_MIN_REFERENCES', 'LIBRARY_RULE_PREFIX', 'LIBRARY_SCHEMA'] (0s)
S10 GATE [only: constants]: PASS (1/1 groups passed)
```

### 3

```powershell
cd framework
python -m surprise.gates.s09 --only constants
```

退出码：0

输出的最后 20 行：

```
[PASS] constants: 19 constants as planned; tiers {'fast': 'deepseek-flash', 'strong': 'deepseek-v4-pro'} (0s)
S09 GATE [only: constants]: PASS (1/1 groups passed)
```

## 与说明的偏差

无。原因那一句按「英文，一行」写在三个常数各自的注释下，句子相同。说明没有要求只出现一次。

## 未决问题

无。
