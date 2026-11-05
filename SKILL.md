---
name: codex-cli-troubleshooting
description: "Fix Codex reconnect loops, quota, model, proxy errors."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [codex, openai, chatgpt, quota, capacity, model-not-found, diagnostics, sqlite]
    related_skills: [codex, cn-network-ops]
---

# Codex CLI troubleshooting

## When to use

- "codex 用不了 / 无法对话 / 卡住 / 一直重试 / 很慢"
- `Selected model is at capacity` / `Please try a different model`
- 400 `model_not_found` / `The '<model>' model is not supported when using Codex with a ChatGPT account`
- `workspace routing discovery failed` / `stream connection failed`
- Any `codex exec` failure, or "检查一下我的 codex 环境"

Do not open with the proxy or a network diag. Codex funnels server-side quota,
model-availability and network faults through the same retry loop, so one symptom
has four independent causes. Classify from Codex's own state first.

## Classification table — read before touching anything

| What the log or `exec` says | Cause | Fix |
|---|---|---|
| `Selected model is at capacity` / 429 | quota near ceiling, or the model is deprioritised | quota check → wait for reset, or credits |
| 400 `model_not_found`: "The 'X' model is not supported when using Codex with a ChatGPT account" | configured model is not in this account's inventory (config drift, retired slug) | set `model` to a slug from `models_cache.json` |
| `Connection failed: error sending request` (`retry_delay=10s`/`60s`) / `workspace routing discovery failed` | 一直在 reconnect / 无限重试 | 先走 Step 0 分流（外壳可能是额度/模型）/ Step 6 / Step 8 |
| `failed to load models cache: missing field ...` | `models_cache.json` schema drift | let Codex refetch; delete the file if it persists |

**The trap: all four render identically in the TUI.** Endless retries with no
output is also what a *bad model name* looks like. Read the error string; never
infer the class from "it doesn't answer".

## Step 0 — 一直在 reconnect / 无限重试：先分流，再修

这个症状本身不含信息量：**重试循环是 Codex 对所有失败类型的统一外壳**。
按下面顺序走，不要在第一步就去动代理或节点。

### 0.1 先确定“谁”在重试，从哪个线程

```bash
# 桌面 App 的 codex 子进程（它和终端的 CLI 不共享环境）
pgrep -f "CodexCLI.app/Contents/MacOS/codex"
# 线程 + 模型 + cwd + 重试间隔（60s = 流已建立后才重试，10s = 首次发送就失败）
python3 - <<'PY'
import sqlite3, os, datetime, re
c=sqlite3.connect(f"file:{os.path.expanduser('~/.codex/logs_2.sqlite')}?mode=ro", uri=True)
ts,b=c.execute("select ts,feedback_log_body from logs where feedback_log_body like '%Connection failed%' order by id desc limit 1").fetchone()
print(datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S'))
for pat in (r'thread_id=([\w\-]+)', r'model=([\w.\-]+)', r'cwd=([^ ]+)', r'retry_delay=(\w+)'):
    m=re.search(pat,b); print(f'  {pat[:10]:12}', m.group(1) if m else '-')
PY
```

### 0.2 剥开外壳：看这一轮自己的 `error_json`

`Connection failed` 只是传输层外壳，真实原因常藏在同一轮的 turn 记录里（额度、模型不存在、
上下文超限）。**这一步是整个流程里性价比最高的**：

```bash
python3 - <<'PY'
import sqlite3, os, datetime
c=sqlite3.connect(f"file:{os.path.expanduser('~/.codex/thread_history_1.sqlite')}?mode=ro", uri=True)
tid=os.environ.get('TID')  # 0.1 取到的 thread_id
for r in c.execute("select status, substr(coalesce(error_json,''),1,160), started_at "
                   "from thread_turns where thread_id like ? order by started_at desc limit 5", (tid+'%',)):
    print(r[0], '|', r[1] or '-', '|', datetime.datetime.fromtimestamp(r[2]).strftime('%m-%d %H:%M') if r[2] else '-')
PY
```

看到的 `You've hit your usage limit` / `model_not_found` / `context length` 才是要修的东西；
`Connection failed` 本身通常不用修。

### 0.3 按 0.2 的结果分派

| 0.2 里看到的 | 真正要做的 | 去哪 |
|---|---|---|
| 什么都没有，纯 `error sending request` | 进程 env 里的代理端口是死的（尤其桌面 App） | Step 8 |
| `You've hit your usage limit` / `at capacity` | 额度，等 7 天窗口重置 | Step 4 |
| `model_not_found` / `not supported` | 模型名不在账号清单里 | Step 3 |
| `context length` / 线程极大 | 换新线程，不要在原线程重试 | 0.4 |
| `000`、多秒超时、节点探测也不通 | 线路/节点 | Step 7 |

