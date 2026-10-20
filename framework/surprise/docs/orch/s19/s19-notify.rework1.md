# 审查意见 · s19-notify · 第 1 轮

总体：改动范围、发送器、gateway 那一行、分类、余额、每日上限、只读、PID 检查都对，测试隔离做得好（autouse 去掉两个变量并拦截 httpx）。下面三处要返工，都在 `framework/surprise/notify/watch.py`，并给每一处加测试（`framework/tests/test_surprise_s19_notify.py`）。允许改动的路径与禁止事项照原说明不变。

## 1. 停滞判断漏掉子目录里的文件，SQLancer 格会误报（必须改）

编排者在服务器上只读核对了预实验 c8 的 SQLancer 格（`results/e1-pilot-c8/cells/sqlancer/s9101-r0`）：2 小时里 `progress.jsonl` 是 0 行，格日志 `s9101-r0.log` 只有 23 字节；一直在写的只有 `sqlancer/stdout.txt`（SQLancer 每 5 秒打一行进度，2 小时 126,938 行）。按现在的规则（格目录下直接的文件、`llm/` 下的文件、格日志），每个 SQLancer 格开跑 30 分钟后都会报一次 `stall`。

改为：最近活动取**格目录整棵树里所有文件**（任意深度）与格日志的 mtime 最大值。格目录不大（预实验 2 小时的 `full` 格 57 个文件，S8 的 3 小时长跑 137 个），每分钟遍历一次没问题。这一条修正了原说明里"格目录下直接的文件、`llm/` 下的文件"的写法，以这里为准。

测试：一个只有 `sqlancer/stdout.txt` 在更新、其余文件都旧的格不报 `stall`；整棵树都旧时照样报。

## 2. 文件在列出与 `stat` 之间消失时，看守会崩（必须改）

`_stall` 先 `iterdir()` 再 `path.is_file()`、`path.stat()`。SQLite 的日志文件（`ledger.sqlite-journal` 之类）不断地建了又删，`is_file()` 与 `stat()` 之间文件没了就抛 `FileNotFoundError`，`run` 随之退出。格目录本身也可能在两次调用之间不见（网格把旧格改名为 `.stale-<k>`）。

改为：遍历与取 mtime 时，消失的文件跳过，消失的目录当作没有活动，都不抛异常。

测试：用 monkeypatch 让某个文件在列出之后 `stat` 抛 `FileNotFoundError`，`poll` 照常返回；格目录在 `snapshot` 之后被删，`poll` 不抛。

## 3. 一次轮询抛异常就结束看守（必须改）

看守要连跑好几天，一旦死掉就再也没有提醒，用户也不会知道。`run` 里 `poll()` 抛出的任何异常都不能结束循环：
- 打印一行（异常类名与消息，经 `_safe_text` 去掉密钥），继续按间隔轮询；
- 连续 3 次轮询失败时，经 `notifier` 发一条标题为 `[CoevoDB] 看守出错` 的消息，正文写 `OUT`、异常类名与消息（去密钥）；同一段连续失败只发这一次，有一次轮询成功就重新可发；这条消息也计入每日上限；
- `notifier.send` 本身失败或抛异常照旧不影响看守。

`poll()` 本身的行为不变（门槛直接调它）。只在 `run` 这一层接住，不要在 `poll` 里面加宽泛的 try/except。

测试：`run` 用一个前几次 `poll` 抛异常、之后正常并最终 `finished` 的看守，确认 `run` 返回 0、出错消息只发了一次、打印里没有密钥。可以把 `time.sleep` monkeypatch 掉。

## 验收

同原说明：`pytest -q testing tests`（在 1142 passed, 3 skipped 上只增不减）、`python -m surprise.gates.s19`（11/11）、`s09`、`s10`、`s15 --only config llm prices`。提交到当前分支，更新 `.orch/report.md`（追加"第 2 轮"一节，格式同前）。
