#!/usr/bin/env python3
"""Print Codex/ChatGPT quota windows as hard numbers.

Reads ~/.codex/auth.json, calls the codex usage endpoint, prints plan, both
rate-limit windows (used_percent, window length, reset ETA) and credits.
Never prints token material.
"""
import datetime
import json
import os
import subprocess
import sys

AUTH = os.path.expanduser("~/.codex/auth.json")
URL = "https://chatgpt.com/backend-api/codex/usage"


def main() -> int:
    try:
        auth = json.load(open(AUTH))
    except OSError as exc:
        print(f"cannot read {AUTH}: {exc}")
        return 2
    tok = (auth.get("tokens") or {})
    access = tok.get("access_token")
    if not access:
        print("no OAuth access_token in auth.json (API-key mode?)")
        return 2
    acct = tok.get("account_id", "")

    out = subprocess.run(
        ["curl", "-s", "--max-time", "25", URL,
         "-H", f"Authorization: Bearer {access}",
         "-H", f"chatgpt-account-id: {acct}",
         "-H", "User-Agent: codex-cli"],
        capture_output=True, text=True).stdout.strip()
    if not out.startswith("{"):
        print(f"unexpected response ({len(out)} bytes): {out[:300]}")
        return 1

    data = json.loads(out)
    print("plan_type:", data.get("plan_type"))
    print("rate_limit_allowed:", (data.get("rate_limit") or {}).get("allowed"))

    rl = data.get("rate_limit") or {}
    now = datetime.datetime.now().timestamp()
    for name in ("primary_window", "secondary_window"):
        w = rl.get(name) or {}
        if not w:
            print(f"{name}: absent")
            continue
        secs = w.get("limit_window_seconds")
        reset = w.get("reset_at")
        when = datetime.datetime.fromtimestamp(reset).strftime("%Y-%m-%d %H:%M") if reset else "?"
        left = f"{(reset - now) / 3600:.1f}h" if reset else "?"
        print(f"{name}: used {w.get('used_percent')}%  window {secs}s  reset {when} (in {left})")

    cr = data.get("credits") or {}
    if cr:
        print(f"credits: has_credits={cr.get('has_credits')} balance={cr.get('balance')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
