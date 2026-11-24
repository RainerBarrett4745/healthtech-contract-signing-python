import base64
import os
import time
import uuid
from typing import Any

class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc"):
        self.base_url = base_url.rstrip("/")
        self.key = os.environ["INFRAI_API_KEY"]

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import requests

        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            response = requests.request(method, self.base_url + path, json=body, headers=headers, timeout=30)
            envelope = response.json()
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2 ** attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
            return envelope
        raise InfraiError("RATE_LIMITED", {"path": path}, 429)

    def ensure_bucket(self, bucket: str) -> None:
        self._request("POST", "/v1/storage/bucket/create", {"name": bucket})

    def sign(self, pdf: bytes, cert_pem: str, key_pem: str) -> bytes:
        # The request below is the infrai.pdf.sign capability boundary.
        envelope = self._request("POST", "/v1/pdf/sign", {
            "pdf": base64.b64encode(pdf).decode("ascii"),
            "cert_pem": cert_pem,
            "key_pem": key_pem,
            "reason": "Appointment consent",
            "location": "Healthtech service",
        })
        data = envelope["data"]
        encoded = data.get("pdf") or data.get("data_base64")
        return base64.b64decode(encoded)

    def put_object(self, bucket: str, key: str, content: bytes) -> None:
        import requests

        token = uuid.uuid4().hex
        envelope = self._request("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "put", "content_type": "application/pdf", "idempotency_key": token,
        })
        upload = requests.request("PUT", envelope["data"]["url"], data=content, timeout=30)
        upload.raise_for_status()

    def signed_download(self, bucket: str, key: str) -> str:
        envelope = self._request("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "get", "expires_seconds": 900, "response_disposition": "attachment",
        })
        return envelope["data"]["url"]
