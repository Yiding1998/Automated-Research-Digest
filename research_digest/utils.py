from __future__ import annotations

import email.utils
import html
import re
from datetime import UTC, datetime
from html.parser import HTMLParser


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_map = dict(attrs)
            self._href = attrs_map.get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = clean_text(" ".join(self._text))
            if text:
                self.links.append((self._href, text))
            self._href = None
            self._text = []


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    parsers = [
        _parse_iso,
        _parse_rfc2822,
        _parse_crossref_parts,
    ]
    for parser in parsers:
        parsed = parser(value)
        if parsed is not None:
            return parsed
    return None


def split_sentences(text: str, limit: int = 2) -> str:
    text = clean_text(text)
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:limit]).strip()


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    low = text.lower()
    return sum(1 for keyword in keywords if keyword.strip('"').lower() in low)


def _parse_iso(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def _parse_rfc2822(value: str) -> datetime | None:
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_crossref_parts(value: str) -> datetime | None:
    try:
        parts = [int(part) for part in value.split("-")]
        while len(parts) < 3:
            parts.append(1)
        return datetime(parts[0], parts[1], parts[2], tzinfo=UTC)
    except (ValueError, IndexError):
        return None
