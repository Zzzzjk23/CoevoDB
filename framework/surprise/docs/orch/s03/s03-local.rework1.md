角色：执行者

# s03-local 第1轮返工：证明前提与pair校验

编排者已读完4个新增文件与13条shell命令。独立pytest183 passed/3 skipped，S01/S02与旧local组通过，ART普通/注入分支认可。但以下实测反例违反等价前提，不能合并。

1. `SELECT a FROM t WHERE NOT (b BETWEEN 1 AND 3)` 当前改成`(NOT (b BETWEEN 1)) OR (NOT (3))`。
2. `SELECT a FROM t WHERE NOT (CASE WHEN a > 0 THEN b > 0 AND b < 5 ELSE FALSE END)` 当前在CASE内部AND处切开。setup t(a,b)=(1,1),(2,NULL),(3,3),(4,6)，两个原query在DuckDB和DataFusion成功并返回[[4]]，两个rewrite都语法错误，judge误报fail/error_mismatch。

De Morgan证明覆盖二元逻辑连接词；BETWEEN/CASE等语法内部AND不是连接词。此次选择保守拒绝这些形态：apply_rule返回None，judge invalid/not_applicable，不增加新规则、不引入SQL解析依赖。确保SQL其它嵌套表达式不会被类似误拆；可保守限定被支持的语法。原有正常NOT(p AND q)、NOT(p OR q)和NULL/重复行覆盖必须保留。

3. `_canon`整体lower/split会接受改变字符串或引用标识符的paired_query。例如`SELECT CASE WHEN s IS NOT NULL THEN s ELSE 'ABC' END FROM t`的机械产物为`SELECT COALESCE(s, 'ABC') FROM t`，传入`'abc'`版当前pass。必须invalid/untrusted_rewrite且不执行外部pair。可以只接受字节一致或保守词法归一化，但字符串、引用标识符、美元引号文本、字面量内部空白不可变化。保留允许未引用SQL关键字大小写/外部空格变化的测试（若采用严格字节比较，明确报告接口收窄并调整仅这项过时测试，不删其它断言）。实际永远只执行机械产物。

已在主检出区gates/s03.py补以上断言并确认当前HEAD被拦下。worktree门槛仍是原派发版本，勿改。编排者用`.venv/Scripts/python.exe .orch/scratch/s3_root_gate.py s03-local --only local`独立运行最新门槛。

增加真正有区分力的回归测试；不加skip/xfail，不改旧代码/公共文件/门槛/docs/conftest。允许路径仍仅brief4个文件。复跑pytest和原local/S02门槛，提交，更新.orch/report.md。没有扩展其它会话范围的授权。
