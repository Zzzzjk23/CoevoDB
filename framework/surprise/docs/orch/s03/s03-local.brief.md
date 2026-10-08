角色：执行者

# 工作包 s03-local：ART 索引差分与确定性改写

基线为派发时的 session/s03（registry 已合并）；只实现 S3 的 Index presence 和 Equivalent query。PLAN 第3节逐项表为标签契约。公共注册文件归其他包，你不得修改。

```allow-paths
framework/surprise/harness/oracles/index_presence.py
framework/surprise/harness/oracles/equivalent_query.py
framework/surprise/harness/oracles/rewrites.py
framework/tests/test_surprise_s03_local.py
```

## 公共接口

每个 oracle 模块导出 judge_case(case, *, factory, timeout_s, options) -> Label，并在模块末尾调用 registry.register('index_presence'或'equivalent_query', judge_case)。registry.get_handler 仅懒导入模块，模块须自行注册，不需要更改 __init__.py。options 是 registry.OracleOptions，有 rewrite_rule、paired_query、old_python、reference_factories。公共 judge 已完成目标 setup / 确定性 / 原三类前提筛查，handler 创建自己的 factory() runner 并 finally close；用 forms.full_query(case) 取得完整语句。所有标签 cve={}，不做 S4。

## Index presence

- DuckDB ART 索引有/无，两侧同 schema、同数据、同 SQL，比 multiset；先无索引再建立可用索引，设置失败不伪装为一次有效比较。可调用旧 index_variant.parse_tables，但旧 oracle 的 PG 索引 SQL 不能照搬。旧文件完全不改。
- DataFusion 返回 invalid/not_applicable；无可索引基表、非SELECT、无法建立任何有效ART索引，返回明确不适用/错误，不假 pass。
- 成功索引写 detail['indexes_created']（非空列表，名称与语句确定性）；wrong_result 身份带索引干预与行为画像，内部错误映射 crash，原SQL普通/值依赖报错判invalid。不调用 LLM。
- 保留 NULL、重复行语义；finally 清理自己的资源，禁止改服务器或全局配置。可用旧 errors/normalize/common 构造标签，所有 setup 执行结果要检查。

## Equivalent query

- 新 rewrites.py 导出 RULES 字典（每条值带 proof 字符串，说明 SQL 3VL 与等价前提）和 apply_rule(query, rule_id) -> str | None。None 表示前提不满足。至少 double_negation、demorgan、case_to_coalesce 三条，机械检查前提，不能凭在一份数据上结果相同来认证任意 SQL 对。
- double_negation 在 WHERE 谓词 p 上应用 NOT(NOT(p))；demorgan 只对安全识别的 NOT(p AND q)/NOT(p OR q)；case_to_coalesce 只对 CASE WHEN x IS NOT NULL THEN x ELSE y END，要求测试与THEN同一个安全表达式。避免 regex 穿越字符串、注释、子查询/括号或误配不同表达式；不能处理就不适用。补反例测试（NULL三值、不同THEN、文字里有关键字、括号/运算符边界、重复行）。不要把规则泛化成你没有证明的形态。
- 用旧 EquivalenceOracle 执行已认证的规则两侧；同一 runner 上查询不得改数据。option rewrite_rule=None 默认选 double_negation（形态不支持即 invalid/not_applicable）。未知 rule、外部 paired_query 没有对应认证规则、paired_query 不等于规则实际机械产出，都 invalid/untrusted_rewrite，未受信的查询不得执行。规则匹配成立而两侧出现差异，按旧 oracle 与 common 整理 fail/身份证据。旧 None 的 pass/invalid 拆分要记录真实执行。
- 规则必须有可读等价性论证与有意义的反例测试；不接 LLM 改写。错误不能靠另一条随机SQL证实。

## 派发前实测（门槛已提交，不许改）

setup：CREATE TABLE t(a INT,b INT); INSERT INTO t VALUES (1,1),(2,NULL),(3,3)。DuckDB 与 DataFusion 都实测：
1. SELECT a FROM t WHERE b > 1，与 NOT(NOT(b > 1)) 都为 [[3]]。
2. SELECT a FROM t WHERE NOT (b > 1 AND a < 3)，与 NOT(b > 1) OR NOT(a < 3) 都为 [[1],[3]]。
3. SELECT CASE WHEN b IS NOT NULL THEN b ELSE 0 END AS v FROM t，与 COALESCE(b,0) 都为 [[1],[0],[3]]。

门槛会用一个 DuckDBRunner 子类在 CREATE INDEX 后注入空结果，必须捕获 wrong_result，不能仅让常规查询过绿。

## 验收与收尾

```powershell
cd framework
python -m pytest -q testing tests
python -m surprise.gates.s03 --only local
python -m surprise.gates.s02
```

通过数不得少于149、skip不得增加。其他S3组缺并行包时预期红。python 已指向项目解释器，PowerShell5.1无&&。不改测试求绿、不改conftest。公共文件/gates/docs/CLAUDE.md/tools/orch/旧代码均禁止修改。不要清理 .orch/tmp，不装依赖、不访问密钥、不碰worktree外文件。被拒操作不能绕过。只在当前分支提交，写 .orch/report.md（文件、命令退出码与末20行、偏差、未决问题），不tag/merge/rebase/push/switch/删分支。前置缺失或说明矛盾就报告停下。
