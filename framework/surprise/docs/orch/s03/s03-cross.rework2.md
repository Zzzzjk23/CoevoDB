角色：执行者

# s03-cross 第2轮（最后）返工：WITH起头的SELECT INTO

独立pytest186 passed/3 skipped、多语句增强cross组通过；完整返工diff和累计22条shell命令核对，第一轮修正认可。

还剩一个同范围缺口：is_readonly_query('WITH x AS (SELECT 1 AS a) SELECT a INTO z FROM x') 返回True，因为INTO只在head == SELECT下被拒绝。该语句会建表，必须在runner/cross执行前拒绝。编排者已把该断言加入主检出区gates/s03.py并实测当前HEAD失败。

保守对所有允许head检查代码中的INTO即可；字符串/引用标识符/注释里的INTO不能错拒。请补无DB记录runner确认不会执行，以及真实PG正常WITH与引用INTO文本的测试，勿真的运行SELECT INTO反例。保留原有门槛/断言，不加skip/xfail。

允许路径、scope和禁区均不变。复跑pytest、旧cross和S02门槛，提交，更新report。编排者会用根.orch/scratch/s3_root_gate.py独立复跑当前门槛。此为第2轮，若缺前提或矛盾报告停下，不扩范围。
