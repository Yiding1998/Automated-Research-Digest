from __future__ import annotations

from typing import Any

from .config import env_value
from .http import HTTPClient
from .models import DigestItem
from .utils import split_sentences


def summarize(items: list[DigestItem], config: dict[str, Any], errors: list[str], language: str | None = None) -> str:
    settings = config.get("summarization", {})
    mode = settings.get("mode", "local")
    target_language = language or settings.get("language", "English")
    if mode == "openai":
        try:
            return _openai_summary(items, config, errors, target_language)
        except Exception as exc:  # noqa: BLE001 - fallback is intentional
            fallback_errors = errors if str(exc) == "missing API key" else [*errors, f"openai summary fallback: {exc}"]
            return _local_summary(items, config, fallback_errors, target_language)
    return _local_summary(items, config, errors, target_language)


def _local_summary(items: list[DigestItem], config: dict[str, Any], errors: list[str], language: str) -> str:
    profile = config.get("profile", {})
    settings = config.get("summarization", {})
    max_highlights = int(settings.get("max_highlights", 8))
    zh = _is_chinese(language)
    labels = _labels(zh)
    lines = [
        f"# {profile.get('name', 'Research Digest')}",
        "",
        labels["found"].format(count=len(items)),
        "",
        f"## {labels['highlights']}",
        "",
    ]
    if not items:
        lines.extend([labels["no_items"], ""])
    for index, item in enumerate(items[:max_highlights], start=1):
        date = item.published.date().isoformat() if item.published else labels["date_unknown"]
        reason = split_sentences(item.summary, limit=1) or item.venue or item.source
        lines.append(f"{index}. [{item.title}]({item.url})")
        kind_name = labels["kind_names"].get(item.kind, item.kind)
        lines.append(f"   - {item.source} | {kind_name} | {date} | {labels['score']} {item.score:.1f}")
        if item.authors:
            lines.append(f"   - {labels['authors']}: {', '.join(item.authors[:6])}")
        if item.venue:
            lines.append(f"   - {labels['venue']}: {item.venue}")
        if reason:
            lines.append(f"   - {labels['note']}: {reason}")
        lines.append("")

    grouped = _group_by_kind(items)
    for kind in ("paper", "conference", "news", "feed"):
        group = grouped.get(kind, [])
        if not group:
            continue
        section = labels["kind_sections"].get(kind, f"{kind.title()} Items")
        lines.extend([f"## {section}", ""])
        for item in group:
            date = item.published.date().isoformat() if item.published else labels["date_unknown"]
            lines.append(f"- [{item.title}]({item.url}) - {item.source}, {date}")
        lines.append("")

    if errors:
        lines.extend([f"## {labels['warnings']}", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _openai_summary(items: list[DigestItem], config: dict[str, Any], errors: list[str], language: str) -> str:
    settings = config.get("summarization", {}).get("openai", {})
    key = env_value(settings.get("api_key_env"))
    if not key:
        raise RuntimeError("missing API key")

    payload_items = []
    for item in items[:50]:
        payload_items.append(
            {
                "title": item.title,
                "source": item.source,
                "kind": item.kind,
                "url": item.url,
                "published": item.published.date().isoformat() if item.published else "",
                "venue": item.venue,
                "authors": item.authors[:8],
                "summary": item.summary[:1200],
                "score": round(item.score, 1),
            }
        )
    prompt = (
        f"Write a concise research intelligence digest in {language}. "
        "Prioritize novelty, relevance, and why the reader should care. "
        "Use Markdown. Include sections: Executive Summary, Important Papers, Conferences/CFPs, News, Watchlist. "
        f"In Important Papers, include up to {config.get('summarization', {}).get('max_highlights', 8)} relevant papers when available; "
        "do not collapse a long time window into only a few papers unless only a few are truly relevant. "
        "Every item must preserve its URL. Avoid hype.\n\n"
        f"Items: {payload_items}\nWarnings: {errors}"
    )
    payload: dict[str, Any] = {
        "model": settings.get("model", "gpt-4.1-mini"),
        "messages": [
            {"role": "system", "content": "You are a careful research analyst."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    if settings.get("max_completion_tokens"):
        payload["max_completion_tokens"] = int(settings["max_completion_tokens"])
    if settings.get("disable_thinking", False):
        payload["thinking"] = {"type": "disabled"}

    client = HTTPClient(timeout=int(settings.get("timeout_seconds", 60)))
    response = client.post_json(
        str(settings.get("base_url", "https://api.openai.com/v1/chat/completions")),
        payload,
        headers={"Authorization": f"Bearer {key}"},
    )
    return response["choices"][0]["message"]["content"].strip() + "\n"


def _group_by_kind(items: list[DigestItem]) -> dict[str, list[DigestItem]]:
    grouped: dict[str, list[DigestItem]] = {}
    for item in items:
        grouped.setdefault(item.kind, []).append(item)
    return grouped


def _is_chinese(language: str) -> bool:
    normalized = language.lower()
    return normalized in {"zh", "zh-cn", "chinese", "中文", "简体中文"}


def _labels(zh: bool) -> dict[str, Any]:
    if not zh:
        return {
            "found": "Found {count} new or matching items.",
            "highlights": "Highlights",
            "no_items": "No new matching items found.",
            "date_unknown": "date unknown",
            "score": "score",
            "authors": "Authors",
            "venue": "Venue",
            "note": "Note",
            "warnings": "Source Warnings",
            "kind_names": {
                "paper": "paper",
                "conference": "conference",
                "news": "news",
                "feed": "feed",
            },
            "kind_sections": {
                "paper": "Paper Items",
                "conference": "Conference Items",
                "news": "News Items",
                "feed": "Feed Items",
            },
        }
    return {
        "found": "找到 {count} 条新的或匹配的动态。",
        "highlights": "重点摘要",
        "no_items": "没有发现新的匹配条目。",
        "date_unknown": "日期未知",
        "score": "相关度",
        "authors": "作者",
        "venue": "来源/会议/期刊",
        "note": "要点",
        "warnings": "数据源提醒",
        "kind_names": {
            "paper": "论文",
            "conference": "会议/征稿",
            "news": "新闻",
            "feed": "订阅源",
        },
        "kind_sections": {
            "paper": "论文条目",
            "conference": "会议/征稿条目",
            "news": "新闻条目",
            "feed": "订阅源条目",
        },
    }