### 0.4 线程本体的处理（重试循环自己的副作用）

重试循环会让一个已经坏掉的线程持续重发**整个上下文**。先量体积：

```bash
python3 -c "
import sqlite3,os
c=sqlite3.connect(f\"file:{os.path.expanduser('~/.codex/thread_history_1.sqlite')}?mode=ro\",uri=True)
print(c.execute(\"select sum(length(item_json)),count(*) from thread_items where thread_id like ?\",(os.environ['TID']+'%',)).fetchone())
"
```

- 几 MB 以上 / 上千条 item：别修线程，`/new`（或 fork）开新会话继续做事。实测一个 29 轮、1360 条、
  40 MB 的线程，每次重试都在重发巨量上下文，怎么改配置都不会变好。
- 想止住循环：TUI 里打断该轮；**桌面 App 必须退出重开**（env 修复也只有重开进程才生效，
  `kill` 后 `open -a /Applications/ChatGPT.app`）。

### 0.5 “算修好了”的可观测标准（缺一不可）

```bash
# a) 最后一条 Connection failed 的时间戳不再前进（对比当前时间）
# b) 用 config 默认跑一次真请求，拿到 tokens used
codex exec --skip-git-repo-check "Reply with exactly: CONFIG-OK"
# c) 桌面 App：新 codex 子进程的 env 里代理端口是活的（或干脆没有代理变量）
ps eww -p $(pgrep -f "CodexCLI.app/Contents/MacOS/codex" | head -1) | tr ' ' '\n' | grep -Ei '^(HTTP|HTTPS)_PROXY='
```

只说“应该好了”不算。没有 (a)+(b) 就是没修完，重试循环还会继续刷日志。

## Step 1 — read the SQLite logs, not the log directory

`~/.codex/log/` holds only `codex-login.log`. Structured events live in SQLite,
and must be opened READ-ONLY because Codex holds live `-wal`/`-shm` files.

| File | Table | Content |
|---|---|---|
| `~/.codex/logs_2.sqlite` | `logs` | every event, text in `feedback_log_body` |
| `~/.codex/state_5.sqlite` | `threads` | id → title → model → cwd |

```bash
python3 - <<'PY'
import sqlite3, re, datetime, os
c = sqlite3.connect(f"file:{os.path.expanduser('~/.codex/logs_2.sqlite')}?mode=ro", uri=True)
for kw in ['at capacity','Connection failed','routing discovery','429','503','model_not_found','not supported']:
    n = c.execute('select count(*) from logs where feedback_log_body like ?', ('%'+kw+'%',)).fetchone()[0]
    print(f'{kw:20} {n}')
q = '''select ts, feedback_log_body from logs
where (feedback_log_body like '%at capacity%' or feedback_log_body like '%Connection failed%'
    or feedback_log_body like '%routing discovery%' or feedback_log_body like '%not supported%')
order by id desc limit 25'''
for ts, b in c.execute(q):
    m = re.search(r'model=([\w.\-]+)', b)
    kind = ('AT_CAPACITY' if 'at capacity' in b else 'ROUTING' if 'routing discovery' in b
            else 'CONN' if 'Connection failed' in b else 'MODEL' if 'not supported' in b else '?')
    print(datetime.datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S'), f'{kind:12}', m.group(1) if m else '-')
PY
```

`feedback_log_body` is ~90% tracing spans — slice ±800 chars around the keyword
to see the substance:

```bash
python3 -c "
import sqlite3,os
c=sqlite3.connect(f\"file:{os.path.expanduser('~/.codex/logs_2.sqlite')}?mode=ro\",uri=True)
b=c.execute(\"select feedback_log_body from logs where feedback_log_body like '%Connection failed%' order by id desc limit 1\").fetchone()[0]
i=b.find('Connection failed'); print(b[max(0,i-900):i+400])
"
```

## Step 2 — the classes are independent; check timestamps

Connection errors are usually chronologically FIRST (proxy weather), quota and
model errors come after and have nothing to do with them. Reporting the first
class you see as "the" cause is the classic misdiagnosis.

## Step 3 — model inventory: the cheapest fix for "无法对话"

