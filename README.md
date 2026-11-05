# codex-cli-troubleshooting

[![CI](https://github.com/Alpha-chen/codex-cli-troubleshooting/actions/workflows/ci.yml/badge.svg)](https://github.com/Alpha-chen/codex-cli-troubleshooting/actions/workflows/ci.yml)

A diagnosis playbook (Hermes Agent *skill*) for Codex CLI / Codex Desktop failures:
endless reconnect loops, `Selected model is at capacity`, `400 model_not_found`,
`Connection failed: error sending request`, `workspace routing discovery failed`.

The core idea: **one error message, four independent causes.** Codex funnels
server-side quota, model-availability, thread-size and network faults through the
same retry loop, so "it doesn't answer" carries no information until you classify
it. This skill classifies from Codex's own state before touching any proxy config.

| Layer | Looks like | Real cause |
|---|---|---|
| 0. Reconnect loop | `Error: Connection failed ... retry_delay=60s` forever | a *shell* around one of the four causes below |
| 1. Account quota | `Selected model is at capacity` / `You've hit your usage limit` | 7-day window near 100% (Plus) |
| 2. Model inventory | `400 model_not_found ... not supported when using Codex with a ChatGPT account` | `model =` names a slug this account does not have |
| 3. Environment | `error sending request` on every request | `HTTP(S)_PROXY` in the process env points at a dead port |
| 4. Network / nodes | timeouts, `routing discovery failed` | proxy node or provider line is down |

## Install

中英双语安装与使用说明见 [INSTALL.md](INSTALL.md)。
Bilingual install/usage guide: [INSTALL.md](INSTALL.md).

```bash
unzip codex-cli-troubleshooting-1.0.3.zip && cd codex-cli-troubleshooting-1.0.3 && ./install.sh
```

## What's in here

```
SKILL.md                     the playbook (Steps 0-8 + pitfalls)
scripts/codex_logs.py        error counts, timeline+model, thread map, --slice context
scripts/check_codex_quota.py /codex/usage → windows, reset ETA, credits
scripts/node_sweep.py        end-to-end node sweep through the mihomo REST API
```

## Quick start

```bash
# 1. what actually happened, and on which model / thread
python3 scripts/codex_logs.py

# 2. is it quota? (hard number + reset time)
python3 scripts/check_codex_quota.py

# 3. if it is the network class: which nodes are alive
MIHOMO_SECRET=<controller secret> python3 scripts/node_sweep.py
```

## Notes

- Codex 0.146+ does **not** write plain-text logs. Everything lives in
  `~/.codex/logs_2.sqlite` (`logs.feedback_log_body`),
  `~/.codex/state_5.sqlite` (`threads`) and
  `~/.codex/thread_history_1.sqlite` (`thread_turns.status` / `error_json`).
  Open them with `file:...?mode=ro` — Codex holds live WAL files.
- The usage endpoint nests both windows under `rate_limit`; a top-level lookup
  returns nothing and is easily misread as "no quota data".
- Model inventories are account-, plan- and release-specific. Read
  `~/.codex/models_cache.json` before editing `config.toml`; a remembered slug is
  not evidence it still exists.
- Desktop app and terminal CLI do **not** share an environment: the app spawns its
  bundled `codex` through a login shell, so stale `~/.zshrc` proxy exports land in
  it. "Works in my terminal, fails in the app" is a real class of bug.
- A dead proxy port reproduces the exact error text in one run — use it to prove
  causality instead of guessing.

Install as a Hermes skill by copying this directory to
`$HERMES_HOME/skills/devops/codex-cli-troubleshooting/`.

## License

MIT
