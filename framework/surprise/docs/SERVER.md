# SERVER · 实验服务器

2026-10-19 由 S14 建立。正式实验在这台服务器上跑（`EXPERIMENT.md` §7）。第 1–4 节是环境与部署，写给编排者；第 5 节是运行手册，写给用户；第 7 节是门槛 `gates/s14.py` 读取的机读版本表。

分工：实验由用户自己 ssh 上服务器跑。Claude 只在搭环境（S14）与部署新引擎（S16–S18）时动服务器，而且要用户先确认服务器空闲。执行者（grok，2026-10-19 起暂用 codex）不登录服务器。（2026-10-19 用户改定，见 PLAN §9 补充一条：服务器专用，Claude 直接部署、不必先问是否空闲，实验也由 Claude 照运行单起，次序按 SESSIONS；执行者仍不登录服务器。第 5 节的命令谁来敲都一样。）

## 1. 主机与布局

- 主机：ssh 别名 `3090`（`~/.ssh/config` 里 HostName 129.94.175.154，经 UNSW 跳板 `login.cse.unsw.edu.au`），用户 `junkezhang`，免密钥。Ubuntu 24.04.4，Xeon Gold 5315Y（8 个物理核、16 线程），62 GB 内存，根分区可用约 308 GB。
- 这是多人共用的机器（2026-10-19 另有 `jws`、`user` 两个账号登录着），我们没有 sudo。所以所有东西都装在用户目录里，不装系统包，不注册系统服务。
- 代码：裸仓库 `~/coevodb.git`；工作目录 `~/CoevoDB` 是它的克隆，只检出 tag（分离头指针），不在上面改代码。
- 仓库外、不入库的东西都在 `~/CoevoDB` 下，路径与 Windows 本机一致（代码按 git 公共目录找 `.venvs`）：

| 路径（相对 `~/CoevoDB`） | 内容 |
|---|---|
| `.venv` | 主环境：DuckDB 1.5.5、DataFusion 54.0.0 等，见 §2 |
| `.venvs/duckdb-1.1.3` | 旧版 DuckDB（Version differential 子进程） |
| `.venvs/duckdb-1.1.3-full` | 在 DuckDB 1.1.3 上跑整个新框架（S8 召回、E4） |
| `.venvs/datafusion-50.0.0` | 旧版 DataFusion（Version differential 子进程），只有 datafusion 与 pyarrow |
| `.orch/mamba/` | micromamba 与两个 conda-forge 环境：`envs/py313`（Python 底座）、`envs/pgdeps`（编 PG 用的 ICU 67.1、readline、zlib） |
| `.orch/sqlite-3.51.0/` | 按 Windows 编译选项自编的 SQLite 3.51.0（`lib/libsqlite3.so.3.51.0`） |
| `.orch/pg16/` | PostgreSQL 16.15：`pgsql/`（安装）、`data/`、`sock/`、`server.log` |
| `.orch/jdk/jdk-21.0.12.1+1/` | Temurin JDK 21（S15 的 SQLancer 用） |
| `.orch/sqlancer/` | SQLancer `ab328b75` 加一个补丁的构建，DuckDB JDBC 换成 1.5.5.0（S15，见 §8） |
| `.orch/dl/` | 下载的源码包与构建日志 |
| `.src/duckdb-v1.5.5`、`.src/datafusion-54.0.0` | 引擎源码浅克隆，提交号与 Windows 相同（S9 门槛钉住） |
| `framework/results/s08/` | S8 钉住的四个产物目录（`pre`、`longrun`、`old_no_llm`、`recall113`），从 Windows 拷来，逐字节相同 |

- uv 在 `~/.local/bin/uv`（0.13.1），没有加进 PATH。

## 2. 环境版本

| 项 | 版本 | 怎么来的 |
|---|---|---|
| Python | 3.13.9（conda-forge 构建） | micromamba 建 `envs/py313`；四个 venv 都由 uv 以它为底座建立，不继承底座的包 |
| SQLite（标准库 `sqlite3`） | 3.51.0，`sqlite_source_id()` 与 Windows 逐字相同 | 见下文 |
| DuckDB | 1.5.5；旧版 1.1.3 | PyPI |
| DataFusion | 54.0.0；旧版 50.0.0 | PyPI |
| PostgreSQL | 16.15，ICU 67.1 | 官方源码包（SHA256 已核对）自编 |
| JDK | Temurin 21.0.12.1+1 | Adoptium 官方 tar 包（SHA256 已核对） |
| SQLancer | `ab328b756bf5d923b9d93959af3432546efe56fd` 加 `docs/sqlancer/log-each-select.patch`；DuckDB JDBC 1.5.5.0 | 在 Windows 上用 Maven 3.9.16 构建，整个目录拷来（§8） |

