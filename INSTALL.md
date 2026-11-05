# Install

One zip, one command. No sudo, no build step, no network access after the download.

## 1. From the zip (recommended)

```bash
unzip codex-cli-troubleshooting-1.0.0.zip
cd codex-cli-troubleshooting-1.0.0
./install.sh
```

That is it — the skill lands in `~/.hermes/skills/devops/codex-cli-troubleshooting/`
and is picked up by the next Hermes session.

Common variants:

```bash
./install.sh --target codex          # Codex CLI instead: ~/.codex/skills/<name>/
./install.sh --target both           # both agents
./install.sh --profile work          # Hermes profile: ~/.hermes/profiles/work/skills/
./install.sh --path /opt/hermes/skills   # explicit skills root
./install.sh --force                 # replace an existing install (old one is backed up)
```

## 2. Standalone one-liner (no download of the zip first)

```bash
curl -fsSL https://raw.githubusercontent.com/Alpha-chen/codex-cli-troubleshooting/main/install.sh \
  | bash -s -- --target hermes
```

The script detects that it has no local files next to it, fetches the release zip
into a temp dir, installs, and cleans up.

## 3. Manual

Copy the folder to `<skills root>/codex-cli-troubleshooting/` keeping the layout:

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

Hermes reads `<HERMES_HOME>/skills/**/SKILL.md` (default `~/.hermes/skills/`);
Codex CLI reads `~/.codex/skills/<name>/SKILL.md`.

## Requirements

- **bash** and **python3** (3.9+). The scripts are standard library only — no pip installs.
- macOS or Linux. Windows: run under WSL, or copy the folder manually.
- Optional: `curl` + `unzip` for the standalone mode.

## Verify the install worked

```bash
# frontmatter must start with "name: codex-cli-troubleshooting"
head -5 ~/.hermes/skills/devops/codex-cli-troubleshooting/SKILL.md

# scripts compile and are executable
python3 -m py_compile ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/*.py && echo OK

# a real read of your Codex logs (needs ~/.codex to exist)
python3 ~/.hermes/skills/devops/codex-cli-troubleshooting/scripts/codex_logs.py
```

Then just describe the symptom in a new agent session — e.g. *"codex 一直在 reconnect"*,
*"Selected model is at capacity"*, *"codex 用不了"* — the skill loads itself on trigger
wording and walks the four-layer classification.

## Uninstall

```bash
rm -rf ~/.hermes/skills/devops/codex-cli-troubleshooting
# Codex CLI: rm -rf ~/.codex/skills/codex-cli-troubleshooting
```

A `--force` reinstall moves the previous copy to `<name>.bak.<timestamp>`; delete those
too if you want a clean removal.

## What it will and will not do

- Read-only by default: it reads `~/.codex/*.sqlite`, `models_cache.json`, `config.toml`
  and the proxy controller's REST API. Nothing is sent anywhere.
- It **never** prints `auth.json` contents; quota checks parse it in-process and only
  report percentages and reset times.
- It only writes to `config.toml` when a model slug is provably invalid, and it backs the
  file up first (`config.toml.bak.<timestamp>`).
- The node sweep temporarily switches your proxy selection and restores the previous one
  when it finishes.