```bash
python3 -c "
import json,os
d=json.load(open(os.path.expanduser('~/.codex/models_cache.json')))
print('fetched_at:', d.get('fetched_at'), 'client:', d.get('client_version'))
for m in d.get('models',[]): print(m['slug'], 'vis=', m.get('visibility'), 'prio=', m.get('priority'))
"
```

- `visibility: list` = selectable by the user; `hide` = internal, not selectable.
- A configured `model =` that is absent from this list can only produce
  `model_not_found`; no proxy or quota change will help. Repoint it at a `list` slug.
- If `config.toml` names one model but the log names another, the user switched
  models in the TUI — fix the model that actually ran, and say so.

## Step 4 — quota, as a hard number

`scripts/check_codex_quota.py` parses `~/.codex/auth.json` and GETs
`https://chatgpt.com/backend-api/codex/usage` with `Authorization: Bearer` plus
`chatgpt-account-id`, then prints windows, reset ETA and credits.

**The windows are nested under `rate_limit`**, not at the top level:

```
rate_limit.primary_window.used_percent     # ~5h window
rate_limit.secondary_window.used_percent   # 7-day window — gates new/expensive models
rate_limit.secondary_window.reset_at       # unix ts → convert to local time + hours left
credits.has_credits / balance              # "false" / "0" = no overflow escape hatch
```

`secondary_window` ≥ ~90% on a Plus account **is** what `at capacity` means: the
account is throttled, the server is not down. Say it plainly with the reset
date/time, and do not present "try another model" as the fix — at that level
every premium model fails most of the time.

## Step 5 — one probe per model to split model-not-found from capacity

```bash
cd ~ && for m in <slug-a> <slug-b>; do echo "== $m";
  timeout 95 codex exec --skip-git-repo-check -m "$m" "reply with the single word OK" 2>&1 | tail -4
  done
```

- success prints `tokens used`
- `Selected model is at capacity` → that slot is quota-blocked right now
- 400 `model_not_found` → the account does not have that model at all

One model per terminal call, `timeout ~95`: each `exec` is a full agent start and
batching them blows any sane tool timeout. Use 5 runs before ranking two models —
capacity is stochastic and 3-run samples flip the order. Re-measure after changing
exit node; the node dominates the failure rate.

## Step 6 — network probe (only for the connection class)

```bash
for i in 1 2 3; do curl -s -o /dev/null -w "%{http_code} %{time_total}s %{remote_ip}\n" \
  --max-time 20 -X POST https://chatgpt.com/backend-api/codex/responses \
  -H "Authorization: Bearer $TOKEN" -H "chatgpt-account-id: $ACCT" \
  -H 'Content-Type: application/json' -d '{}'; done
```

`400`/`401` in well under a second, repeated 3× = endpoint reachable, path healthy
(empty body / fake cred is the point of the probe). `000` or multi-second = real
network fault → `cn-network-ops`. A `%{remote_ip}` in `198.18.x` means a TUN
client is in play and no proxy env is needed.

## Step 7 — only for the network class: node sweep (UDP protocols)

Run this **after** Steps 3-4 rule out model/quota. On this Mac the client is
猫熊网络/Maoxiong (mihomo core, renamed `Dapan.suid`, root), `mixed-port 17890`,
TUN with fake-IP, and its own config is encrypted (`config.enc`) while the
on-disk `config.yaml` is a placeholder (`proxies: []`, `rules: MATCH,REJECT`).
The runtime API is therefore the only truthful view:

```bash
# TLS controller, self-signed, secret in config.yaml
curl -sk -H "Authorization: Bearer <secret>" https://127.0.0.1:19090/configs
curl -sk -H "Authorization: Bearer <secret>" https://127.0.0.1:19090/version
```

`scripts/node_sweep.py` switches each node through that API and makes a real
`POST` to the Codex endpoint:

```bash
MIHOMO_SECRET=<secret> python3 scripts/node_sweep.py          # TUN: no PROXY needed
MIHOMO_SECRET=<secret> PROXY=http://127.0.0.1:17890 python3 scripts/node_sweep.py
```

- `401`/`400`/`403`/`404` in ~1s = node works and reached OpenAI (bogus cred / empty body).
- `000` at a uniform ~5.00s across **every** node including US ones = provider-wide
  outage, not your config. Verify local network (`curl --noproxy '*' https://www.baidu.com`),
  core liveness and DNS first, then report it as 服务商线路故障 and stop editing.
- All non-US nodes dead while some US ones work = carrier UDP block on hysteria2.
  Pin a US node; never leave the group on `自动选择` (url-test ranks by latency and a
  UDP-blackholed node still TCP-connects fast).