各 venv 的包（`uv pip freeze` 的直接依赖部分，版本照 Windows 本机）：

- `.venv` 与 `.venvs/duckdb-1.1.3-full`：代码直接用到的是 duckdb、datafusion 54.0.0、psycopg2-binary 2.9.13、sqlglot 30.21.0、pyyaml 6.0.3、pytest 9.1.1、matplotlib 3.10.6、scipy 1.16.3、numpy 2.3.5、pyarrow 21.0.0、httpx 0.28.1。Windows 的这两个 venv 继承 anaconda 底座的包（matplotlib、scipy、numpy、pyarrow、httpx 及其依赖来自那里）；服务器上的 venv 不继承底座，把这些包连同间接依赖（pyparsing、pillow、fonttools 等）直接装进去，版本逐个照 Windows 上那个 venv 实际看到的版本钉住（两个 venv 的间接依赖版本略有不同，例如 anyio、idna，各照各的）。完整列表是 §7 的 `venvs`。
- `.venvs/duckdb-1.1.3`：duckdb 1.1.3、psycopg2-binary 2.9.13。
- `.venvs/datafusion-50.0.0`：datafusion 50.0.0、pyarrow 25.0.1；不装 duckdb、psycopg2（与 Windows 相同，S1 修订的决定）。

**SQLite 为什么要自编。** Linux 上 Python 的 `sqlite3` 用它链接的那份库，版本与编译选项都会改变查询结果，而 SQLite 是 DuckDB、DataFusion 的 Cross-DBMS 参照，S17 起还是目标：

- uv 自带的 Python 3.13.9 内置 SQLite 3.50.4；系统库是 3.45.1；conda-forge 的 libsqlite 3.51.0 版本对了，但打过补丁（source id 带 `-experimental`），编译选项也多出 ICU、STAT4、数学函数、`percentile`、`LIKE_DOESNT_MATCH_BLOBS`、`MAX_EXPR_DEPTH=10000` 等十几项。例如 `select sqrt(4)` 在 Windows 上报 `no such function`，在 conda-forge 的库上返回 2.0，参照的投票就会不同。
- 所以从官方 amalgamation（`sqlite-amalgamation-3510000.zip`）按 Windows 那份库的编译选项重编，再把 `envs/py313/lib/libsqlite3.so.0` 指到它（conda 原来的文件留着没删）。结果：`sqlite_source_id()` 与 Windows 逐字相同；`pragma compile_options` 只差 `COMPILER`、`MUTEX_W32`/`MUTEX_PTHREADS`、`ATOMIC_INTRINSICS` 三项平台固有的。
- sqlite.org 现在只列最新版的哈希，3.51.0 的包没法按官方哈希核对，以 source id 相同为准。

**PostgreSQL 参照。** 与 Windows 那份（EDB 16.15）逐项比对过：UTF8 编码、`C` 排序与字符分类（libc 提供者）、`lc_*` 都是 `C`、时区 `Australia/Sydney`、`datestyle = 'iso, mdy'`、全文检索 `english`、ICU 排序版本 153.14（ICU 67）都相同，只有 `version()` 里的编译器字样不同。监听 `127.0.0.1:55432`，用户 `coevo`，harness 的默认 DSN 不用改。

与 Windows 的一处不同：Windows 本机对 127.0.0.1 用 trust 认证；这台机器多人共用，trust 会让别的账号以超级用户 `coevo` 连进来，再借 `COPY ... TO PROGRAM` 以我们的身份执行命令。所以这里用 `scram-sha-256`，密码只写在 `~/.pgpass`（权限 0600）里，libpq 自动读取，DSN 照旧不带密码；unix socket 放在私有目录 `.orch/pg16/sock`（0700）。用户 crontab 有一条 `@reboot`，服务器重启后自动启动 PG。

## 3. 部署新代码（编排者）

本机推送 tag，服务器只检出 tag：

```
# Windows 本机，仓库根
git push server refs/tags/<tag>

# 服务器
cd ~/CoevoDB
git fetch -q origin "refs/tags/<tag>:refs/tags/<tag>"
git -c advice.detachedHead=false checkout -q --detach <tag>
git status --short          # 必须为空
```

