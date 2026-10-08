# s03-registry 第1轮审查：返工

实现接口与范围基本符合；本次只修测试的长期有效性，不扩大实现范围，不改门槛。

1. framework/tests/test_surprise_s03_registry.py 的 test_missing_later_module_is_not_a_pass 和 test_evaluate_accounts_datafusion_and_missing_handler 直接假定 index_presence/equivalent_query/cross_dbms 文件不存在。后三包合并后这两个测试会失败，这不是合法的持续回归测试。
2. 为这两个测试使用 pytest monkeypatch 夹具：在测试内复制 registry._HANDLERS 与 _LAZY_MODULES，把欲验证的 later ID 从复制的 handler 字典中移除，将该ID的lazy模块改成明确不存在的测试专用模块名。由monkeypatch在退出时恢复。这样始终模拟缺模块，不依赖实际文件缺失。
3. 所有已有断言保留：缺模块必须抛ImportError/ModuleNotFoundError，evaluate仍必须写一条invalid/harness_error且记录异常；LIMIT的nondeterministic提前筛查断言保留。不要增加skip/xfail、不要删断言、不要用分支避开模块已实现的情况。
4. 补验证：在registry._HANDLERS里临时给later ID塞一个假的成功handler，再让上述缺模块测试的隔离逻辑仍能覆盖导入失败；或者通过同类模拟证明其不依赖仓库中该文件是否存在。不得创建实际后三包的实现文件。
5. 原测试已独立复跑，S03 registry组通过。全部门槛中local/cross/version/matrix缺后续模块的失败是此阶段预期，不改它们。

修完同样跑pytest、S03 --only registry、S02，提交当前分支并更新.orch/report.md。不要清理.orch/tmp。
