"""
signer_client.py
In-process TikTok signer (SignerPy) with OPTIONAL external HTTP signer fallback.
No localhost service required. Set SIGNER_URL env to use an external signer.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from SignerPy import sign as _sp_sign
    HAVE_SIGNER = True
except Exception:
    HAVE_SIGNER = False

try:
    import httpx
    _HAVE_HTTP = True
except Exception:
    _HAVE_HTTP = False


class TikTokSigner:
    def __init__(self, signer_url: Optional[str] = None):
        self.signer_url = signer_url or os.getenv("SIGNER_URL", "").strip()
        self._client = None
        self._mode = None
        self.available = HAVE_SIGNER or bool(self.signer_url)

    def sign(self, qs: str, params: dict) -> dict:
        """Return signing headers (x-gorgon/x-ladon/x-argus/x-khronos/x-ss-stub)."""
        # 1) external HTTP signer if configured
        if self.signer_url and _HAVE_HTTP:
            try:
                if self._client is None:
                    self._client = httpx.Client(timeout=5.0)
                r = self._client.post(self.signer_url, json={"url": qs, "params": params})
                if r.status_code == 200:
                    data = r.json()
                    out = data.get("signed_params") or data.get("headers") or {}
                    out = {k: v for k, v in out.items() if isinstance(v, str)}
                    if out:
                        return out
            except Exception:
                pass

        # 2) in-process SignerPy (default)
        if HAVE_SIGNER:
            for mode, arg in (("str", qs), ("dict", params)):
                if self._mode and mode != self._mode:
                    continue
                try:
                    sig = _sp_sign(params=arg, payload=None, version=8404)
                    self._mode = mode
                    return {k: v for k, v in sig.items() if isinstance(v, str)}
                except Exception:
                    continue
        return {}

    def close(self):
        if self._client:
            self._client.close()


# module-level singleton used by the bot
signer = TikTokSigner()