本机的远程 `server` 指向 `3090:coevodb.git`。服务器工作目录的 `origin` 是 `~/coevodb.git`。S14 期间部署用的中间 tag 叫 `s14-deploy-N`。

部署之后在服务器上记录一次，再拷回本机入库（也只在用户确认空闲时做）：

```
# 服务器
cd ~/CoevoDB/framework
../.venv/bin/python -m surprise.gates.s14 --record ~/s14-record   # 探针、pytest、全部门槛

# Windows 本机，仓库根
scp "3090:s14-record/*" framework/surprise/gates/s14_evidence/
```

门槛 s14 的 `linux` 组要求记录的提交与本机代码相同。打出 `s14-done` 之后，S14 的证据就不再改；后面的会话要验证服务器，把记录放进自己的证据目录。

## 4. 重建步骤

服务器要重装时照这里做（全部在用户目录，不需要 sudo）。路径都相对 `~/CoevoDB`。

1. uv：`curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh`。
2. micromamba：`mkdir -p .orch/mamba && cd .orch/mamba && curl -fsSL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba`。
3. Python 底座：`MAMBA_ROOT_PREFIX=$PWD/.orch/mamba .orch/mamba/bin/micromamba create -y -p .orch/mamba/envs/py313 -c conda-forge --override-channels python=3.13.9 libsqlite=3.51.0`。
4. SQLite：下载 `https://sqlite.org/2025/sqlite-amalgamation-3510000.zip`，解压后
   `gcc -O2 -fPIC -shared -DSQLITE_ENABLE_COLUMN_METADATA -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_GEOPOLY -DSQLITE_ENABLE_RTREE -DSQLITE_MAX_VARIABLE_NUMBER=250000 -DSQLITE_THREADSAFE=1 sqlite3.c -o .orch/sqlite-3.51.0/lib/libsqlite3.so.3.51.0 -Wl,-soname,libsqlite3.so.0 -lpthread -ldl -lm`，
   再 `ln -sfn` 把 `envs/py313/lib/libsqlite3.so.0` 与 `libsqlite3.so` 指过去。核对 `sqlite_source_id()` 是 `2025-11-04 19:38:17 fb2c931ae597f8d00a37574ff67aeed3eced4e5547f9120744ae4bfa8e74527b`。
5. venv：`uv venv --python .orch/mamba/envs/py313/bin/python3.13 <路径>`，再 `uv pip install --python <路径>/bin/python <§7 里该 venv 的全部 包==版本>`（值为 `null` 的不装）。
6. PG：`micromamba create -p .orch/mamba/envs/pgdeps -c conda-forge --override-channels icu=67.1 readline zlib`；官方源码包 `postgresql-16.15.tar.bz2`（SHA256 `c1575341fa7bd40f5274ea465b34390f4dc64cdd0770af327005caaeb9f6b7ed`）；`./configure --prefix=$HOME/CoevoDB/.orch/pg16/pgsql --with-icu --with-openssl --with-readline --with-zlib CPPFLAGS=-I<pgdeps>/include LDFLAGS="-L<pgdeps>/lib -Wl,-rpath,<pgdeps>/lib"`（`PKG_CONFIG_PATH=<pgdeps>/lib/pkgconfig`），`make -j16 world-bin && make install-world-bin`。initdb：`-U coevo --encoding=UTF8 --locale=C --auth=scram-sha-256 --pwfile=<临时文件>`，密码先写进 `~/.pgpass`（`127.0.0.1:55432:*:coevo:<密码>` 与 `localhost` 一行）；`postgresql.conf` 末尾加 `listen_addresses`、`port`、`unix_socket_directories`、`timezone`、`log_timezone`、`datestyle`、`default_text_search_config` 七行，取值见 §2。
7. JDK：Adoptium `OpenJDK21U-jdk_x64_linux_hotspot_21.0.12.1_1.tar.gz`（SHA256 `ce79869e1307ed8ee1e2baa86a412b1eb5b75d10a01006d788a6f968bcfaee94`）解压到 `.orch/jdk/`。
8. 源码：`git clone --depth 1 --branch v1.5.5 https://github.com/duckdb/duckdb .src/duckdb-v1.5.5`；`git clone --depth 1 --branch 54.0.0 https://github.com/apache/datafusion .src/datafusion-54.0.0`。
9. S8 产物：在 Windows 的 `framework/results/s08` 下 `tar -czf - pre longrun old_no_llm recall113 | ssh 3090 'tar -C ~/CoevoDB/framework/results/s08 -xzf -'`。
10. 核对：`cd framework && ../.venv/bin/python -m surprise.gates.s14 --only env`。

