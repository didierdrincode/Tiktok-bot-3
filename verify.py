#!/usr/bin/env python3
"""
verify.py — read REAL public play counts, show delta vs the last sample AND vs
session start, and append a history line.

Primary source : tiktok.livecounts.io (needs origin/authority headers)
Fallback source: TikTok's own aweme/detail endpoint using the local signer

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
from urllib.parse import urlencode

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from curl_cffi import requests as hc
    _HAVE_CFFI = True
except Exception:
    hc = requests
    _HAVE_CFFI = False

from signer_client import signer, AID, VERSION_CODE, VERSION_NAME

BASE = Path(__file__).resolve().parent
COUNT_FILE = BASE / "viewcounts.json"
LOG_FILE = BASE / "viewcounts.log"
CAMPAIGNS_FILE = BASE / "campaigns.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

DETAIL_HOSTS = [
    "https://api16-normal-c-useast1a.tiktokv.com",
    "https://api22-normal-c-useast2a.tiktokv.com",
    "https://api16-normal-c-alisg.tiktokv.com",
    "https://api.tiktokv.com",
]


def to_id(s: str) -> str:
    m = re.search(r"/video/(\d{15,20})", s or "") or re.search(r"(\d{18,19})", s or "")
    return m.group(1) if m else (s or "").strip()


# --- source 1: livecounts ------------------------------------------------
def via_livecounts(item_id: str):
    headers = {
        "authority": "tiktok.livecounts.io",
        "origin": "https://livecounts.io",
        "referer": "https://livecounts.io/",
        "accept": "application/json, text/plain, */*",
        "user-agent": UA,
    }
    for attempt in range(2):
        try:
            r = requests.get(f"https://tiktok.livecounts.io/video/stats/{item_id}",
                             headers=headers, timeout=15)
            if r.status_code == 200:
                d = r.json()
                for k in ("playCount", "play_count", "viewCount", "views", "view_count"):
                    if k in d:
                        return int(d[k]), "livecounts"
        except Exception:
            pass
        time.sleep(1.5)
    return None, "livecounts"


# --- source 2: TikTok's own API (signed) ---------------------------------
def via_api(item_id: str):
    params = {
        "aid": AID, "app_name": "musical_ly", "channel": signer.channel,
        "device_platform": "android", "device_type": signer.device_type,
        "device_brand": signer.device_brand,
        "device_id": signer.device_id or "".join(str((i * 7) % 10) for i in range(19)),
        "openudid": signer.openudid, "iid": signer.iid,
        "os_version": signer.os_version, "os_api": signer.os_api,
        "version_code": VERSION_CODE, "version_name": VERSION_NAME,
        "aweme_id": item_id,
    }
    qs = urlencode(params)
    headers = {"user-agent": signer.ua, "accept-encoding": "gzip"}
    headers.update(signer.sign(qs, params, device_id=params["device_id"]))

    for host in DETAIL_HOSTS:
        try:
            url = f"{host}/aweme/v1/aweme/detail/?{qs}"
            if _HAVE_CFFI:
                r = hc.get(url, headers=headers, timeout=12,
                           impersonate="chrome", verify=False)
            else:
                r = requests.get(url, headers=headers, timeout=12, verify=False)
            if r.status_code != 200 or len(r.content) < 20:
                continue
            d = r.json()
            detail = d.get("aweme_detail") or {}
            stats = detail.get("statistics") or {}
            pc = stats.get("play_count")
            if pc is not None:
                return int(pc), f"api:{host.split('//')[1]}"
        except Exception:
            continue
    return None, "api"


def counter(item_id: str):
    val, src = via_livecounts(item_id)
    if val is not None:
        return val, src
    val, src = via_api(item_id)
    return val, src


# --- state ---------------------------------------------------------------
def load_counts() -> dict:
    if COUNT_FILE.exists():
        try:
            return json.loads(COUNT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_counts(d: dict) -> None:
    COUNT_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def load_targets():
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
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--watch", type=int, default=0)
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
        print(f"    {'campaign':<30}{'now':>12}{'last':>12}{'session':>12}  source")
        print("    " + "-" * 74)
        for name, vid in pairs:
            now, src = counter(vid)
            if now is None:
                print(f"    {name[:29]:<30}{'ERR':>12}{'-':>12}{'-':>12}  {src}")
                continue
            prev = counts.get(vid, now)
            if vid not in session_start:
                session_start[vid] = now
            print(f"    {name[:29]:<30}{now:>12,}{now - prev:>+12,}"
                  f"{now - session_start[vid]:>+12,}  {src}")
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