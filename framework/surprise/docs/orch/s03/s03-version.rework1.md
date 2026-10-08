角色：执行者

# s03-version 第1轮返工：类型兼容、证据稳定、协议与错误标签

独立pytest216 passed/3 skipped，S01/S02及原version组通过。编排者已读3个文件和全部26条shell命令；主检出区增强version组失败，不能合并。以下各项均在本包允许路径内解决，不改任何旧代码、公共文件、cross/local、gates或docs。

1. 本机DF50/54实测同一查询的原始类型和值一致：SELECT DATE '2020-01-02' AS d（date）、SELECT arrow_cast('hi','Binary') AS b（bytes）、SELECT CAST(1.25 AS DECIMAL(10,2)) AS n（Decimal）。当前旧结果走normalize_rows、新结果经过DataFusionRunner._norm，日期temporal前缀对ISO导致假fail/regression，bytes前缀对0x导致假invalid。新旧必须采用与同一目标runner兼容的主进程归一化，以上三项judge必须pass。可以在主进程调用既有targets.datafusion_runner._norm再共享normalize，不能改旧源文件、不能靠识别日期字符串来猜原始类型。worker仍传原始typed JSON，旧DF路径只直接导入datafusion和标准库。新增端到端类型label测试，不能只测_query_old解码；仅修改你新写的DF类型期望为正确兼容格式，原Duck类型测试保留。
2. old_rows/new_rows写进证据前按bag语义规范排序，保留重复行、NULL及值类型。当前同一SELECT a,b FROM t以真实DuckDBRunner包装器交替返回正序/逆序，相同bag两次都是pass，但to_dict不同。门槛会验证factory确实被调用及标签完全稳定。不能改Oracle比较为按行序、不能丢原始行字段。
3. _same_outcome把双方任意查询错误当成pass，这是不满足SQL执行前提。“双方都错仍pass”指两边成功返回同一错误bag，不指双方Binder/Parser错误。SELECT missing FROM t当前假pass，应invalid/query_error；双方值依赖错误invalid/value_dependent_error。真实的新旧结果一样且成功仍pass，包括同一错误结果；保留该测试。允许把你新增的test_both_engines_erroring_is_a_pass改为invalid断言（保留不调用参照/见证、cve为空等有效断言），这是PI澄清原brief的歧义，不是放宽门槛。
4. _query_old必须检查子进程returncode、要求成功/查询错误响应有非空的真实engine_version。当前真实成功JSON改returncode=7或删除engine_version仍pass。两项必须invalid/harness_error，不采信失败进程的成功rows，也不回退成主环境版本。保持缺解释器/坏JSON/setup错误/timeout现有无敏感输出处理。对损坏的typed cell（例如decimal无效文本）应返回protocol invalid，不泄漏异常或误判pass；不要从带垃圾的stdout里捞最后一个成功对象。
5. 只跳过确实未实现的index_presence模块。当前catch任意ModuleNotFoundError会吞index模块其它依赖缺失；应校验exc.name为完整可选模块名，其它见证运行错误传播给evaluate的harness_error记录。模拟缺模块的测试必须设置准确name并保留；加其它依赖缺失不被吞的反例，不依赖local模块长期不存在。
6. direction_evidence.witnesses请保存完整Label.to_dict（可保留原flat核心字段并另加label字段）；目前只摘身份核心，没有见证的detail/改写SQL。保持独立见证身份在版本标签/证据中，不能拿版本差异本身做见证，不能把旧崩溃本身当新回归。

主检出区gates/s03.py已加入经实测的类型/行序/双方错误/退出码/缺版本反例。根命令`.venv/Scripts/python.exe .orch/scratch/s3_root_gate.py s03-version --only version`供PI独立复核，你worktree门槛仍冻结在原基线，不许改。旧Cross的DATE归一化假候选已经登记HANDOFF给S4，属于计划外，不派给你，不改cross或旧normalizer。

流程提醒：日志中一次递归删除.orch/tmp/empty-cwd被deny，后来取消递归部分只删除单文件；该目录必须继续保留。返工中完全不清理既有tmp资料/目录，不再尝试目录删除、不换写法绕过。报告说明被拒及后续处理，不要再为了收尾清理探测文件。

复跑pytest、原version/S02门槛，新增反例测试，提交当前分支并更新report；不merge/rebase/tag/切分支，不改外部服务或依赖环境。允许路径仍仅3个文件，缺前提或与PLAN冲突报告停下。