- A `PUT` answers `204` with an empty body — `json.loads()` on it raises. Guard with
  `return json.loads(raw) if raw else {}`.
- Group names contain emoji/CJK: `urllib.parse.quote(name, safe="")`.
- A `PUT` is runtime-only. Persist by putting the node first in the group's `proxies:`
  list — only possible when the client exposes an editable YAML (this one does not).
- Sweep results expire fast: 7 working nodes → 0 working inside 40 minutes was observed.
  Re-sweep before claiming anything about node health.

### The node pool rotates — sweep before every session, not once

**Treat a sweep result as valid for minutes, not days.** The working set does not
just shrink and recover — it *rotates* to a different set of countries. Measured
on the same subscription, same day, ~3 hours apart:

| Time | Working nodes | Dead |
|---|---|---|
| 17:00 | 7 — **all US** (V215 0.80s, V110, V213, V217, V214, V216, V212) | every HK/JP/TW/SG/KR/UK/DE/CA/NL/RU/MY/TH node |
| 17:50 | 0 — provider-wide outage | everything, US included |
| 20:30 | 6 — **mostly TW/SG** (TW V107 1.74s, TW V106, SG V101, SG V102, RU V109, HK-V234) | every US node that worked at 17:00 |

Two conclusions that change how you work:

1. **A previously-good node is not a safe default.** The US node pinned at 17:00
   was dead at 20:30. Hard-coding one node and never re-checking is the same
   mistake as leaving the group on `自动选择`.
2. **The failure *shape* tells you which regime you are in.** "Some nodes work,
   and they are all one country" = the carrier is blocking UDP by region and the
   region changes. "Zero nodes work, US included, everything at a uniform 5.00s"
   = the provider's line is down. Different reports, different advice.

So the practical rule:

```bash
# start of every Codex troubleshooting session — 2 minutes, worth it
export MIHOMO_CTRL=http://127.0.0.1:9090        # plain HTTP controller
export MIHOMO_GROUP="🌍 国外网站"
export PROXY=http://127.0.0.1:7892
python3 scripts/node_sweep.py
# then pin whatever it says is fastest, and record the timestamp in the report
```

Do not skip this because "it worked an hour ago". Do not report a node as
healthy without a probe from *this* session. When you pin a node, say when it was
measured:

> 节点：🇹🇼 V107（20:30 实测 1.74s，3 次全 401）

That timestamp is the part that makes the claim honest — it tells the next
session (or the user, an hour later) that the ranking has an expiry.

- **Switching a node is `PUT /proxies/<GROUP>` with `{"name": <node>}` in the body.**
  `PUT /proxies/<node>` returns `400 Bad Request` for every node, which a naive sweep
  silently turns into "all good" because the probe then measures the *unchanged*
  current selection 51 times. Always assert the selector actually changed
  (`/proxies/<group>.now`) before trusting a sweep.
- Auto-picking the group: `GLOBAL` is listed first and has an `all` array, but it is
  not switchable — skip the builtin groups (`GLOBAL/DIRECT/REJECT/PASS`) and prefer a
  `Selector` whose members are real nodes. Restore the original selection when done.
- **Do not sweep while the user is mid-turn.** Each switch tears down the live
  connection, so a 50-node sweep injects a burst of `Connection failed` rows and the
  user sees "it got worse". Check for an in-flight turn first (Step 0.1), or warn that
  the next ~2 minutes of errors are yours and say so in the report.

## Step 8 — GUI app only? check the proxy ENV of the codex child process

Symptom: the Codex Desktop app (ChatGPT.app) retries forever with
`Connection failed: error sending request`, while `codex exec` from a terminal
works perfectly. The CLI and the app do **not** share an environment.

```bash
NEW=$(pgrep -f "CodexCLI.app/Contents/MacOS/codex" | head -1)
ps eww -p "$NEW" | tr ' ' '\n' | grep -Ei '^(HTTP|HTTPS|ALL|NO)_PROXY='
```

