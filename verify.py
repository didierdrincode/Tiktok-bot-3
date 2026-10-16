#!/usr/bin/env python3
"""
verify.py — read a video's REAL public play counter and measure the delta.
Usage:
    python verify.py <video_url_or_id>
    python verify.py <video_url_or_id> --watch 30      # sample every 30s
"""
from __future__ import annotations

import argparse
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def to_id(s: str) -> str:
    m = re.search(r"/video/(\d{15,20})", s) or re.search(r"(\d{18,19})", s)
    return m.group(1) if m else s.strip()


def counter(item_id: str) -> int:
    r = requests.get(f"https://tiktok.livecounts.io/video/stats/{item_id}",
                     headers={"user-agent": UA}, timeout=15)
    r.raise_for_status()
    d = r.json()
    for k in ("playCount", "play_count", "viewCount", "views", "view_count"):
        if k in d:
            return int(d[k])
    raise KeyError(f"no counter field in {list(d.keys())}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--watch", type=int, default=0, help="sample every N seconds")
    args = ap.parse_args()

    vid = to_id(args.video)
    if args.watch:
        first = counter(vid)
        print(f"[start] {first:,}")
        while True:
            time.sleep(args.watch)
            now = counter(vid)
            print(f"[+{now - first:,}] {now:,}")
    else:
        print(f"{vid}: {counter(vid):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())