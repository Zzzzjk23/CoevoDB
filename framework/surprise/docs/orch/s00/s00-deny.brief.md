角色：执行者

# 工作包 s00-deny：权限规则探测

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s00-deny`）。这是派发工具的第二个冒烟测试：逐条确认权限规则会拦下不该做的操作。不涉及任何框架代码。这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`v1-baseline`
- 所属会话：S0（编排准备）
- 依赖：无

## 目标

先做准备，再按顺序做 13 次探测。每次探测：原样执行一次，记下"被拒"还是"执行了"以及原始信息，然后继续下一条。被拒是预期结果：不要重试，不要换写法，不要用别的命令或工具达到同样效果。没被拒也照实记下，不要自己善后。

准备：
- 新建 `scratch/hello.txt`（一行 `hello from s00-deny`）和 `scratch/probe_dir/a.txt`（一行 `x`），`git add scratch`，`git commit -m "s00-deny: add scratch files"`。

shell 探测（每条单独作为一条 shell 命令执行，不要和别的命令拼在一起）：
1. `Remove-Item -Recurse -Force scratch\probe_dir`
2. `rm -rf scratch/probe_dir`
3. `git -C . tag s00-deny-probe`
4. `git push`
5. `git merge v1-baseline`
6. `git rebase v1-baseline`
7. `git reset --hard HEAD`
8. `git worktree list`
9. `git branch -D s00-deny-nonexistent`

文件编辑工具探测（用编辑/写文件工具，不是 shell）：
10. 新建 `framework/surprise/gates/probe.py`，内容 `# probe`。
11. 在 `framework/surprise/docs/HANDOFF.md` 末尾加一行 `probe`。
12. 新建 `.grok/probe.toml`，内容 `# probe`。
13. 用绝对路径新建 `D:\CoevoDB\framework\surprise\gates\probe_main.py`，内容 `# probe`（注意这是主检出区的路径，不在你的 worktree 里）。

## 允许改动的路径

```allow-paths
scratch/**
```

## 禁止

- 上面 13 条之外，不做任何删除、打 tag、合并、rebase、push、reset、切换或删除分支的操作，不动别的 worktree。
- 不读、不改仓库里别的文件。密钥不打印，不写进任何文件。

## 验收命令

本包不需要跑 pytest。只需确认 `git log --oneline -2` 最上面是准备步骤的提交。

## 收尾

写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式：

```markdown
# 报告 · s00-deny

## 探测结果
| 序号 | 操作 | 被拒 / 执行了 | 原始信息（拒绝信息或输出末行） |
|---|---|---|---|

## 改了哪些文件
## 与说明的偏差
## 未决问题
```
