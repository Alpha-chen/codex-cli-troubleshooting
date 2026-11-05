#!/usr/bin/env python3
"""End-to-end sweep of proxy nodes against the Codex endpoint.

Why end-to-end: hysteria2 is UDP-only, so a TCP port probe reports healthy nodes
that are actually blackholed. Switch the selector, then make a real request.
401/400/403/404/200 all mean "reached OpenAI" (bogus credential / empty body is
the point of the probe). 000 or a multi-second timeout means dead.

Env:
  MIHOMO_CTRL    controller base URL   default https://127.0.0.1:19090 (TLS, self-signed)
                                        use http://127.0.0.1:9090 for a plain controller
  MIHOMO_SECRET  controller secret     (mihomo config `secret:` value)
  MIHOMO_GROUP   selector group name   (auto: first Selector/URLTest group if unset)
  PROXY          explicit proxy URL for the probe, e.g. http://127.0.0.1:17890
                                        omit when the client runs in TUN mode — the
                                        kernel already routes traffic into the tunnel
  CODEX_URL      probe target          default chatgpt.com/backend-api/codex/responses

Prints one line per node: OK/--  http_code  latency  node, then restores the
selection that was active when the sweep started.
"""
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CTRL = os.environ.get("MIHOMO_CTRL", "https://127.0.0.1:19090").rstrip("/")
SECRET = os.environ.get("MIHOMO_SECRET", "")
GROUP = os.environ.get("MIHOMO_GROUP", "")
PROXY = os.environ.get("PROXY", "")
URL = os.environ.get("CODEX_URL", "https://chatgpt.com/backend-api/codex/responses")
OK_CODES = {"200", "400", "401", "403", "404"}
BUILTIN = {"GLOBAL", "DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"}

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def api(path, method="GET", data=None):
    req = urllib.request.Request(
        CTRL + path,
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {SECRET}"} if SECRET else {}),
        },
    )
    raw = urllib.request.urlopen(req, timeout=8, context=_ctx).read()
    return json.loads(raw) if raw else {}  # PUT answers 204 with an empty body


def pick_group(proxies):
    """A group whose members are real nodes. GLOBAL is listed first but is not
    switchable via PUT and contains everything, so never auto-pick it."""
    if GROUP:
        return GROUP
    for want in ("Selector", "URLTest", "Fallback"):
        for name, meta in proxies.items():
            if meta.get("type") == want and meta.get("all") and name not in BUILTIN:
                if any(n not in BUILTIN for n in meta["all"]):
                    return name
    return ""


def select(group, node):
    """PUT switches a GROUP (the URL), with the node in the body. PUT /proxies/<node>
    is the mistake that yields HTTP 400 'Bad Request'."""
    api("/proxies/" + urllib.parse.quote(group, safe=""), "PUT", {"name": node})
    time.sleep(0.4)


def probe():
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}|%{time_total}",
           "--max-time", "12", "-X", "POST", URL,
           "-H", "Content-Type: application/json", "-d", "{}"]
    if PROXY:
        cmd[1:1] = ["-x", PROXY]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    code, _, secs = out.partition("|")
    return code or "000", secs or "-"


def main():
    try:
        proxies = api("/proxies")["proxies"]
    except Exception as exc:
        sys.exit(f"controller unreachable at {CTRL}: {exc}\n"
                 "Enable `external-controller` (and `secret`) in the client config first.")

    group = pick_group(proxies)
    if not group:
        sys.exit("no switchable group exposed by the controller — the client may decrypt "
                 "its config at runtime and hide its selectors. Sweep from its own UI instead.")
    members = proxies[group].get("all") or []
    original = proxies[group].get("now")

    nodes = [n for n in members if proxies.get(n, {}).get("type", "").lower().startswith("hysteria")]
    if not nodes:  # any real node type beats an empty sweep
        nodes = [n for n in members if n not in BUILTIN and proxies.get(n, {}).get("type")]
    if not nodes:
        sys.exit(f"group {group!r} exposes no concrete nodes")

    print(f"group={group!r} original={original!r} nodes={len(nodes)}")
    good = []
    try:
        for name in nodes:
            try:
                select(group, name)
            except Exception as exc:
                print(f"--  SWITCHFAIL  -  {name}  ({exc})")
                continue
            code, secs = probe()
            ok = code in OK_CODES
            if ok:
                good.append((float(secs), name))
            print(f"{'OK' if ok else '--'}  {code:>3}  {secs:>6}s  {name}")
    finally:
        if original:
            try:
                select(group, original)
                print(f"restored selection: {original}")
            except Exception as exc:
                print(f"!! could not restore {original!r}: {exc}")

    print(f"=== {len(good)}/{len(nodes)} working ===")
    for secs, name in sorted(good)[:10]:
        print(f"  {secs:5.2f}s  {name}")
    if not good:
        print("0/N => provider-wide outage or a carrier UDP block, not your config. "
              "Check local network (curl --noproxy '*' https://www.baidu.com), core liveness "
              "and DNS before re-editing anything.")


if __name__ == "__main__":
    main()