## 5. 运行手册（用户）

以下命令都在服务器上执行（先 `ssh 3090`）。`PY` 指主环境的解释器：

```
PY=~/CoevoDB/.venv/bin/python
```

### 5.1 开跑前检查

```
cd ~/CoevoDB
git describe --tags --exact-match          # 当前部署的 tag，应是运行单写的那个
git status --short                         # 必须为空
.orch/pg16/pgsql/bin/pg_ctl -D .orch/pg16/data status    # 应显示 server is running
df -h ~ | tail -1                          # 磁盘余量
uptime                                     # 负载；别人的进程占满 CPU 时先别开跑
tmux ls                                    # 有没有还在跑的网格
```

PG 没在跑时启动它（不要重新 initdb）：

```
~/CoevoDB/.orch/pg16/pgsql/bin/pg_ctl -D ~/CoevoDB/.orch/pg16/data -l ~/CoevoDB/.orch/pg16/server.log -w start
```

### 5.2 在 tmux 里启动网格

```
tmux new -s <名字>                          # 例如 s14-smoke
cd ~/CoevoDB/framework
$PY -m surprise.experiments.grid run <配置.json> --out results/<名字> 2>&1 | tee -a results/<名字>.log
```

按 `Ctrl-b` 再按 `d` 离开 tmux，网格继续跑；`tmux attach -t <名字>` 回来看。网格中途被打断（断电、误按 `Ctrl-c`）时，用同一条命令续跑：已经 `done` 的格不会重跑，没跑完的格改名成 `<格>.stale-<k>` 保留，再从头跑。`tee -a` 是追加，续跑时日志里前后两段都在。

不带 LLM 的格，子进程里没有密钥（网格从子进程环境里去掉 `DEEPSEEK_API_KEY`）。

密钥与 token 存在服务器上（2026-10-21，用户指示）：`~/.config/coevodb/llm.env` 导出 `DEEPSEEK_API_KEY`（现在是 OpenRouter 的密钥，73 个字符），`~/.config/coevodb/pushplus.env` 导出 `PUSHPLUS_TOKEN`（32 个字符）；文件 600、目录 700，只有本账号能读。`~/.bashrc` 末尾两行加载它们，所以新开的交互 shell 与 tmux 会话里都有这两个变量，不用再 `read -s`；在这之前开的 tmux 会话里没有，要新开或 `. ~/.bashrc`。核对只看长度：`echo ${#DEEPSEEK_API_KEY} ${#PUSHPLUS_TOKEN}`。不要把值写进 `~/.bashrc`（它是 644，同机的人都能读）、命令行参数或日志；不要 `cat` 这两个文件。换密钥时由编排者从本机的用户级环境变量经 ssh 标准输入重写对应文件。服务器上的 shell 都带着密钥，所以测试照 CLAUDE.md 只跑 `pytest -q testing tests`（`framework/test_api.py` 在有密钥时会真的发请求）。

提醒（`s19-notify`，2026-10-21；部署了含它的 tag 之后才有）：网格起来之后，在同一个 tmux 会话里开第二个窗口（`Ctrl-b c`）起看守。它只读 `results/<名字>`，每 60 秒查一次，有事就经 pushplus 推给用户；网格结束（每格都有 `cell.json`）或网格进程退出后自己停：

```
cd ~/CoevoDB/framework
$PY -m surprise.notify.watch results/<名字> --pid "$(pgrep -f -o 'surprise.experiments.grid run .*results/<名字>')" 2>&1 | tee -a results/<名字>.notify.log
```

推送的事件：开始看守（顺带确认推送通了）；某格连续 5 次 LLM 调用失败（标题写原因：402 额度不足、401/403 密钥、429 限流、超时）；调用上限用完；格失败（附日志末 3 行）；在跑的格 30 分钟没有任何文件活动；OpenRouter 的 key 剩余额度低于 $1 或用完（只有在 OpenRouter 给 key 设了额度上限时才查得到）；看守自己连续 3 次出错；网格结束或网格进程退出。同一次轮询的事件合成一条，一天最多 30 条。手动试推送：`$PY -m surprise.notify.pushplus "[CoevoDB] 测试" "来自 3090"`（退出码 0 是发出去了，2 是没有 token）。

