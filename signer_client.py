"""
signer_client.py
In-process TikTok signer on top of `tiktok-signer` (iqbalmh18), with a STABLE
DeviceProfile persisted to disk.

Critical: TikTok binds X-Argus to a device. The device_id / openudid / cdid in the
query string MUST be the same values the signer used. This module owns the device
and exposes it, so the bot never invents its own.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

try:
    from tiktok_signer import TikTokSigner, DeviceProfile
    HAVE_SIGNER = True
except Exception:
    HAVE_SIGNER = False

DEVICE_FILE = Path(__file__).resolve().parent / "device-profile.json"

# App identity — MUST match the signer defaults so signatures verify.
AID = 1233
VERSION_NAME = "37.0.4"
VERSION_CODE = 2023700040
USER_AGENT = (
    "com.zhiliaoapp.musically/2023700040 "
    "(Linux; U; Android 9; in_ID; 2203121C; Build/PQ3A.190705.09121607;"
    "tt-ok/3.12.13.4-tiktok)"
)


class SignerClient:
    def __init__(self) -> None:
        self.available = HAVE_SIGNER
        self.ua = USER_AGENT
        self.device_id = ""
        self.openudid = ""
        self.cdid = ""
        self.iid = ""
        self.device_type = "2203121C"
        self.device_brand = "Xiaomi"
        self.os_version = "9"
        self.os_api = "28"
        self.channel = "googleplay"
        if HAVE_SIGNER:
            self._load_device()

    def _load_device(self) -> None:
        data: dict = {}
        if DEVICE_FILE.exists():
            try:
                data = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        if not data:
            data = {
                "device_id": str(random.randint(10**18, 10**19 - 1)),
                "iid": str(random.randint(7 * 10**18, 8 * 10**18)),
                "device_type": self.device_type,
                "device_brand": self.device_brand,
                "os_version": self.os_version,
                "os_api": self.os_api,
                "channel": self.channel,
            }
            try:
                DEVICE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        profile = DeviceProfile(
            device_id=data["device_id"],
            device_type=data.get("device_type", self.device_type),
            os_version=data.get("os_version", self.os_version),
            channel=data.get("channel", self.channel),
        )
        TikTokSigner.set_device(profile)          # ONE stable device for the session

        self.device_id = data["device_id"]
        self.iid = data["iid"]
        self.device_type = data.get("device_type", self.device_type)
        self.device_brand = data.get("device_brand", self.device_brand)
        self.os_version = data.get("os_version", self.os_version)
        self.os_api = data.get("os_api", self.os_api)
        self.channel = data.get("channel", self.channel)
        self.openudid = getattr(profile, "openudid", "") or ""
        self.cdid = getattr(profile, "cdid", "") or ""

    def sign(self, qs: str, params: dict, data=None, device_id: Optional[str] = None) -> dict:
        if not HAVE_SIGNER:
            return {}
        try:
            h = TikTokSigner.generate_headers(
                params=qs, data=data, aid=AID,
                device_id=device_id or None,          # ← per-request device
                version_name=VERSION_NAME, version_code=VERSION_CODE,
            )
            return {k: v for k, v in h.items() if isinstance(v, str)}
        except Exception:
            return {}


signer = SignerClient()