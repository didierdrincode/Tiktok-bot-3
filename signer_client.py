from __future__ import annotations
import httpx
from typing import Dict, Any

class TikTokSigner:
    def __init__(self, signer_url: str = "http://localhost:8080/sign"):
        self.signer_url = signer_url
        self.client = httpx.Client(timeout=5.0)

    def get_signed_params(self, endpoint_url: str, params: Dict[Any, Any]) -> Dict[str, Any]:
        """
        Sends the target URL and raw parameters to the local/remote WASM signer service
        to generate valid TikTok security tokens (_signature, X-Bogus, etc.).
        """
        try:
            response = self.client.post(
                self.signer_url,
                json={"url": endpoint_url, "params": params}
            )
            if response.status_code == 200:
                data = response.json()
                # Returns the fully signed parameters including cryptographic tokens
                return data.get("signed_params", params)
        except Exception as e:
            print(f"[!] Signer service error: {e}")
        
        # Fallback to unsigned parameters if signer fails
        return params

    def close(self):
        self.client.close()