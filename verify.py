#!/usr/bin/env python3
"""
verify.py — read REAL public play counts, show delta vs the last sample AND vs
session start, and append a history line.

Usage:
    python verify.py <url_or_id>
    python verify.py --all                 # every enabled campaign in campaigns.json
    python verify.py --all --watch 60      # loop every 60s
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
COUNT_FILE = BASE / "viewcounts.json"
LOG_FILE = BASE / "viewcounts.log"
CAMPAIGNS_FILE = BASE / "campaigns.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def to_id(s: str) -> str:
    m = re.search(r"/video/(\d{15,20})", s or "") or re.search(r"(\d{18,19})", s or "")
    return m.group(1) if m else (s or "").strip()


def counter(item_id: str) -> int:
    r = requests.get(f"https://tiktok.livecounts.io/video/stats/{item_id}",
                     headers={"user-agent": UA}, timeout=15)
    r.raise_for_status()
    d = r.json()
    for k in ("playCount", "play_count", "viewCount", "views", "view_count"):
        if k in d:
            return int(d[k])
    raise KeyError(f"no counter field in {list(d.keys())}")


def load_counts() -> dict:
    if COUNT_FILE.exists():
        try:
            return json.loads(COUNT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_counts(d: dict) -> None:
    COUNT_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def load_targets() -> list[tuple[str, str]]:
    if not CAMPAIGNS_FILE.exists():
        return []
    raw = json.loads(CAMPAIGNS_FILE.read_text(encoding="utf-8"))
    camps = raw.get("campaigns", raw) if isinstance(raw, dict) else raw
    out = []
    for c in camps:
        if not c.get("enabled", True):
            continue
        vid = to_id(c.get("url") or c.get("id") or "")
        if vid:
            out.append((c.get("name") or vid, vid))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--all", action="store_true", help="all enabled campaigns")
    ap.add_argument("--watch", type=int, default=0, help="loop every N seconds")
    args = ap.parse_args()

    pairs = load_targets() if (args.all or not args.video) else \
        [(to_id(args.video), to_id(args.video))]
    if not pairs:
        print("[-] no targets")
        return 1

    session_start: dict[str, int] = {}

    def sample() -> None:
        counts = load_counts()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[*] view counts @ {ts}")
        print(f"    {'campaign':<30}{'now':>12}{'last':>12}{'session':>12}")
        print("    " + "-" * 66)
        for name, vid in pairs:
            try:
                now = counter(vid)
            except Exception as e:
                print(f"    {name[:29]:<30}{'ERR':>12}  ({type(e).__name__})")
                continue
            prev = counts.get(vid, now)
            if vid not in session_start:
                session_start[vid] = now
            d_last = now - prev
            d_sess = now - session_start[vid]
            print(f"    {name[:29]:<30}{now:>12,}{d_last:>+12,}{d_sess:>+12,}")
            counts[vid] = now
            try:
                with LOG_FILE.open("a", encoding="utf-8") as f:
                    f.write(f"{ts},{vid},{now}\n")
            except Exception:
                pass
        save_counts(counts)

    sample()
    while args.watch:
        time.sleep(args.watch)
        sample()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())