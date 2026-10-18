## CLAUDE.md（提议）

1. 文档列表：
   - `SESSIONS.md`：12 个实施会话的范围、交付物与门槛
   + `SESSIONS.md`：实施会话的范围、交付物与门槛（S0–S12 迁移，S13 起正式实验）
   + `EXPERIMENT.md`：正式实验协议
   + `SERVER.md`：实验服务器的环境、部署与运行手册

2. 不可违反，新加一条：
   + 实验服务器（`ssh 3090`）专用：编排者直接部署（只推 tag，服务器工作目录只检出 tag、不在上面改代码），并照运行单在上面起实验，次序按 `SESSIONS.md`；不跑计划外的实验，不动正在跑的格。密钥经 ssh 标准输入进 tmux 会话的环境，不进命令行、文件与日志。grok 不登录服务器。

3. 命令，"引擎环境"之后加一条：
   + 服务器上的环境版本与 Windows 相同，路径见 `framework/surprise/docs/SERVER.md`；解释器是 `~/CoevoDB/.venv/bin/python`，部署见 SERVER.md §3。

4. 执行者模式，加一条：
   + 不登录、不连接实验服务器（不用 ssh、scp、rsync、sftp）。

## ORCHESTRATION.md（提议）

1. §1 表格"执行者"的"不做"一列末尾加：不登录实验服务器。
2. 新加 §11"实验服务器"：
   - 服务器专用（2026-10-19 用户决定，PLAN §9 补充一条）：你直接部署，并照运行单起实验，次序按 SESSIONS；
   - 部署只推 tag（`git push server refs/tags/<tag>`），服务器工作目录只检出 tag，不在上面改代码；
   - grok 不登录服务器：deny 规则看不到 ssh 引号里的远程命令，服务器上的操作也不留 diff 可审；需要在服务器上做的事由你做，需要改的代码照旧由 grok 在本机 worktree 里改；
   - 环境与运行手册见 `SERVER.md`。

## tools/orch/grok_worker.py（提议）

DENY_BASH 加 `ssh`、`scp`、`rsync`、`sftp`，把"grok 不登录服务器"从说明里的规定变成会被拦下的写法（与 ORCHESTRATION §10 一样，包一层的写法拦不住，靠审查）。