### 5.3 查看状态

```
cd ~/CoevoDB/framework
$PY -m surprise.experiments.grid status results/<名字>
```

每格一行，末行是 `done X/Y`。某一格的进度在 `results/<名字>/<臂>/s<种子>-r<重复>/` 下。

### 5.4 生成报告

全部格 `done` 之后：

```
cd ~/CoevoDB/framework
$PY -m surprise.metrics.report results/<名字>
```

写到 `results/<名字>/report/`：`report.json` 与 7 张图。

### 5.5 压缩并拷回

服务器上：

```
cd ~/CoevoDB/framework/results
tar -czf ~/<名字>.tar.gz <名字> <名字>.log
```

Windows 本机（PowerShell）：

```
New-Item -ItemType Directory -Force D:\CoevoDB\framework\results\server | Out-Null
scp 3090:<名字>.tar.gz D:\CoevoDB\framework\results\server\
```

拷回并核对能解压之后，再删服务器上的原始目录（里程碑报告出完之前不要删；E1 的原始目录要留到 E3 与 S16–S18 的回放检查都用完，见 `EXPERIMENT.md` §5）。

### 5.6 S14 冒烟

S14 的门槛要求用户照本节跑通一次 1 分钟的冒烟网格。配置是 `framework/surprise/docs/grids/s14_smoke.json`（一个不带 LLM 的 `surprise` 臂与读汇总的 `sqlancer` 臂，种子 7，每格 1 分钟，约 2 分钟跑完）：

```
tmux new -s s14-smoke
PY=~/CoevoDB/.venv/bin/python
cd ~/CoevoDB/framework
$PY -m surprise.experiments.grid run surprise/docs/grids/s14_smoke.json --out results/s14-smoke 2>&1 | tee -a results/s14-smoke.log
$PY -m surprise.experiments.grid status results/s14-smoke
$PY -m surprise.metrics.report results/s14-smoke
cd ~/CoevoDB/framework/results && tar -czf ~/s14-smoke.tar.gz s14-smoke s14-smoke.log
```

