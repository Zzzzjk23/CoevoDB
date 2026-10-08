角色：执行者

# 工作包 s03-version：新旧两引擎执行与回归方向证据

基线为派发时的session/s03，registry和cross已合并。只做S3 Version differential。依据PLAN第3节：新旧不同且旧版获其他独立引擎多数支持，或新版被前四类之一独立见证，才fail/regression；方向不可定则invalid。

```allow-paths
framework/surprise/harness/oracles/version_differential.py
framework/surprise/harness/oracles/version_worker.py
framework/tests/test_surprise_s03_version.py
```

## 接口与执行

导出judge_case(case, *, factory, timeout_s, options)->Label，模块末尾调用registry.register('version_differential', judge_case)，公共registry懒导入，不改公共文件。options.old_python可显式指定字符串路径；否则按平台Scripts/python.exe或bin/python，定位主检出区.venvs/duckdb-1.1.3和.venvs/datafusion-50.0.0，COEVO_VENVS可覆盖。worktree需通过git公共目录找到主检出区，gates/s01.py的venv_python/环境定位可参考但不得改它。

旧DataFusion环境只有datafusion/pyarrow，没有duckdb或psycopg2，不许安装它们。新version_worker入口直接通过文件路径执行（建议-I），其DataFusion路径仅导入datafusion与标准库，不导入surprise/targets/oracles。DuckDB路径也只需duckdb与标准库。旧代码写死bin/python和Unix PATH，别复用那个启动逻辑、也别改旧代码。

JSON输入setup+完整query+engine，输出真实engine_version、原始行/错误等；Decimal/date/datetime/bytes需要稳定且不丢类型的JSON传输，主进程再按既有normalize规则归一化。旧进程不做标签判定、不读密钥，子进程去掉DEEPSEEK_API_KEY；不能打印环境。新/旧setup错误、超时、非法输出、不存在解释器等明确invalid，不伪装成pass。

新旧一致：pass（即使都错，差分没有信号）。不一致：
1. 复用cross_dbms.default_reference_factories和collect_reference_results获取独立参照，旧结果获至少两个独立引擎一致支持且新版是唯一不同，才有多数方向证据。版本别名不算独立。调用者给空reference_factories表示没有参照。
2. 或独立调用公开judge的tlp/norec/plan_variant/index_presence（仅已可用、满足前提的类型）对新版见证fail，记录完整标签证据；不能把version差异本身当独立见证、不能把crash旧版误称新回归。新版独立见证的身份要带进version标签。
local包可能仍在并行审查、派发基线可能没有index_presence模块。仅确实未实现的可选见证可跳过，不能让缺该模块把方向不可定变成harness_error。测试要模拟缺模块而不依赖它长期不存在，合并local后仍须有效；不要吞其它见证运行错误或把它们当fail。
3. 否则invalid/direction_unknown。不以“较新版必然更错”或人工期望行给任意差分定方向。

detail至少old_version/new_version/old_rows/new_rows/direction/direction_evidence。fail时direction='regression'且direction_evidence非空；同输入标签稳定（不要放耗时/临时随机路径）。wrong_result行为画像、错误分类按共享标签规则；不做CVE重跑/最小化。

## 回归门槛来自本机实测

docs/FAMILY_LEDGER_155.md的版本梯中F2，docs/recall_repros.json['F2']：setup src(a,b,v)=(1,1,10),(1,2,20)。
query SELECT SUM(v) OVER (PARTITION BY a, a, b) AS w_aab, SUM(v) OVER (PARTITION BY a, a, a) AS w_aaa FROM src ORDER BY b。
DuckDB1.1.3为[[10,30],[20,30]]，1.5.5为[[10,10],[20,20]]，新版plan_variant已独立fail/wrong_result/no_optimizer。选F2，不选未指定ASOF并列的F3。
编排者另实测DataFusion54/PG16/SQLite3.51执行F2全为[[10,30],[20,30]]，支持旧版方向。门槛还会用reference_factories={}检查F2仍可由新版plan_variant独立见证回归，不能只有多数支路可用。
另：SELECT version() 两个DuckDB版本会返回不同字符串，但独立sound oracles都不见证错误；reference_factories={} 时必须invalid/direction_unknown，不能拿这个metadata差异当bug。
基础SELECT a,b FROM t WHERE b>1在两个DuckDB和两个DataFusion版本上必须pass；旧DF实际版本50.0.0，新54.0.0。
DataFusion50/54的SELECT version()分别为Apache DataFusion 50.0.0/54.0.0，reference_factories={}也必须invalid/direction_unknown。

## 验收与收尾

```powershell
cd framework
python -m pytest -q testing tests
python -m surprise.gates.s03 --only version
python -m surprise.gates.s02
```

不少于149测试，skip不增加。新增方向、双方都错、新版正常而旧版内部错误、子进程超时/坏JSON/setup错误、类型传输测试；新旧两个真实venv必须跑，不能只mock。其他缺包门槛预期红。
不改conftest/公共文件/gates/docs/CLAUDE.md/tools/orch/旧代码，禁止LLM打标签或API调用。不要清理.orch/tmp、不碰worktree外文件、不装依赖，拒绝操作不能绕过。当前分支提交后写.orch/report.md（文件、命令退出码及末20行、偏差、未决问题），不tag/merge/rebase/push/switch/删分支。缺前置/说明矛盾报告停下。
