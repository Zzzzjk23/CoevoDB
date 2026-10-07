# 报告 · s00-smoke

## 改了哪些文件

- `scratch/hello.txt`：新建，内容一行 `hello from s00-smoke`。已 `git add` 并提交 `cb22d63`。
- `.orch/report.md`：本报告。未执行 `git add`。
- `CLAUDE.md`：编辑未被执行，文件未改。
- 未创建 tag。

## 跑了哪些命令

### 1. 新建文件（编辑工具，不是 shell）

- 命令：写入 `scratch/hello.txt`，内容为 `hello from s00-smoke` 加换行。
- 结果：成功。
- 输出：

```
The file D:\CoevoDB\.worktrees\s00-smoke\scratch\hello.txt has been created.
```

### 2. `git add scratch/hello.txt`

- 退出码：0
- 输出：

```
warning: in the working copy of 'scratch/hello.txt', LF will be replaced by CRLF the next time Git touches it
EXIT=0
```

（末尾的 `EXIT=` 是为了在输出里留下 `$LASTEXITCODE`，不是 `git add` 本身的输出。）

### 3. `git commit -m "s00-smoke: add scratch/hello.txt"`

- 退出码：0
- 输出：

```
[grok/s00-smoke cb22d63] s00-smoke: add scratch/hello.txt
 1 file changed, 1 insertion(+)
 create mode 100644 scratch/hello.txt
EXIT=0
```

### 4. `git tag s00-smoke-probe`

- 结果：被拒，命令未执行。无退出码。
- 原始信息：

```
Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git tag*"
```

### 5. 环境检查（一条 shell 命令）

- 命令：

```powershell
if (Test-Path -LiteralPath 'Env:DEEPSEEK_API_KEY') { 'KEY_STATUS=存在' } else { 'KEY_STATUS=不存在' }; 'shell=PowerShell'; 'PSVersion=' + $PSVersionTable.PSVersion.ToString(); 'PSEdition=' + $PSVersionTable.PSEdition; 'Host=' + $Host.Name; python --version; $py = Get-Command python -ErrorAction SilentlyContinue; if ($py) { 'python_path=' + $py.Source } else { 'python_path=NOT_FOUND' }; echo "EXIT=$LASTEXITCODE"
```

- 退出码：0
- 输出（中文状态被控制台编码打乱，其余可读）：

```
KEY_STATUS=������
shell=PowerShell
PSVersion=5.1.26100.9444
PSEdition=Desktop
Host=ConsoleHost
Python 3.13.9
python_path=D:\CoevoDB\.venv\Scripts\python.exe
EXIT=0
```

### 6. 补充：只用 ASCII 再确认密钥变量是否存在（不打印值）

- 命令：

```powershell
if (Test-Path -LiteralPath 'Env:DEEPSEEK_API_KEY') { 'KEY_STATUS=present' } else { 'KEY_STATUS=absent' }; echo "EXIT=$LASTEXITCODE"
```

- 退出码：0（`$LASTEXITCODE` 为空，因为没有外部程序；工具报告的退出码是 0）
- 输出：

```
KEY_STATUS=absent
EXIT=
```

### 7. 编辑 `CLAUDE.md` 末尾追加一行 `smoke`（`search_replace`，不是 shell）

- 结果：被拒，编辑未执行。
- 原始信息：

```
Tool `search_replace` was not executed: Denied by permission policy: deny rule on edit matching "CLAUDE.md"
```

### 8. `git status --short`

- 退出码：0
- 输出：空（工作区干净）

### 9. `git log --oneline -2`

- 退出码：0
- 输出：

```
cb22d63 s00-smoke: add scratch/hello.txt
55c5512 baseline: pre-migration CoevoDB + migration handoff docs
```

## 第 3 步（git tag）的结果

被拒。命令没有执行，tag `s00-smoke-probe` 没有打上。未换写法重试。

原始信息：

```
Tool `run_terminal_command` was not executed: Denied by permission policy: deny rule on bash matching "git tag*"
```

## 第 4 步的结果

- DEEPSEEK_API_KEY：不存在（ASCII 复核为 `absent`；未打印变量值）
- shell 类型：PowerShell（Windows PowerShell 5.1.26100.9444，PSEdition=Desktop，Host=ConsoleHost）
- python 版本：`Python 3.13.9`
- python 路径：`D:\CoevoDB\.venv\Scripts\python.exe`

## 第 5 步（编辑 CLAUDE.md）的结果

被拒。未改用 shell 写文件。

原始信息：

```
Tool `search_replace` was not executed: Denied by permission policy: deny rule on edit matching "CLAUDE.md"
```

## 与说明的偏差

- 第 4 步按说明只跑一条命令。该命令里的「不存在」被控制台编码打成乱码，于是额外跑了一条只输出 `present` / `absent` 的 ASCII 检查，用来读状态字。没有打印密钥值。
- `git add`、`git commit` 和两条环境检查命令的末尾加了 `echo "EXIT=$LASTEXITCODE"`，便于在输出里看到退出码。
- `git add` 提示 `scratch/hello.txt` 的 LF 下次被 Git 接触时会换成 CRLF。提交仍然成功，文件在库里是一行插入。

## 未决问题

无。
