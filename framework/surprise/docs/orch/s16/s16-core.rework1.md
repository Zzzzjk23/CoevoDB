# 审查意见 · s16-core 第 1 轮

做得好：三组门槛（instances、runner、registry）都过了，S04 只有预期中的 freeze 失败；7 个旧测试失败时你如实停下、没有改它们，这是对的。下面三处要改，其余不动。

## 1. 没配置目标实例时，`runner_factory_for("postgres")` 抛 `ValueError`

`framework/surprise/harness/oracles/registry.py`：`runner_factory_for("postgres")` 在环境变量 `COEVO_TARGET_PG_DSN` 没有值（不存在或空串）时抛 `ValueError`，消息写明要设这个变量（可提 `surprise.experiments.pg_instance`），不含任何 DSN 内容；有值时照现在返回 `PostgresTargetRunner`。`TARGET_ENGINES` 保持三个。

理由（编排者的决定）：PG 目标要每个运行自己起的实例，没起实例就"没有默认 runner"。φ 现有的约定正是这样处理没有 runner 的引擎：`features.extract.extract` / `extract_isolated` 在要计划层或数据层而没有 runner 时抛 `ValueError`，`python -m surprise.features corpus` 把它当作 `skipped`，`phi` 命令退出码 2。照这样做，你列的 7 个失败里这 5 个应当不改测试就通过，请逐个复跑确认：

- `tests/test_surprise_s03_registry.py:126` `test_runner_factory_for_maps_target_engines`
- `tests/test_surprise_s05_dynamic.py:502`、`:584`、`:612`、`:646`

S5 门槛（`python -m surprise.gates.s05`）里也有两处依赖这个约定（`extract(postgres)` 抛 `ValueError`、语料统计里 PG 种子的计划层与数据层是 `skipped`），复跑它，应当全过。

另外两个——`tests/test_surprise_s03_registry.py:68`（断言 `TARGET_ENGINES` 只有两个）与 `:181`（遍历全部目标引擎跑健全 oracle，没有 PG 实例）——是 S16 必然改变的事实，**仍然不要改**，报告里照旧列出，编排者去问用户。

## 2. `close()` 永不抛异常

现在 `close()` 在重连失败时会把 `psycopg2` 的异常抛出去（例如服务器正在崩溃恢复）。`close()` 在 oracle 的 `finally` 里调用，一抛就把已经得出的标签（包括 crash 的 fail）变成 `harness_error`。改成：尽力删 schema（可以按第 3 条重试），实在不行就放弃（残留的 schema 随每格实例一起删掉，可以接受），最后关连接，不抛异常。

## 3. 服务器崩溃重启期间，连接重试

PG 的后端崩溃（段错误、断言）会让 postmaster 进入恢复模式，几秒内拒绝新连接（`the database system is in recovery mode`、`starting up`、`Connection refused` 等 `OperationalError`）。旧的 `targets/postgres_runner.py` 为此在 `connect()` 里重试 30 次、每次 0.5 秒。`_connect()` 也要这样：遇 `psycopg2.OperationalError` 重试，最多约 30 秒，之后再抛。这样 CVE 的新进程重跑在崩溃之后还能连上、复现崩溃，而不是 `harness_error`。认证失败这类不会自己好的错误可以不重试（你判断，写进报告）。

测试：给 1、2、3 各加测试（3 可以 monkeypatch `psycopg2.connect` 先失败几次再成功，或先失败超过时限；2 可以让重连失败）。

## 验收

同原说明的验收命令；另跑 `python -m surprise.gates.s05` 与 `python -m surprise.gates.s03`（都应 PASS）。pytest 结果写清楚：除了上面两个已知会失败的测试之外，其余必须全过。
