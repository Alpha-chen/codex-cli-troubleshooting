#!/usr/bin/env python3
"""One-shot Codex recon: error counts, error timeline with model, thread map.

Read-only (mode=ro) because Codex holds live -wal/-shm files.

  python3 codex_logs.py            # counts + last 25 errors + recent threads
  python3 codex_logs.py --slice "Connection failed"   # +-900 chars of context
"""
import datetime
import os
import re
import sqlite3
import sys

HOME = os.path.expanduser("~/.codex")
LOGS = f"file:{HOME}/logs_2.sqlite?mode=ro"
STATE = f"file:{HOME}/state_5.sqlite?mode=ro"
KINDS = ["at capacity", "Connection failed", "routing discovery", "429", "503",
         "model_not_found", "not supported", "missing field"]


def main():
    c = sqlite3.connect(LOGS, uri=True)
    print("=== error counts ===")
    for kw in KINDS:
        n = c.execute("select count(*) from logs where feedback_log_body like ?",
                      ("%" + kw + "%",)).fetchone()[0]
        print(f"{kw:22} {n}")

    print("\n=== last 25 error events ===")
    q = """select ts, feedback_log_body from logs
           where (feedback_log_body like '%at capacity%'
               or feedback_log_body like '%Connection failed%'
               or feedback_log_body like '%routing discovery%'
               or feedback_log_body like '%not supported%')
           order by id desc limit 25"""
    for ts, body in c.execute(q):
        m = re.search(r"model=([\w.\-]+)", body)
        kind = ("AT_CAPACITY" if "at capacity" in body else
                "ROUTING" if "routing discovery" in body else
                "CONN" if "Connection failed" in body else
                "MODEL" if "not supported" in body else "?")
        when = datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S")
        print(when, f"{kind:12}", m.group(1) if m else "-")

    if "--slice" in sys.argv:
        kw = sys.argv[sys.argv.index("--slice") + 1]
        row = c.execute("select feedback_log_body from logs where feedback_log_body like ? "
                        "order by id desc limit 1", ("%" + kw + "%",)).fetchone()
        if row:
            i = row[0].find(kw)
            print(f"\n=== slice around {kw!r} ===\n" + row[0][max(0, i - 900):i + 400])

    print("\n=== recent threads ===")
    try:
        s = sqlite3.connect(STATE, uri=True)
        for row in s.execute("select id, title, model, cwd from threads "
                             "order by updated_at desc limit 8"):
            print(tuple(str(x)[:60] for x in row))
    except Exception as exc:
        print("thread map unavailable:", exc)


if __name__ == "__main__":
    main()
