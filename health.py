"""
health.py
Probes candidate hosts and proxies; keeps only endpoints that return a REAL body.
"""
from __future__ import annotations

import concurrent.futures as futures
import random
from urllib.parse import urlencode

import requests

from config import REQUEST_TIMEOUT, DEVICE_POOL
from signer_client import signer

STATS_PATH = "/aweme/v1/aweme/stats/"
PROBE_ITEM = "7123456789012345678"
MIN_BODY = 4


def _params(item_id: str) -> dict:
    dev = random.choice(DEVICE_POOL)
    return {
        "aid": 1988, "channel": "googleplay",
        "device_type": dev["device_type"], "device_brand": dev["device_brand"],
        "device_id": random.randint(10**18, 10**19 - 1),
        "os_version": dev["os_version"], "os_api": dev["os_api"],
        "version_code": 250103, "app_name": "musical_ly",
        "device_platform": "android",
        "openudid": "".join(random.choice("0123456789abcdef") for _ in range(16)),
        "iid": random.randint(7 * 10**18, 8 * 10**18),
        "item_id": item_id, "play_delta": 1, "digg_delta": 0, "share_delta": 0,
    }


def probe(host: str, proxy=None, item_id: str = PROBE_ITEM):
    """Return (ok, note). ok=True only when a non-empty body comes back."""
    p = _params(item_id)
    qs = urlencode(p)
    headers = {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "user-agent": random.choice(DEVICE_POOL)["ua"],
        "accept-encoding": "gzip",
        "connection": "close",
    }
    headers.update(signer.sign(qs, p))
    try:
        r = requests.post(f"{host}{STATS_PATH}?{qs}", headers=headers, proxies=proxy,
                          timeout=REQUEST_TIMEOUT, verify=False)
    except Exception as e:
        return False, type(e).__name__
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}"
    if len(r.content) < MIN_BODY:
        return False, "empty"
    try:
        code = r.json().get("status_code")
    except Exception:
        return False, "non-json"
    return (True, "ok") if code == 0 else (False, f"status_code={code}")


def live_hosts(hosts: list[str], workers: int = 8) -> list[str]:
    out = []
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        fmap = {ex.submit(probe, h): h for h in hosts}
        for f in futures.as_completed(fmap):
            ok, _ = f.result()
            if ok:
                out.append(fmap[f])
    return out


def live_proxies(pool: list[dict], host: str, workers: int = 48) -> list[dict]:
    out = []
    if not pool:
        return out
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        fmap = {ex.submit(probe, host, p): p for p in pool}
        for f in futures.as_completed(fmap):
            ok, _ = f.result()
            if ok:
                out.append(fmap[f])
    return out