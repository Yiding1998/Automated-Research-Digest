from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any


@dataclass(slots=True)
class DigestItem:
    source: str
    kind: str
    title: str
    url: str
    published: datetime | None = None
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def fingerprint(self) -> str:
        key = str(self.metadata.get("fingerprint_key") or self.url.strip().lower() or f"{self.source}:{self.title}".lower())
        return sha256(key.encode("utf-8", errors="ignore")).hexdigest()

    def text_blob(self) -> str:
        return " ".join(
            part
            for part in [
                self.title,
                self.summary,
                self.venue,
                " ".join(self.authors),
                " ".join(str(v) for v in self.metadata.values()),
            ]
            if part
        )