跑完后可以 `exit` 退出 tmux。然后照 §5.5 在 Windows 上把 `s14-smoke.tar.gz` 拷到 `D:\CoevoDB\framework\results\server\`，告诉编排者；编排者解压后用 `python -m surprise.gates.s14 --ingest-smoke <解压出的 s14-smoke 目录>` 把门槛要读的部分放进 `framework/surprise/gates/s14_evidence/smoke/`。

### 5.7 并行网格

S15 起网格可以同时跑几格。网格配置的四个顶层键（都可以不写）：

| 键 | 含义 | 默认 |
|---|---|---|
| `concurrency` | 同时跑几格 | 1 |
| `cpus_per_cell` | 每格绑几个 CPU（Linux 上用 CPU 亲和性；各格互不重叠；`concurrency × cpus_per_cell` 不能超过可用 CPU 数） | 不绑 |
| `engine_threads` | 每格的引擎线程数（经环境变量 `SLURM_CPUS_ON_NODE` 交给 DuckDB） | 引擎自己定 |
| `kill_grace_minutes` | 墙钟强杀的宽限：一格跑到"预算 + 宽限"还没结束就被中断，再过 2 分钟还不结束就连同子进程一起杀掉 | 10 |

- 起格的次序按块：同一种子、同一引擎下的全部臂是一块，一块的格一起起跑（`EXPERIMENT.md` §5）。
- 正式实验的并发度由每个里程碑的预实验定（1、4、8 格比吞吐与标签稳定性），写进那个里程碑的配置，跑的过程中不改。
- 状态里被强杀的格显示 `done (killed)`：它的报告照常写完（状态 `interrupted`），不会重跑。
- 看负载：`uptime`；看每格的 CPU：`top -H` 或 `ps -eo pid,psr,pcpu,args | grep surprise`（`psr` 是所在的 CPU）。

### 5.8 归档

每个里程碑出完报告后，在服务器上打包、拷回本机、本机核对，再回服务器精简（只留报告与摘要）。**E1 的原始目录先不精简**：E3 的 A14 要它的理论存储，S16–S18 的回放检查要它的账本（`EXPERIMENT.md` §5）。

服务器上：

```
cd ~/CoevoDB/framework
$PY -m surprise.experiments.archive pack results/<名字> --dest ~/<名字>.tar.gz
```

会同时写 `~/<名字>.tar.gz.json`（每个文件的 SHA256 与整个包的 SHA256）。Windows 本机（PowerShell，仓库根）：

```
scp 3090:<名字>.tar.gz 3090:<名字>.tar.gz.json D:\CoevoDB\framework\results\server\
cd D:\CoevoDB\framework
..\.venv\Scripts\python.exe -m surprise.experiments.archive verify results\server\<名字>.tar.gz
```

`verify` 退出码 0 之后，回服务器精简（它会先拿归档核对一遍目录，对不上就什么都不删）：

```
cd ~/CoevoDB/framework
$PY -m surprise.experiments.archive prune results/<名字> --archive ~/<名字>.tar.gz
```

精简后留下 `grid.json`、`report/`，以及每格的 `cell.json`、`config.json`、`report.json`（有 `error.txt` 也留）；账本、理论存储、进度、日志都只在归档里。

## 6. 平台差异

S14 在服务器上第一次跑全量测试、全部门槛与冒烟网格时发现的差异，逐条记录。代码、门槛的改动都只为让同一件事在两个平台上得到同一个结果，没有放宽任何断言。

| # | 现象 | 原因 | 处理 |
|---|---|---|---|
| 1 | `test_pg_local_server.py::test_live_server_roundtrip` 与旧系统对照组（`old_no_llm`，也就是 `test_real_no_llm_is_killed_at_the_budget` 与 S12 门槛 `old_arm`）报 `PermissionError` | 旧代码的默认路径（`framework/util/paths.py` 的 `COEVO_PGBLD` 等五个、`framework/config.yml` 的 `old_venv`）指向原开发机的 `/home/user/work/db_safety/...`。这台服务器上恰好有另一个账号 `user`，目录存在但不可读，`Path.exists()` 抛异常而不是返回 False；Windows 上这些路径不存在，返回 False | 不改旧代码（S12 的 `moves` 组钉着它们与 `s11-done-r2` 只差导入路径）。`util/paths.py` 的文档本来就说"新克隆用环境变量覆盖"：`~/CoevoDB/.orch/server.env` 把五个变量指到 `~/CoevoDB/.orch/absent/` 下不存在的路径，与 Windows 上"路径不存在"的行为一致；`~/.bashrc` 第一行（在交互式判断之前）读入它，所以 ssh 远程命令、tmux 里的 shell 都有。门槛 s14 的 `env` 组核对这五个变量 |
| 2 | `test_surprise_s04_pipeline.py` 两个测试断言子进程退出码是 77 / 0，Linux 上得到 -9 | 测试夹具 `tests/test_surprise_s04_runners.py` 的 `die(code)`：Windows 上用 `TerminateProcess(code)`（S5 为避开 `os._exit` 的偶发访问冲突），POSIX 上写成了给自己发 SIGKILL，退出码恒为 -9。harness 如实报了 crash 与退出码 | 包 `s14-posix-die`：POSIX 分支改成 `os._exit(code)`（Linux 上 `exit_group` 立即结束所有线程，没有 Windows 那个问题）；断言不变 |
| 3 | 门槛 s03 的 `version` 组找不到 `.venvs/duckdb-1.1.3/Scripts/python.exe`；同组"旧 DataFusion 环境里没有 DuckDB"一项查的是 `Lib/site-packages/duckdb`，在 Linux 上恒真 | 门槛写死了 Windows 的 venv 布局 | 编排者改门槛：解释器按 `Scripts/python.exe`、`bin/python` 依次找；污染检查改为在整个 venv 里找 `site-packages/duckdb`，两个平台上都真的在查 |
| 4 | 门槛 s14 的 `smoke` 组判冒烟网格的 `grid.json` 与配置不符 | `load_config` 把 `sqlancer` 臂的汇总文件存成绝对路径：服务器上是 `/home/<用户>/CoevoDB/framework/...`，本机是 `D:\CoevoDB\framework\...` | 编排者改门槛：两边都截成工作目录内的相对路径再比，且只在两边指向同一个文件时才截；网格代码不动 |

## 7. 机读清单

门槛 `gates/s14.py` 的 `env` 组读下面这段 JSON：在服务器上逐项核对实际环境，在 Windows 上核对服务器留下的记录。

- `python`：四个 venv 的解释器版本；`sqlite`：主环境标准库 `sqlite3` 的版本与 source id，`platform_options` 是两个平台之间允许不同的编译选项前缀（其余编译选项必须逐项相同）；
- `venvs`：每个 venv 里各个分发包的版本，`null` 表示必须没装；
- `postgres`：PostgreSQL 参照的设置（`current_setting`、`pg_database` 与 ICU 排序版本）；
- `src`：两份源码检出的提交号；
- `linux`：只在服务器上核对的项：JDK 版本、pg_hba 里 `trust` 行的个数、必须覆盖的旧代码默认路径（§6）。

```json
{
  "schema": 1,
  "python": "3.13.9",
  "sqlite": {"version": "3.51.0", "source_id": "2025-11-04 19:38:17 fb2c931ae597f8d00a37574ff67aeed3eced4e5547f9120744ae4bfa8e74527b", "platform_options": ["ATOMIC_INTRINSICS=", "COMPILER=", "MUTEX_"]},
  "venvs": {
    ".venv": {"anyio": "4.15.1", "certifi": "2025.11.12", "cloudpickle": "3.1.1", "contourpy": "1.3.3", "cycler": "0.11.0", "datafusion": "54.0.0", "duckdb": "1.5.5", "fonttools": "4.60.1", "h11": "0.16.0", "httpcore": "1.0.9", "httpx": "0.28.1", "idna": "3.20", "iniconfig": "2.3.0", "kiwisolver": "1.4.9", "matplotlib": "3.10.6", "numpy": "2.3.5", "packaging": "26.3", "pillow": "12.2.0", "pluggy": "1.6.0", "psycopg2-binary": "2.9.13", "pyarrow": "21.0.0", "pygments": "2.21.0", "pyparsing": "3.2.5", "pytest": "9.1.1", "python-dateutil": "2.9.0.post0", "pyyaml": "6.0.3", "scipy": "1.16.3", "six": "1.17.0", "sniffio": "1.3.1", "sqlglot": "30.21.0", "typing-extensions": "4.16.0"},
    ".venvs/duckdb-1.1.3": {"duckdb": "1.1.3", "psycopg2-binary": "2.9.13"},
    ".venvs/duckdb-1.1.3-full": {"anyio": "4.10.0", "certifi": "2025.11.12", "cloudpickle": "3.1.2", "contourpy": "1.3.3", "cycler": "0.11.0", "datafusion": "54.0.0", "duckdb": "1.1.3", "fonttools": "4.60.1", "h11": "0.16.0", "httpcore": "1.0.9", "httpx": "0.28.1", "idna": "3.11", "iniconfig": "2.3.1", "kiwisolver": "1.4.9", "matplotlib": "3.10.6", "numpy": "2.3.5", "packaging": "26.3", "pillow": "12.2.0", "pluggy": "1.6.0", "psycopg2-binary": "2.9.13", "pyarrow": "21.0.0", "pygments": "2.21.0", "pyparsing": "3.2.5", "pytest": "9.1.1", "python-dateutil": "2.9.0.post0", "pyyaml": "6.0.3", "scipy": "1.16.3", "six": "1.17.0", "sniffio": "1.3.0", "sqlglot": "30.21.0", "typing-extensions": "4.15.0"},
    ".venvs/datafusion-50.0.0": {"datafusion": "50.0.0", "duckdb": null, "psycopg2-binary": null, "pyarrow": "25.0.1"}
  },
  "postgres": {"server_version_num": "160015", "server_encoding": "UTF8", "datcollate": "C", "datctype": "C", "datlocprovider": "c", "TimeZone": "Australia/Sydney", "DateStyle": "ISO, MDY", "default_text_search_config": "pg_catalog.english", "lc_messages": "C", "lc_monetary": "C", "lc_numeric": "C", "lc_time": "C", "icu_collversion": "153.14"},
  "src": {".src/duckdb-v1.5.5": "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa", ".src/datafusion-54.0.0": "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b"},
  "linux": {"java": "21.0.12.1", "pg_trust_rules": 0, "old_code_overrides": ["COEVO_PGBLD", "COEVO_OLD_VENV", "COEVO_DUCKDB_SRC", "COEVO_ARGUS_DIR", "COEVO_KEYS_YML"]}
}
```

## 8. SQLancer

S15 加的外部工具基线（`EXPERIMENT.md` §3.1 的 `sqlancer` 臂）：在服务器上真跑 SQLancer，它报出的每份缺陷日志都转成 `SqlCase`，交给与其它臂相同的七类 oracle 与 CVE 流程评判，家族由同一个身份键来数。SQLancer 说它是缺陷不算数，harness 判 `fail` 才算。

**版本。** SQLancer `ab328b756bf5d923b9d93959af3432546efe56fd`（2026-10-14 的 main，版本号 2.0.0），打一个补丁 `sqlancer/log-each-select.patch`（在 `framework/surprise/docs/` 下）：原代码在关掉 `--log-each-select` 时必然断言失败（`MainOptions.logExecutionTime` 要求先开它），而不关的话每个数据库的 `-cur.log` 会记下每一条查询，每格 24 小时几十 GB。补丁让两处调用先看 `logEachSelect`。SQLancer 自带 DuckDB JDBC 1.3.0.0；我们去掉它，换成 `duckdb_jdbc-1.5.5.0.jar`（Maven Central，SHA1 `c440b2f2f88bbf432799a44ba35e702486659978`），日志头 `-- Database version: v1.5.5` 可以核对。

**构建（Windows 本机，编排者）。**

1. JDK：Temurin 21.0.12.1+1 的 Windows zip（SHA256 `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e`）解到 `.orch/jdk/`。Maven 3.9.16 的 bin zip（核对 SHA512）解到 `.orch/maven/`。
2. `git init .orch/sqlancer-src`，`git fetch --depth 1 https://github.com/sqlancer/sqlancer.git <commit>`，检出；`git apply` 上面的补丁。
3. `JAVA_HOME=.orch/jdk/jdk-21.0.12.1+1 mvn -B -DskipTests -Dmaven.repo.local=.orch/m2 package`。
4. 组装 `.orch/sqlancer/`：`sqlancer-2.0.0.jar`；`lib/`（`target/lib` 的全部 jar，去掉 `duckdb_jdbc-1.3.0.0.jar`）；`override/duckdb_jdbc-1.5.5.0.jar`；`COMMIT`（一行 commit 哈希）。共约 450 MB。

