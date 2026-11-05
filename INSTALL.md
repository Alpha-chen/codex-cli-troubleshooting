# 安装与使用 / Install & Usage

一个 zip，一条命令，装完即用。无需 sudo、无需编译、装完不再联网。
One zip, one command, ready to use. No sudo, no build step, no network access after the download.

---

## 这是什么 / What this is

**中文** — 一个给 Agent 用的诊断技能（skill）：当 Codex CLI 或 Codex 桌面版出现
「一直 reconnect」「Selected model is at capacity」「codex 用不了」时，按四层因果
（额度 / 模型清单 / 进程环境变量 / 网络节点）逐层定位，附带三个可直接运行的脚本。

**English** — A diagnostic skill for agents. When Codex CLI or the Codex desktop app
keeps reconnecting, reports `Selected model is at capacity`, or simply "doesn't work",
it classifies the failure across four independent layers — account quota, model
inventory, process environment, network/nodes — and ships three runnable scripts.

---

## 前置条件 / Requirements

**中文**
- bash + python3（3.9 以上，脚本只用标准库，不需 pip 安装任何东西）
- macOS 或 Linux；Windows 请用 WSL
- 可选：curl + unzip（只有「一行命令」方式需要）

**English**
- bash + python3 (3.9+). Scripts are standard-library only — no pip installs.
- macOS or Linux. On Windows, use WSL.
- Optional: curl + unzip (only needed for the one-liner install).

---

## 方式一：下载 zip 解压安装（推荐） / Option 1 — from the zip (recommended)

**中文**

```bash
unzip codex-cli-troubleshooting-1.0.3.zip
cd codex-cli-troubleshooting-1.0.3
./install.sh
```

装完落在 `~/.hermes/skills/devops/codex-cli-troubleshooting/`，下一次会话自动加载。

**English**

```bash
unzip codex-cli-troubleshooting-1.0.3.zip
cd codex-cli-troubleshooting-1.0.3
./install.sh
```

It installs to `~/.hermes/skills/devops/codex-cli-troubleshooting/` and is picked up by
the next session.

---

## 方式二：一行命令 / Option 2 — one-liner

**中文**

```bash
curl -fsSL https://raw.githubusercontent.com/Alpha-chen/codex-cli-troubleshooting/main/install.sh \
  | bash -s -- --target hermes
```

脚本发现自己旁边没有文件时，会自动把 release 包下到临时目录安装，用完清理。

**English**

```bash
curl -fsSL https://raw.githubusercontent.com/Alpha-chen/codex-cli-troubleshooting/main/install.sh \
  | bash -s -- --target hermes
```

When the script finds no local package beside it, it downloads the release zip into a
temp dir, installs, and cleans up.

---

## 方式三：手动拷贝 / Option 3 — manual

**中文** — 把文件夹整个拷到 `<skills 根目录>/codex-cli-troubleshooting/`，保持内部结构不变：

**English** — Copy the folder into `<skills root>/codex-cli-troubleshooting/`, keeping the layout:

```
codex-cli-troubleshooting/
├── SKILL.md
├── scripts/
│   ├── check_codex_quota.py
│   ├── codex_logs.py
│   └── node_sweep.py
├── README.md
└── LICENSE
```

**中文** — Hermes 读 `<HERMES_HOME>/skills/**/SKILL.md`（默认 `~/.hermes/skills/`）；
Codex CLI 读 `~/.codex/skills/<名字>/SKILL.md`。

**English** — Hermes reads `<HERMES_HOME>/skills/**/SKILL.md` (default `~/.hermes/skills/`);
Codex CLI reads `~/.codex/skills/<name>/SKILL.md`.

---

## 安装参数 / Install options

| 参数 / Flag | 作用 / Effect |
|---|---|
| `--target hermes` | 默认。Hermes Agent → `~/.hermes/skills/devops/` / default target |
| `--target codex` | Codex CLI → `~/.codex/skills/` / install for Codex CLI |
| `--target both` | 两个都装 / both agents |
| `--profile NAME` | Hermes 多档案：`~/.hermes/profiles/NAME/skills/` / Hermes profile |
| `--path DIR` | 直接指定 skills 根目录 / explicit skills root |
| `--force` / `-f` | 覆盖已装版本，旧的自动备份成 `<名字>.bak.<时间戳>` / replace, old copy backed up |
| `-h` / `--help` | 显示帮助 / show help |

**中文** — 重复安装而不加 `--force` 会以退出码 1 拒绝，不会静默覆盖。
**English** — Re-running without `--force` exits 1 instead of silently overwriting.

---

