from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class HTTPError(RuntimeError):
    pass


@dataclass(slots=True)
class HTTPClient:
    user_agent: str = "research-digest/0.1 (+local)"
    timeout: int = 20

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        request = urllib.request.Request(url, headers=self._headers(headers))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise HTTPError(f"GET failed for {url}: {exc}") from exc

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        return json.loads(self.get_text(url, headers=headers))

    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
        body = json.dumps(payload).encode("utf-8")
        merged = self._headers(headers)
        merged["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=merged, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read().decode(charset, errors="replace")
                return json.loads(raw) if raw else {}
        except (urllib.error.URLError, TimeoutError) as exc:
            raise HTTPError(f"POST failed for {url}: {exc}") from exc

    def build_url(self, base: str, params: dict[str, Any]) -> str:
        clean = {key: value for key, value in params.items() if value not in (None, "")}
        return base + "?" + urllib.parse.urlencode(clean, doseq=True)

    def _headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if extra:
            headers.update(extra)
        return headers