On this Mac the app spawns its bundled `codex-cli` through a **login shell**, so
`~/.zshrc` exports land in it. A stale `HTTP(S)_PROXY=http://127.0.0.1:<dead port>`
(pointed at a previous client's port, e.g. 7892) makes every request fail
instantly — identical error text to a real network fault. Rust/reqwest reads
those env vars; a TUN client makes them unnecessary.

Reproduce before fixing (proves causality in one run):

```bash
HTTP_PROXY=http://127.0.0.1:<dead> HTTPS_PROXY=http://127.0.0.1:<dead> \
  timeout 60 codex exec --skip-git-repo-check -m <model> "reply OK"
# -> ERROR ... error sending request for url (https://chatgpt.com/...)
HTTP_PROXY=http://127.0.0.1:17890 HTTPS_PROXY=http://127.0.0.1:17890 \
  timeout 90 codex exec --skip-git-repo-check -m <model> "reply OK"
# -> OK / tokens used
```

Fix and apply: repoint the exports in `~/.zshrc` at the live mixed-port (or drop
them entirely under TUN), then **quit and reopen the app** — the running process
keeps its inherited env, and the session's turn will keep retrying every 60s
until it is relaunched. Verify the new child's env and the absence of fresh
`Connection failed` rows afterwards.

## Apply, then verify with the config default

1. `cp ~/.codex/config.toml ~/.codex/config.toml.bak.$(date +%Y%m%d-%H%M%S)`
2. set `model = "<slug from the inventory>"`
3. when quota is tight, drop `model_reasoning_effort` from `xhigh` to `medium` —
   effort multiplies tokens spent per turn, and a throttled account has no room for it
4. verify with **no** `-m` flag so the config default is what gets exercised:
   `codex exec --skip-git-repo-check "Reply with exactly: CONFIG-OK"`

Quote the real output (`CONFIG-OK`, `tokens used N`) in the report. Report the
layers separately: which one the user must act on (wait for reset vs change
model) and which ones are already fixed.

## Pitfalls

- **“一直在 reconnect”不是一类故障，是一个显示外壳。** 先看该轮 turn 的 `error_json`（Step 0.2），
  再决定修额度、修模型名、修线程体积还是修代理 —— 直接去换节点/重装是白忙。
- **重试循环自己会污染日志。** 判断是否恢复只能看“最后一条错误的时间戳有没有停止前进”，
  历史计数（`Connection failed 115`）在修好之后依然不变，拿它当结论会来回折腾。
- **桌面 App 与终端 CLI 是两套环境。** App 经登录 shell 继承 `~/.zshrc` 的代理变量；CLI 不继承。
  所以“我这边 codex 好用、App 一直报错”是完全正常的现象，不要用 CLI 的成功否认 App 的故障。
- **修完必须重开进程。** 代理变量被进程继承，改完 `.zshrc` 不重启 App 时那个会话会继续每 60s 重试一次。

- **Model inventory is account-, plan- and release-specific.** A slug remembered
  from an earlier diagnosis is not evidence it still exists — read
  `models_cache.json` before editing config; retired/hidden slugs fail with
  `model_not_found` while looking exactly like a dead network.
- **Do not read "无法对话 / 一直重试" as network.** The TUI surfaces a 400
  model error as an infinite retry loop.
- **Never open the SQLite files read-write.** Codex holds the WAL; use the
  `file:...?mode=ro` URI or you block on busy.
- **Never print `auth.json`.** Parse in Python, print plan/percentages only, and
  truncate any id.
- **The usage endpoint's windows are nested under `rate_limit`.** A top-level
  lookup returns nothing and gets misread as "no quota data available".
- **One `codex exec` probe per terminal call.** Six sequential probes in one
  shell loop exceed the tool timeout and lose the whole batch.
- **`Model metadata not found ... fallback metadata` is a warning, not the bug.**
  Clear a broken cache by deleting `models_cache.json` and letting Codex refetch;
  don't diagnose off the warning.
- **Fix the model that ran, not the one in the file** — compare `config.toml`
  against the model named in the log lines.
- **不要信任上一次的节点扫描结果。** 同一订阅同一天实测：17:00 可用的是 7 个美国节点，
  20:30 这 7 个全挂、换成 6 个台湾/新加坡节点。可用集合会**轮换国家**，不只是变多变少。
  所以每次排障开头先重扫一遍，并在报告里带上测量时间（"V107，20:30 实测 1.74s"）。
  把一个节点硬编码成默认值再也不复查，和留 `自动选择` 是同一类错误。

## Related

- `scripts/codex_logs.py` — Steps 1-3 in one call (counts, timeline+model, thread map, `--slice`).
- `scripts/check_codex_quota.py` — Step 4 (windows under `rate_limit`, reset ETA, credits).
- `scripts/node_sweep.py` — Step 7 end-to-end node sweep via the mihomo controller.
- `codex` — delegating actual coding work to the CLI once it answers again.
- `cn-network-ops` — when the classified cause is the network class
  (proxy nodes, TUN fake-IP, DNS pollution).
