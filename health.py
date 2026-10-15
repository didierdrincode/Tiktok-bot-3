"""
health.py — probes hosts/proxies with the SAME signing + TLS stack as the bot.
"""
from __future__ import annotations

import concurrent.futures as futures
from urllib.parse import urlencode

try:
    from curl_cffi import requests as hc
    _HAVE_CFFI = True
except Exception:
    import requests as hc
    _HAVE_CFFI = False

from config import REQUEST_TIMEOUT
from signer_client import signer, AID, VERSION_CODE, VERSION_NAME

STATS_PATH = "/aweme/v1/aweme/stats/"
PROBE_ITEM = "7123456789012345678"
MIN_BODY = 4


def _params(item_id: str) -> dict:
    return {
        "aid": AID, "app_name": "musical_ly", "channel": signer.channel,
        "device_platform": "android", "device_type": signer.device_type,
        "device_brand": signer.device_brand, "device_id": signer.device_id,
        "openudid": signer.openudid, "iid": signer.iid,
        "os_version": signer.os_version, "os_api": signer.os_api,
        "version_code": VERSION_CODE, "version_name": VERSION_NAME,
        "item_id": item_id, "play_delta": 1, "digg_delta": 0, "share_delta": 0,
    }


def _post(url, headers, proxy):
    if _HAVE_CFFI:
        return hc.post(url, headers=headers, proxies=proxy, timeout=REQUEST_TIMEOUT,
                       impersonate="chrome", verify=False)
    return hc.post(url, headers=headers, proxies=proxy,
                   timeout=REQUEST_TIMEOUT, verify=False)


def probe(host: str, proxy=None, item_id: str = PROBE_ITEM):
    p = _params(item_id)
    qs = urlencode(p)
    headers = {
        "user-agent": signer.ua,
        "accept-encoding": "gzip",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    headers.update(signer.sign(qs, p))
    try:
        r = _post(f"{host}{STATS_PATH}?{qs}", headers, proxy)
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
            if f.result()[0]:
                out.append(fmap[f])
    return out


def live_proxies(pool: list[dict], host: str, workers: int = 48) -> list[dict]:
    out = []
    if not pool:
        return out
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        fmap = {ex.submit(probe, host, p): p for p in pool}
        for f in futures.as_completed(fmap):
            if f.result()[0]:
                out.append(fmap[f])
    return out