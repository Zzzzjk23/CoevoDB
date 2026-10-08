# 接着做完 · s02-manifest

上一轮不是你出了问题：编排者查看状态时用错了一个参数，把这个包提前终止了。当时你还在分析阶段，分支上没有提交，worktree 里也没有未提交的文件。

请接着把 `.orch/brief.md` 里的工作包做完，要求一条都没有变：

- 交付 `framework/surprise/harness/manifest.py` 和 `framework/tests/test_surprise_manifest.py`，接口、哈希算法、命令行的退出码与输出都按说明写的来。
- 验收命令照说明里的那一组跑，全部通过。
- 提交到当前分支，写 `.orch/report.md`。
- 不要清理 `.orch/tmp`。

你上一轮已经读过的文件和得出的结论可以直接用，不必重读。
