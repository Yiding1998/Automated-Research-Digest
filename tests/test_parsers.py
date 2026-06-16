from __future__ import annotations

import unittest
from datetime import UTC, datetime

from research_digest.scoring import filter_and_score
from research_digest.models import DigestItem
from research_digest.sources import _parse_conference_alerts, _parse_rss


class ParserTests(unittest.TestCase):
    def test_parse_rss_item(self) -> None:
        xml = """<?xml version="1.0"?>
        <rss><channel><item>
        <title>New paper on AI agents</title>
        <link>https://example.com/paper</link>
        <pubDate>Tue, 16 Jun 2026 10:00:00 GMT</pubDate>
        <description>This paper studies multi-agent systems.</description>
        </item></channel></rss>"""
        items = _parse_rss(xml, "Example", "paper", datetime(2026, 6, 1, tzinfo=UTC))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "New paper on AI agents")
        self.assertEqual(items[0].kind, "paper")

    def test_parse_conference_alerts(self) -> None:
        html = """
        <h2 class="h5">June 2026</h2>
        <div class="py-2 border-bottom"><div><div>
        <div style="min-width:70px;">19th</div>
        <div><a href="show-event?id=1">International Conference on AI Agents</a>
        <span><span>Tokyo</span>, <span>Japan</span></span></div>
        <div><span class="badge">in-person</span></div>
        </div></div></div>
        """
        items = _parse_conference_alerts(html, 2026)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "International Conference on AI Agents")
        self.assertEqual(items[0].published, datetime(2026, 6, 19, tzinfo=UTC))

    def test_filter_and_score_excludes(self) -> None:
        xml = """<rss><channel><item>
        <title>AI agents job opening</title>
        <link>https://example.com/job</link>
        <description>Advertisement</description>
        </item></channel></rss>"""
        items = _parse_rss(xml, "Example", "news", datetime(2026, 6, 1, tzinfo=UTC))
        scored = filter_and_score(items, ["AI agents"], ["job opening"])
        self.assertEqual(scored, [])

    def test_fingerprint_can_use_metadata_key(self) -> None:
        base = DigestItem(source="test", kind="feed", title="Same", url="https://example.com")
        changed = DigestItem(
            source="test",
            kind="feed",
            title="Same",
            url="https://example.com",
            metadata={"fingerprint_key": "https://example.com#changed"},
        )
        self.assertNotEqual(base.fingerprint(), changed.fingerprint())


if __name__ == "__main__":
    unittest.main()
