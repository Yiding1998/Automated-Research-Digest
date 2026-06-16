from __future__ import annotations

from datetime import UTC, datetime

from .models import DigestItem
from .utils import keyword_hit_count


KIND_WEIGHTS = {
    "paper": 30.0,
    "conference": 22.0,
    "news": 12.0,
    "feed": 10.0,
}


def filter_and_score(items: list[DigestItem], keywords: list[str], exclude_keywords: list[str]) -> list[DigestItem]:
    scored: list[DigestItem] = []
    now = datetime.now(UTC)
    excludes = [keyword.lower() for keyword in exclude_keywords if keyword.strip()]

    for item in items:
        text = item.text_blob().lower()
        if any(exclude in text for exclude in excludes):
            continue
        hits = keyword_hit_count(text, keywords)
        if hits == 0 and item.kind not in {"conference", "news"}:
            continue

        item.score = KIND_WEIGHTS.get(item.kind, 8.0) + hits * 8.0
        if item.published:
            age_days = max((now - item.published).days, 0)
            item.score += max(0.0, 10.0 - age_days)
        if "citation_count" in item.metadata:
            try:
                item.score += min(float(item.metadata["citation_count"]) / 10.0, 10.0)
            except (TypeError, ValueError):
                pass
        scored.append(item)

    return sorted(scored, key=lambda item: (item.score, item.published or datetime.min.replace(tzinfo=UTC)), reverse=True)
