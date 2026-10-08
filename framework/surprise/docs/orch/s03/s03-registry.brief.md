角色：执行者

# 工作包 s03-registry：共享注册分发与两引擎基础适配

你在自己的 worktree、分支 grok/s03-registry 上实现本包。基线 session/s03（0790d4c），会话 S3。只改下列路径，旧代码一律只调用、不改。

```allow-paths
framework/surprise/harness/oracles/__init__.py
framework/surprise/harness/oracles/registry.py
framework/surprise/harness/oracles/sound.py
framework/surprise/harness/evaluate.py
framework/surprise/harness/contracts.py
framework/surprise/harness/manifest.py
framework/tests/test_surprise_oracles.py
framework/tests/test_surprise_evaluate.py
framework/tests/test_surprise_contracts.py
framework/tests/test_surprise_s03_registry.py
```

## 目标与共享接口（后续三包依赖，必须照此提供）

遵守 PLAN.md 第3节七类 oracle 表与第4节契约。只实现共享分发及 S2 三类接 DataFusion，不实现另外四类 oracle，不实现 CVE。

1. 新增 registry.py：register(oracle_id, handler)、get_handler(oracle_id)、runner_factory_for(engine)。get_handler 懒加载四个后续模块 index_presence/equivalent_query/cross_dbms/version_differential 中的 judge_case 并注册，后续包无需改 __init__.py。未知 ID 抛 ValueError，缺实现模块不可伪装成通过；已登记处理器不能被意外覆盖。
2. registry.OracleOptions 定义字段 rewrite_rule=None、paired_query=None、old_python=None、reference_factories=None；后三包处理器统一签名 judge_case(case, *, factory, timeout_s, options) -> Label。factory 是目标引擎 runner 工厂。reference_factories 为 engine_id -> callable 的参照映射（只有 duckdb/datafusion/sqlite/postgres，目标 ID 不允许再出现在参照里，版本别名也不允许）。None 表示默认参照，空 dict 表示没有参照。
3. judge(case, oracle, *, runner_factory=None, timeout_s=QUERY_TIMEOUT_S, rewrite_rule=None, paired_query=None, old_python=None, reference_factories=None) -> Label；IMPLEMENTED 使用 PLAN 已定七个 ID 的元组。engine 仅支持目标 duckdb/datafusion。现有三类保持 S2 的 setup→确定性→前提→旧 oracle 流程及原标签/身份证据不变。公共筛查在四个新处理器之前完成；OracleOptions 和未知 engine/oracle 在执行前校验。
4. sound.py 包装原 TLP/NoREC/Plan variant 适配器为上述注册 handler 签名。只调用既有适配器，旧模块与既有 tlp/norec/plan_variant/forms/common 文件不改。runner_factory_for 映射到旧 DuckDBRunner/DataFusionRunner。DataFusion 的基础 pass 已由编排者实测。含 LIMIT/随机等原有筛查对七类同样保守生效。
5. evaluate 接受并转发相同四个可选参数；保留执行前参数校验、每次执行恰好一条记录，别把调用者参数错误吞为 harness_error。旧调用完全兼容。若 handler 内异常，仍记录 harness_error。
6. INVALID_REASONS 原七项不删不改，按顺序追加 untrusted_rewrite、direction_unknown、insufficient_engines、non_unique_outlier。标签仍只有 pass/fail/invalid，不适用仍 invalid/not_applicable。
7. manifest 新增会影响 S3 判定的旧依赖到 HASHED_PATHS：targets/datafusion_runner.py、targets/sqlite_runner.py、oracles/equivalence.py、oracles/index_variant.py、oracles/cross_engine.py、oracles/differential.py、oracles/_remote_exec.py、scripts/cross_engine.py（保留原范围和 CRLF 规则）。新 harness 文件本来由 glob 自动覆盖。不改变冻结数值常数。

## 测试需求变更的明确授权

S2 原 test_judge_rejects_unknown_oracle_and_engine_and_is_stable 的 index_presence 尚未实现、datafusion 尚未支持两个前提已被 S3 需求推翻。本包定向更新为：保留未知 oracle/不支持目标（如 sqlite）拒绝断言，新增 DataFusion TLP pass、稳定性和错误路径断言；index_presence 的实际支持由后续 local 包测试，本包不可假实现。test_surprise_contracts.py 对 INVALID_REASONS 的精确元组期待需按新增四项更新，不能改成宽松子集。这是明确需求变化，不得删其他断言或改成 skip/xfail。其他老测试必须全部保留通过。

## 验收

在 worktree 中直接用 python（已经是项目解释器），PowerShell 5.1 无 &&：

```powershell
cd framework
python -m pytest -q testing tests
python -m surprise.gates.s03 --only registry
python -m surprise.gates.s02
```

通过数不少于149，原3个skip不增加。all 的 S3 其他组此时缺后续包，预期红，不改门槛。新增有意义的注册、验证先于执行、DataFusion setup错误/不适用、evaluate 记账测试。

## 禁止与收尾

不改 gates/、docs/、CLAUDE.md、.grok/、tools/orch/、conftest。不调用任何 LLM（你作为执行者编码除外），不使用 DeepSeek。不要清理 .orch/tmp，不碰 worktree 外文件，不装包。被拒操作不能换写法绕过。
不 tag、merge、rebase、push、switch、删分支。实现提交到当前分支后写 .orch/report.md：改动文件、每条命令退出码及末20行、偏差、未决问题。报告不入库。缺前置或说明矛盾就报告停下。
