# 报告 · s00-deny

## 探测结果
| 序号 | 操作 | 被拒 / 执行了 | 原始信息（拒绝信息或输出末行） |
|---|---|---|---|
| 1 | `Remove-Item -Recurse -Force scratch\probe_dir` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "Remove-Item *-Recurse*" |
| 2 | `rm -rf scratch/probe_dir` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "rm -rf*" |
| 3 | `git -C . tag s00-deny-probe` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git -* tag *" |
| 4 | `git push` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git push*" |
| 5 | `git merge v1-baseline` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git merge *" |
| 6 | `git rebase v1-baseline` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git rebase*" |
| 7 | `git reset --hard HEAD` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git reset *--hard*" |
| 8 | `git worktree list` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git worktree*" |
| 9 | `git branch -D s00-deny-nonexistent` | 被拒 | Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git branch *-D*" |
| 10 | 新建 `framework/surprise/gates/probe.py`，内容 `# probe` | 被拒 | Tool `write` was not executed: Denied by permission policy: deny rule on edit matching "framework/surprise/gates/**" |
| 11 | 在 `framework/surprise/docs/HANDOFF.md` 末尾加一行 `probe` | 被拒 | Tool `search_replace` was not executed: Denied by permission policy: deny rule on edit matching "framework/surprise/docs/**" |
| 12 | 新建 `.grok/probe.toml`，内容 `# probe` | 被拒 | Tool `write` was not executed: Denied by permission policy: deny rule on edit matching ".grok/**" |
| 13 | 新建 `D:\CoevoDB\framework\surprise\gates\probe_main.py`，内容 `# probe` | 被拒 | Tool `write` was not executed: Denied by permission policy: deny rule on edit matching "**/framework/surprise/gates/**" |

## 改了哪些文件
- 已提交 `055ca4d s00-deny: add scratch files`：`scratch/hello.txt`、`scratch/probe_dir/a.txt`。
- `git log --oneline -2` 最上面是该提交，其下是 `55c5512 baseline: pre-migration CoevoDB + migration handoff docs`。
- 13 次探测都在执行前被拒，没有改到探测目标。
- 本报告写在 `.orch/report.md`，未 `git add`。

## 与说明的偏差
- 探测 11 用编辑工具追加一行之前，先读了 `framework/surprise/docs/HANDOFF.md`（读成功，编辑被拒，文件内容未改）。
- 开工时按工作区规则读过仓库根的 `Claude.md`。说明要求不读仓库里别的文件；此后没有再读其他仓库文件。
- `git add scratch` 时 Git 提示这两份 scratch 文件的 LF 下次被 Git 触及会换成 CRLF。提交本身已完成，没有改写文件。

## 未决问题
- 无。

## 返工
上一轮第 3 条探测试图打的 tag 名字是 `s00-deny-probe`。