**部署到服务器。** SQLancer 是纯 Java，DuckDB JDBC 的 jar 里带着各平台的本地库，所以整个 `.orch/sqlancer/` 原样拷过去（JDK 用服务器上已有的 `.orch/jdk/`）：

```
# Windows 本机，仓库根
tar -czf .orch/dl/sqlancer.tar.gz -C .orch sqlancer
scp .orch/dl/sqlancer.tar.gz 3090:CoevoDB/.orch/dl/
# 服务器
cd ~/CoevoDB/.orch && tar -xzf dl/sqlancer.tar.gz && cat sqlancer/COMMIT
```

**驱动怎么跑。** 网格的 `sqlancer` 臂写成 `{"name": "sqlancer", "kind": "sqlancer", "engine": "duckdb", "run": true}`（可选 `"run": {"oracles": ["NOREC", "WHERE"], "threads": 1}`），每格起 `python -m surprise.baselines.sqlancer_run`：它在格目录的 `sqlancer/` 下起 java（`--log-each-select false --log-execution-time false`、`--num-tries` 设得很大、`--timeout-seconds` 为预算），每两秒收一次新的缺陷日志，当场分类（结果不一致 `mismatch`、预期外的报错 `unexpected_error`、SQLancer 或驱动自己的问题 `tool_error`）、把能拆成"`SELECT <列> FROM <表或连接>` + 谓词"的转成 `SqlCase`（NoREC → `norec`，TLP WHERE → `tlp`）、评判。`report.json` 的 `executions` 是 SQLancer 实际执行的查询数，"每千次执行的家族数"用它算。每份日志的分类与去向在 `sqlancer/reports.jsonl`。`--replay-logs <目录>` 可以不起 java、只评判已有的日志。

**DataFusion。** SQLancer 有 DataFusion 支持，但不是经 Python：它连自己仓库里的一个 Rust 写的 Arrow Flight SQL 服务端（`src/sqlancer/datafusion/server/datafusion_server`），那个服务端钉在 DataFusion 40.0.0、arrow 52.1.0。要测 DataFusion 54.0.0，得先把服务端移植到 54.0.0 的 API 并在服务器上装 Rust 工具链编出来；做不做由 S17 决定，不做的话 E5 少 5 格（`EXPERIMENT.md` §6 已写明）。
