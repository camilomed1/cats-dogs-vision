"""HTTP client for the Flask API. Images are sent as base64 + metadata, like the other clients."""
import base64

import requests


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method, path, timeout=15, **kwargs):
        try:
            r = requests.request(method, self.base_url + path, timeout=timeout, **kwargs)
        except requests.ConnectionError:
            raise ApiError("Cannot reach the server. Is the Flask backend running?")
        except requests.Timeout:
            raise ApiError("The server took too long to answer.")
        if not r.ok:
            try:
                message = r.json().get("error")
            except ValueError:
                message = None
            raise ApiError(message or f"Server error ({r.status_code})")
        return r

    def health(self) -> dict:
        return self._request("GET", "/api/health", timeout=3).json()

    def predict(self, image_bytes: bytes, metadata: dict, store: bool = True) -> dict:
        body = {
            "image": base64.b64encode(image_bytes).decode("ascii"),
            "metadata": {"client": "desktop", **metadata},
            "store": store,
        }
        return self._request("POST", "/api/predict", json=body).json()

    def history(self, limit: int = 100, client: str = "") -> list:
        params = {"limit": limit, **({"client": client} if client else {})}
        return self._request("GET", "/api/history", params=params).json()

    def delete(self, prediction_id: str) -> None:
        self._request("DELETE", f"/api/predictions/{prediction_id}")

    def image(self, image_url: str) -> bytes:
        """image_url is the relative path returned by the API, e.g. /api/images/<id>."""
        return self._request("GET", image_url).content