## 装完怎么用 / Using it

**中文** — 不需要记脚本名，直接把现象说给 Agent，技能按触发词自动加载：

- 「codex 一直在 reconnect」/「codex 用不了」/「codex 卡住」
- 「Selected model is at capacity」/「Please try a different model」
- 「400 model_not_found」/「not supported when using Codex with a ChatGPT account」
- 「workspace routing discovery failed」/「Connection failed: error sending request」

**English** — You don't need to remember script names; describe the symptom and the
skill loads on trigger wording:

- "codex keeps reconnecting" / "codex is stuck" / "codex won't respond"
- "Selected model is at capacity" / "Please try a different model"
- "400 model_not_found" / "not supported when using Codex with a ChatGPT account"
- "workspace routing discovery failed" / "Connection failed: error sending request"

也可以直接跑脚本 / Or run the scripts directly:

```bash
SKILL=~/.hermes/skills/devops/codex-cli-troubleshooting
python3 $SKILL/scripts/codex_logs.py         # 错误计数 / 时间线+模型 / 线程映射
python3 $SKILL/scripts/check_codex_quota.py  # 额度硬数字 + 重置 ETA
MIHOMO_SECRET=<控制器密码> python3 $SKILL/scripts/node_sweep.py   # 节点存活扫描
```

---

## 验证安装 / Verify

**中文**

```bash
head -5 ~/.hermes/skills/devops/codex-cli-troubleshooting/SKILL.md   # 首行应为 name: codex-cli-troubleshooting
python3 -m py_compile ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/*.py && echo OK
python3 ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/codex_logs.py
```

**English**

```bash
head -5 ~/.hermes/skills/devops/codex-cli-troubleshooting/SKILL.md   # first line: name: codex-cli-troubleshooting
python3 -m py_compile ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/*.py && echo OK
python3 ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/codex_logs.py
```

---

## 卸载 / Uninstall

**中文**

```bash
rm -rf ~/.hermes/skills/devops/codex-cli-troubleshooting        # Hermes
rm -rf ~/.codex/skills/codex-cli-troubleshooting                # Codex CLI
```

用 `--force` 装过多次的话，`ls -d ~/.hermes/skills/devops/codex-cli-troubleshooting.bak.*`
里还有旧备份。

**English**

```bash
rm -rf ~/.hermes/skills/devops/codex-cli-troubleshooting        # Hermes
rm -rf ~/.codex/skills/codex-cli-troubleshooting                # Codex CLI
```

If you used `--force`, older copies remain as
`~/.hermes/skills/devops/codex-cli-troubleshooting.bak.*`.

---

## 安全边界 / Safety

**中文**
- 默认只读：读 `~/.codex/*.sqlite`、`models_cache.json`、`config.toml` 和代理控制器的 REST 接口，不外发任何数据。
- 绝不打印 `auth.json` 内容；额度检查在进程内解析，只输出百分比和重置时间。
- 只有在模型名被证实无效时才改 `config.toml`，且先备份成 `config.toml.bak.<时间戳>`。
- 节点扫描会临时切换代理选择，结束时恢复原选择。

**English**
- Read-only by default: it reads `~/.codex/*.sqlite`, `models_cache.json`, `config.toml`
  and the proxy controller's REST API. Nothing is sent anywhere.
- It never prints `auth.json`; the quota check parses it in-process and reports only
  percentages and reset times.
- It only edits `config.toml` when a model slug is provably invalid, and backs the file
  up first (`config.toml.bak.<timestamp>`).
- The node sweep temporarily switches your proxy selection and restores it when done.

---

## 安装失败怎么办 / If the install fails

| 现象 / Symptom | 处理 / Fix |
|---|---|
| `permission denied: ./install.sh` | 用 `bash install.sh`，或 `chmod +x install.sh` / run `bash install.sh` |
| `python3 not found` | 装 python3 后重试（macOS `brew install python`，Debian/Ubuntu `sudo apt install python3`） |
| `already exists — re-run with --force` | 加 `--force`，或先手动删旧目录 / add `--force` |
| `download failed` | 用方式一（先下 zip），或检查网络/代理 / use Option 1 |
| 装完 Agent 里看不到技能 / skill not visible | 确认路径在 `<HERMES_HOME>/skills/**/`，并重开一次会话 / check the path, start a new session |

---

## 版本 / Version

- 本说明对应 / This guide covers **v1.0.1**
- 仓库 / Repo: https://github.com/Alpha-chen/codex-cli-troubleshooting
- 下载 / Download: https://github.com/Alpha-chen/codex-cli-troubleshooting/releases
- 许可 / License: MIT
