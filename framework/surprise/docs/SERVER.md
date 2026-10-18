# SERVER · 实验服务器

2026-10-19 由 S14 建立。正式实验在这台服务器上跑（`EXPERIMENT.md` §7）。第 1–4 节是环境与部署，写给编排者；第 5 节是运行手册，写给用户；第 7 节是门槛 `gates/s14.py` 读取的机读版本表。

分工：实验由用户自己 ssh 上服务器跑。Claude 只在搭环境（S14）与部署新引擎（S16–S18）时动服务器，而且要用户先确认服务器空闲。grok 不登录服务器。

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

各 venv 的包（`uv pip freeze` 的直接依赖部分，版本照 Windows 本机）：

- `.venv` 与 `.venvs/duckdb-1.1.3-full`（只有 duckdb 版本不同）：duckdb、datafusion 54.0.0、psycopg2-binary 2.9.13、sqlglot 30.21.0、pyyaml 6.0.3、pytest 9.1.1、matplotlib 3.10.6、scipy 1.16.3、numpy 2.3.5、pyarrow 21.0.0、httpx 0.28.1。Windows 的 `.venv` 继承 anaconda 底座的包（matplotlib、scipy、numpy、pyarrow、httpx 来自那里）；服务器上把它们直接装进 venv，版本相同。
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

## 4. 重建步骤

服务器要重装时照这里做（全部在用户目录，不需要 sudo）。路径都相对 `~/CoevoDB`。

1. uv：`curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh`。
2. micromamba：`mkdir -p .orch/mamba && cd .orch/mamba && curl -fsSL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba`。
3. Python 底座：`MAMBA_ROOT_PREFIX=$PWD/.orch/mamba .orch/mamba/bin/micromamba create -y -p .orch/mamba/envs/py313 -c conda-forge --override-channels python=3.13.9 libsqlite=3.51.0`。
4. SQLite：下载 `https://sqlite.org/2025/sqlite-amalgamation-3510000.zip`，解压后
   `gcc -O2 -fPIC -shared -DSQLITE_ENABLE_COLUMN_METADATA -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_GEOPOLY -DSQLITE_ENABLE_RTREE -DSQLITE_MAX_VARIABLE_NUMBER=250000 -DSQLITE_THREADSAFE=1 sqlite3.c -o .orch/sqlite-3.51.0/lib/libsqlite3.so.3.51.0 -Wl,-soname,libsqlite3.so.0 -lpthread -ldl -lm`，
   再 `ln -sfn` 把 `envs/py313/lib/libsqlite3.so.0` 与 `libsqlite3.so` 指过去。核对 `sqlite_source_id()` 是 `2025-11-04 19:38:17 fb2c931ae597f8d00a37574ff67aeed3eced4e5547f9120744ae4bfa8e74527b`。
5. venv：`uv venv --python .orch/mamba/envs/py313/bin/python3.13 <路径>`，再 `uv pip install --python <路径>/bin/python <§2 的包==版本>`。
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
$PY -m surprise.experiments.grid run <配置.json> --out results/<名字> 2>&1 | tee results/<名字>.log
```

按 `Ctrl-b` 再按 `d` 离开 tmux，网格继续跑；`tmux attach -t <名字>` 回来看。网格中途被打断（断电、误按 `Ctrl-c`）时，用同一条命令续跑：已经 `done` 的格不会重跑，没跑完的格改名成 `<格>.stale-<k>` 保留，再从头跑。

不带 LLM 的格，子进程里没有密钥。带 LLM 的格要密钥：只在启动网格的那个 shell 里设 `DEEPSEEK_API_KEY`（例如 `read -s DEEPSEEK_API_KEY && export DEEPSEEK_API_KEY`），不要写进文件、命令行参数或 `~/.bashrc`。

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
scp 3090:<名字>.tar.gz D:\CoevoDB\framework\results\server\
```

拷回并核对能解压之后，再删服务器上的原始目录（里程碑报告出完之前不要删；E1 的原始目录要留到 E3 与 S16–S18 的回放检查都用完，见 `EXPERIMENT.md` §5）。

### 5.6 S14 冒烟

S14 的门槛要求用户照本节跑通一次 1 分钟的冒烟网格。配置是 `framework/surprise/docs/grids/s14_smoke.json`（一个不带 LLM 的 `surprise` 臂与读汇总的 `sqlancer` 臂，种子 7，每格 1 分钟，约 2 分钟跑完）：

```
tmux new -s s14-smoke
cd ~/CoevoDB/framework
$PY -m surprise.experiments.grid run surprise/docs/grids/s14_smoke.json --out results/s14-smoke 2>&1 | tee results/s14-smoke.log
$PY -m surprise.experiments.grid status results/s14-smoke
$PY -m surprise.metrics.report results/s14-smoke
cd ~/CoevoDB/framework/results && tar -czf ~/s14-smoke.tar.gz s14-smoke s14-smoke.log
```

然后在 Windows 上 `scp 3090:s14-smoke.tar.gz D:\CoevoDB\framework\results\server\`，告诉编排者。

## 6. 平台差异

（S14 逐条记录，见下。）

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
  "sqlite": {
    "version": "3.51.0",
    "source_id": "2025-11-04 19:38:17 fb2c931ae597f8d00a37574ff67aeed3eced4e5547f9120744ae4bfa8e74527b",
    "platform_options": ["ATOMIC_INTRINSICS=", "COMPILER=", "MUTEX_"]
  },
  "venvs": {
    ".venv": {"duckdb": "1.5.5", "datafusion": "54.0.0", "psycopg2-binary": "2.9.13", "sqlglot": "30.21.0",
              "pyyaml": "6.0.3", "pytest": "9.1.1", "matplotlib": "3.10.6", "scipy": "1.16.3", "numpy": "2.3.5",
              "pyarrow": "21.0.0", "httpx": "0.28.1"},
    ".venvs/duckdb-1.1.3": {"duckdb": "1.1.3", "psycopg2-binary": "2.9.13"},
    ".venvs/duckdb-1.1.3-full": {"duckdb": "1.1.3", "datafusion": "54.0.0", "psycopg2-binary": "2.9.13",
                                 "sqlglot": "30.21.0", "pyyaml": "6.0.3", "pytest": "9.1.1", "matplotlib": "3.10.6",
                                 "scipy": "1.16.3", "numpy": "2.3.5", "pyarrow": "21.0.0", "httpx": "0.28.1"},
    ".venvs/datafusion-50.0.0": {"datafusion": "50.0.0", "pyarrow": "25.0.1", "duckdb": null, "psycopg2-binary": null}
  },
  "postgres": {
    "server_version_num": "160015",
    "server_encoding": "UTF8",
    "datcollate": "C",
    "datctype": "C",
    "datlocprovider": "c",
    "TimeZone": "Australia/Sydney",
    "DateStyle": "ISO, MDY",
    "default_text_search_config": "pg_catalog.english",
    "lc_messages": "C",
    "lc_monetary": "C",
    "lc_numeric": "C",
    "lc_time": "C",
    "icu_collversion": "153.14"
  },
  "src": {
    ".src/duckdb-v1.5.5": "d8cdaa33fda8df955cc76ef58a280f68f4cd43fa",
    ".src/datafusion-54.0.0": "45d943dfb8699dc9cb9ef2320e955b73e3e6c03b"
  },
  "linux": {
    "java": "21.0.12.1",
    "pg_trust_rules": 0,
    "old_code_overrides": ["COEVO_PGBLD", "COEVO_OLD_VENV", "COEVO_DUCKDB_SRC", "COEVO_ARGUS_DIR", "COEVO_KEYS_YML"]
  }
}
```
