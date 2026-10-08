角色：执行者

# s03-cross 第1轮返工：单条语句与事务隔离

编排者已读完全部3个新增文件与14条shell命令，独立pytest184 passed/3 skipped，S01/S02与原cross组通过。但你承诺的单条只读查询与close回滚隔离存在实际缺口，暂不合并。

1. pg_reference.is_readonly_query('SELECT 1; SELECT 2') 和 'SELECT 1; SET ROLE coevo' 目前返回True。拒绝有第二条可执行语句的query，在runner执行前返回not_applicable；cross也不得把这种query执行后算成一张bag。
2. setup只检查首词。'SELECT 1; COMMIT' 和 'CREATE TABLE z(a INT); END' 目前传给_execute，会破坏事务隔离。setup每个列表元素只允许一条语句，事务控制必须在后端执行前拒绝，不能先执行DDL再报错。COMMIT/END/ROLLBACK等均覆盖。
3. 词法检查应保守：允许单个尾分号，正确忽略字符串、带引号标识符、行/块注释（含嵌套）、美元引号里的分号或控制词；不支持的形式可拒绝，不可错误地拆分后只检查首句。不要引入依赖、不要依赖local包。
4. 增加回归测试：无DB的记录runner确认无任何_execute调用；真实PG普通语句、引用/注释中的分号仍可执行、两runner隔离与close后schema为0。不要真的执行COMMIT反例污染数据库。原有断言、法定数、DF-A/B期望全部保留，不加skip/xfail。

编排者已在主检出区gates/s03.py的cross组补这些断言并实测拦下本次HEAD；worktree内的门槛仍是派发基线，请勿改门槛。编排者用`.venv/Scripts/python.exe .orch/scratch/s3_root_gate.py s03-cross --only cross`从根检出区对你的分支跑新版门槛。

允许路径仍仅brief内3个文件。复跑pytest及原cross/S02门槛，提交并更新.orch/report.md；不merge/rebase/tag、不改外部服务和公共文件。不存在批准扩展范围。
