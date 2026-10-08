角色：执行者

# s03-local 第2轮（最后）返工：E字符串的引用边界

第1轮De Morgan/pair改动已预读认可。编排者在主门槛新增的SqlCase漏导入已经自行改为共用case()助手；那是编排者的错，你无需也不得改门槛。

新增真实反例（SQL内的反斜线每处一个）：

```sql
SELECT E'abc\' CASE WHEN b IS NOT NULL THEN b ELSE 0 END \'xyz' FROM t
```

setup t(b INT)=(1),(NULL)。DuckDB和DataFusion都返回两行同一字符串 `abc' CASE WHEN b IS NOT NULL THEN b ELSE 0 END 'xyz`。当前apply_rule(case_to_coalesce)把字符串内的CASE改成COALESCE，两个改写仍成功但字符串内容改变，judge假fail/wrong_result。

修tokenizer对E转义字符串边界的识别，确保字符串内文本绝不被当成SQL；也检查同类U&前缀、转义引号、美元引号/带引用标识符的边界。可保守拒绝不支持的引号形式（返回None/not_applicable），不需要扩大方言支持，不引入新依赖。不允许只针对此固定文本特判。same_statement也不能把字符串内部case/空白变化当成相同pair。

新增真正区分改写前后语义的测试，两个真实引擎跑原查询并确认字符串内容、apply_rule None、label invalid/not_applicable；保留第1轮和所有原有断言。已在主检出区gates/s03.py补此反例并确认当前代码失败，编排者会独立复跑新版门槛。

允许路径/禁区/scope不变。复跑pytest、原local/S02门槛，提交，更新report。不改门槛/docs/公共文件/旧代码/conftest、不加skip/xfail。此为最后一轮，缺前提或说明矛盾就报告停下。
