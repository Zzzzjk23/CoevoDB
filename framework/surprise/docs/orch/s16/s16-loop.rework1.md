# 审查意见 · s16-loop 第 1 轮

做得好：`loop`、`grid` 两组通过，S05、S08 的六组、S15 的五组都过，S11 只有已知的 `ciao`；发现 `features/data.py` 不在允许路径里时如实停下，对。两个 `test_surprise_s03_registry.py` 的失败是已知的、等用户决定，不要动它们。

## 放行并要改：`framework/surprise/features/data.py`

这个文件本该在允许路径里，是编排者漏写了。本轮**允许改它**，只改 PostgreSQL 一支：

- `extract_data` 在 `engine == "postgres"` 时，列类型不用 `DESCRIBE <表>`（PG 没有这条语句），改为查目录，例如
  `SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a WHERE a.attrelid = to_regclass('<表的引用>') AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum`
  （引用里的单引号按 SQL 规则转义；`to_regclass` 返回 NULL 或查询报错时与现在 `DESCRIBE` 失败一样，层记 `unavailable`）。
- PG 的类型名要先在 PG 一支里翻成现有 `_type_feature` 认得的写法，再交给 `_type_feature`：`smallint`/`integer`/`bigint` → 整数，`real`/`double precision` → 浮点，`numeric(...)` → decimal，`boolean` → boolean，`character varying(...)`/`character(...)`/`text`/`name` → 字符串，`date` → date，`timestamp ... time zone` → timestamp，其余照现有规则落到 `other`。**`_type_feature`、`_type_token` 与 DuckDB / DataFusion 的路径一个字符都不动**（S5 门槛按 DuckDB 语料逐条核对数据层）。
- 测试加到 `framework/tests/test_surprise_s16_loop.py`：PG 用例的数据层 `ok`、类型叶子对（含 `character varying`、`double precision`、`numeric`）。

## 验收

同原说明：`python -m surprise.gates.s16 --only phi loop grid` 应 PASS (3/3)，`python -m surprise.gates.s05` PASS。pytest 除了两个已知的 `test_surprise_s03_registry.py` 失败之外全过。审查时编排者会把 `features/data.py` 记为本轮放行的路径。
