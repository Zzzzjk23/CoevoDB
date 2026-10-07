角色：执行者

# 工作包 s00-smoke：编排冒烟

你是 CoevoDB 改造的执行者，在自己的 git worktree 里工作（当前目录就是 worktree 根，分支 `grok/s00-smoke`）。这是派发工具的冒烟测试，不涉及任何框架代码。这份说明与仓库里的 CLAUDE.md 冲突时，以这份说明为准。

## 基线

- 分支起点：`v1-baseline`
- 所属会话：S0（编排准备）
- 依赖：无

## 目标

按顺序做下面 5 步。每一步都要真的执行一次，不要跳过，不要多做，也不要读或改仓库里别的文件。

1. 新建 `scratch/hello.txt`，内容只有一行：`hello from s00-smoke`。
2. 执行 `git add scratch/hello.txt`，再执行 `git commit -m "s00-smoke: add scratch/hello.txt"`。
3. 执行一次 `git tag s00-smoke-probe`。这一步预期会被权限规则拒绝：被拒就把拒绝信息原样记进报告，不要换写法重试（不要用 `git -C`，不要用别的命令达到同样效果）。如果它竟然成功了，也照实记下，不要自己删除这个 tag。
4. 运行一条 shell 命令，判断环境变量 `DEEPSEEK_API_KEY` 在你的 shell 里是否存在。只报告"存在"或"不存在"，绝不打印它的值。再报告：你的 shell 是哪一种（bash / PowerShell / cmd）、`python --version` 的输出、`python` 可执行文件的路径。
5. 用文件编辑工具（不是 shell）在 `CLAUDE.md` 末尾加一行 `smoke`。这一步预期也会被拒绝：被拒就把拒绝信息原样记进报告，不要改用 shell 写文件。

## 允许改动的路径

```allow-paths
scratch/**
```

## 禁止

- 不改 `framework/surprise/gates/`、`framework/surprise/docs/`、`CLAUDE.md`、`.grok/`、`tools/orch/`（第 5 步只是为了确认它会被拒）。
- 不打 tag（第 3 步只是为了确认它会被拒），不合并，不 rebase，不 push，不切换或删除分支，不动别的 worktree。
- 密钥不打印，不写进任何文件。

## 验收命令

本包不需要跑 pytest。只需确认：

```bash
git status --short        # 干净
git log --oneline -2      # 最上面是第 2 步的提交
```

## 收尾

写 `.orch/report.md`（这个目录不入库，不要 `git add`），格式：

```markdown
# 报告 · s00-smoke

## 改了哪些文件
## 跑了哪些命令
每条命令给出：命令本身、退出码或是否被拒、输出的最后 20 行。
## 第 3 步（git tag）的结果
被拒 / 成功，附原始信息。
## 第 4 步的结果
DEEPSEEK_API_KEY：存在 / 不存在；shell 类型；python 版本与路径。
## 第 5 步（编辑 CLAUDE.md）的结果
被拒 / 成功，附原始信息。
## 与说明的偏差
## 未决问题
```
