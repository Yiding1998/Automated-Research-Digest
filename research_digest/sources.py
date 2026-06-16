from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from hashlib import sha256
from datetime import UTC, datetime
from typing import Any

from .http import HTTPClient
from .models import DigestItem
from .utils import LinkExtractor, clean_text, parse_datetime, split_sentences


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch_all(config: dict[str, Any], since: datetime) -> tuple[list[DigestItem], list[str]]:
    client = HTTPClient(
        user_agent=str(config.get("run", {}).get("user_agent", "research-digest/0.1 (+local)")),
        timeout=int(config.get("run", {}).get("timeout_seconds", 20)),
    )
    keywords = list(config["profile"]["keywords"])
    sources = config.get("sources", {})
    errors: list[str] = []
    items: list[DigestItem] = []

    source_calls = [
        ("arxiv", fetch_arxiv),
        ("crossref", fetch_crossref),
        ("semantic_scholar", fetch_semantic_scholar),
        ("pubmed", fetch_pubmed),
        ("google_news", fetch_google_news),
        ("google_search", fetch_google_search),
        ("conference_alerts", fetch_conference_alerts),
        ("wikicfp", fetch_wikicfp),
        ("watched_pages", fetch_watched_pages),
        ("rss", fetch_rss),
    ]

    for name, fetcher in source_calls:
        settings = sources.get(name, {})
        if name == "rss":
            enabled = bool(settings.get("enabled", bool(settings.get("feeds"))) and settings.get("feeds"))
        else:
            enabled = bool(settings.get("enabled", False))
        if not enabled:
            continue
        try:
            items.extend(fetcher(client, keywords, settings, since))
        except Exception as exc:  # noqa: BLE001 - one broken source should not stop a digest
            errors.append(f"{name}: {exc}")
    return items, errors


def fetch_arxiv(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    terms = [_arxiv_term(keyword) for keyword in keywords]
    query = " OR ".join(terms)
    categories = [str(category) for category in settings.get("categories", [])]
    if categories:
        query = f"({query}) AND ({' OR '.join('cat:' + category for category in categories)})"
    url = client.build_url(
        "https://export.arxiv.org/api/query",
        {
            "search_query": query,
            "start": 0,
            "max_results": int(settings.get("max_results", 10)),
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        },
    )
    root = ET.fromstring(client.get_text(url))
    items: list[DigestItem] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        updated = parse_datetime(_find_text(entry, "atom:updated")) or parse_datetime(_find_text(entry, "atom:published"))
        if updated and updated < since:
            continue
        title = clean_text(_find_text(entry, "atom:title"))
        summary = clean_text(_find_text(entry, "atom:summary"))
        link = ""
        pdf_url = ""
        for link_el in entry.findall("atom:link", ATOM_NS):
            rel = link_el.attrib.get("rel", "")
            href = link_el.attrib.get("href", "")
            if rel == "alternate":
                link = href
            if link_el.attrib.get("title") == "pdf":
                pdf_url = href
        authors = [clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS)) for author in entry.findall("atom:author", ATOM_NS)]
        category = entry.find("arxiv:primary_category", ATOM_NS)
        items.append(
            DigestItem(
                source="arXiv",
                kind="paper",
                title=title,
                url=link or pdf_url,
                published=updated,
                authors=[author for author in authors if author],
                venue=category.attrib.get("term", "") if category is not None else "arXiv",
                summary=split_sentences(summary, limit=3),
                metadata={"pdf_url": pdf_url},
            )
        )
    return items


def fetch_crossref(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    query = " OR ".join(keywords)
    url = client.build_url(
        "https://api.crossref.org/works",
        {
            "query.bibliographic": query,
            "filter": f"from-pub-date:{since.date().isoformat()},until-pub-date:{datetime.now(UTC).date().isoformat()}",
            "sort": "published",
            "order": "desc",
            "rows": int(settings.get("max_results", 10)),
        },
    )
    payload = client.get_json(url)
    items: list[DigestItem] = []
    for record in payload.get("message", {}).get("items", []):
        title = clean_text(_first(record.get("title")))
        if not title:
            continue
        published = _crossref_date(record)
        if published and published < since:
            continue
        authors = [
            clean_text(" ".join(part for part in [author.get("given", ""), author.get("family", "")] if part))
            for author in record.get("author", [])[:8]
        ]
        doi = record.get("DOI", "")
        url_value = record.get("URL", "") or (f"https://doi.org/{doi}" if doi else "")
        items.append(
            DigestItem(
                source="Crossref",
                kind="paper",
                title=title,
                url=url_value,
                published=published,
                authors=[author for author in authors if author],
                venue=clean_text(_first(record.get("container-title"))) or clean_text(record.get("publisher", "")),
                summary=split_sentences(clean_text(record.get("abstract", "")), limit=3),
                metadata={"doi": doi, "type": record.get("type", "")},
            )
        )
    return items


def fetch_semantic_scholar(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    items: list[DigestItem] = []
    api_key = _env_value(settings.get("api_key_env"))
    headers = {"x-api-key": api_key} if api_key else None
    per_query = max(1, int(settings.get("max_results", 10)) // max(1, len(keywords)))
    for keyword in keywords:
        url = client.build_url(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            {
                "query": keyword,
                "limit": per_query,
                "fields": "title,abstract,year,authors,url,venue,publicationDate,citationCount,externalIds",
            },
        )
        payload = client.get_json(url, headers=headers)
        for paper in payload.get("data", []):
            published = parse_datetime(paper.get("publicationDate"))
            if published and published < since:
                continue
            if not published and paper.get("year") and int(paper["year"]) < since.year:
                continue
            authors = [clean_text(author.get("name", "")) for author in paper.get("authors", [])[:8]]
            external_ids = paper.get("externalIds") or {}
            url_value = paper.get("url") or (f"https://doi.org/{external_ids.get('DOI')}" if external_ids.get("DOI") else "")
            items.append(
                DigestItem(
                    source="Semantic Scholar",
                    kind="paper",
                    title=clean_text(paper.get("title", "")),
                    url=url_value,
                    published=published,
                    authors=[author for author in authors if author],
                    venue=clean_text(paper.get("venue", "")),
                    summary=split_sentences(paper.get("abstract", ""), limit=3),
                    metadata={"citation_count": paper.get("citationCount", 0), "query": keyword},
                )
            )
    return items[: int(settings.get("max_results", 10))]


def fetch_pubmed(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    query = " OR ".join(f'"{keyword}"' for keyword in keywords)
    esearch = client.build_url(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": int(settings.get("max_results", 10)),
            "sort": "pub+date",
            "datetype": "pdat",
            "mindate": since.date().isoformat(),
            "maxdate": datetime.now(UTC).date().isoformat(),
        },
    )
    ids = client.get_json(esearch).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    efetch = client.build_url(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
    )
    root = ET.fromstring(client.get_text(efetch))
    items: list[DigestItem] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = clean_text(article.findtext(".//PMID", default=""))
        title = clean_text(article.findtext(".//ArticleTitle", default=""))
        abstract = " ".join(clean_text(el.text or "") for el in article.findall(".//AbstractText"))
        journal = clean_text(article.findtext(".//Journal/Title", default="PubMed"))
        authors = []
        for author in article.findall(".//Author")[:8]:
            name = clean_text(" ".join(part for part in [author.findtext("ForeName", ""), author.findtext("LastName", "")] if part))
            if name:
                authors.append(name)
        published = _pubmed_date(article)
        if published and published < since:
            continue
        items.append(
            DigestItem(
                source="PubMed",
                kind="paper",
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                published=published,
                authors=authors,
                venue=journal,
                summary=split_sentences(abstract, limit=3),
                metadata={"pmid": pmid},
            )
        )
    return items


def fetch_google_news(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    items: list[DigestItem] = []
    language = settings.get("language", "en-US")
    country = settings.get("country", "US")
    for keyword in keywords:
        query = f"{keyword} when:{max(1, (datetime.now(UTC) - since).days)}d"
        url = client.build_url(
            "https://news.google.com/rss/search",
            {"q": query, "hl": language, "gl": country, "ceid": f"{country}:en"},
        )
        items.extend(_parse_rss(client.get_text(url), source="Google News", default_kind="news", since=since))
    return items[: int(settings.get("max_results", 10))]


def fetch_google_search(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    api_key = _env_value(settings.get("api_key_env"))
    cx = _env_value(settings.get("cx_env"))
    if not api_key or not cx:
        raise RuntimeError("missing Google Custom Search API key or cx")

    queries = [str(query) for query in settings.get("queries", []) if str(query).strip()]
    if not queries:
        queries = [" ".join(keywords)]

    per_query = min(10, max(1, int(settings.get("results_per_query", 5))))
    max_results = int(settings.get("max_results", 20))
    days = max(1, (datetime.now(UTC) - since).days)
    date_restrict = str(settings.get("date_restrict", f"d{days}"))
    items: list[DigestItem] = []

    for query in queries:
        url = client.build_url(
            "https://www.googleapis.com/customsearch/v1",
            {
                "key": api_key,
                "cx": cx,
                "q": query,
                "num": per_query,
                "dateRestrict": date_restrict,
            },
        )
        payload = client.get_json(url)
        for result in payload.get("items", []):
            link = str(result.get("link", ""))
            title = clean_text(result.get("title", ""))
            snippet = clean_text(result.get("snippet", ""))
            published = _google_search_date(result)
            if published and published < since:
                continue
            items.append(
                DigestItem(
                    source="Google Search",
                    kind=str(settings.get("kind", "feed")),
                    title=title,
                    url=link,
                    published=published,
                    venue=clean_text(result.get("displayLink", "")),
                    summary=snippet,
                    metadata={"query": query},
                )
            )
            if len(items) >= max_results:
                return items
    return items


def fetch_conference_alerts(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    del since
    items: list[DigestItem] = []
    now = datetime.now(UTC)
    for keyword in keywords:
        url = client.build_url(
            "https://conferencealerts.com/advanced-search-results.php",
            {
                "q": keyword,
                "when": int(settings.get("when_days", 365)),
                "mode": settings.get("mode", ""),
                "countryId": settings.get("country_id", ""),
            },
        )
        html = client.get_text(url, headers={"X-Requested-With": "XMLHttpRequest"})
        items.extend(_parse_conference_alerts(html, now.year))
    return items[: int(settings.get("max_results", 10))]


def fetch_wikicfp(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    del since
    items: list[DigestItem] = []
    for keyword in keywords:
        url = client.build_url(
            "http://www.wikicfp.com/cfp/servlet/tool.search",
            {"q": keyword, "year": "f"},
        )
        html = client.get_text(url)
        items.extend(_parse_wikicfp_links(html))
    return items[: int(settings.get("max_results", 10))]


def fetch_rss(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    del keywords
    items: list[DigestItem] = []
    for feed in settings.get("feeds", []):
        source_name = feed.get("name", "RSS")
        kind = feed.get("kind", "feed")
        feed_items = _parse_rss(client.get_text(feed["url"]), source=source_name, default_kind=kind, since=since)
        items.extend(feed_items[: int(feed.get("max_results", 10))])
    return items


def fetch_watched_pages(client: HTTPClient, keywords: list[str], settings: dict[str, Any], since: datetime) -> list[DigestItem]:
    del since
    items: list[DigestItem] = []
    for page in settings.get("pages", []):
        url = page.get("url")
        if not url:
            continue
        try:
            html = client.get_text(str(url))
        except Exception:
            continue
        text = clean_text(html)
        if page.get("require_keyword_match", False):
            low_text = text.lower()
            if not any(keyword.lower() in low_text for keyword in keywords):
                continue
        title = clean_text(page.get("title", "")) or _html_title(html) or str(url)
        summary = clean_text(page.get("summary", "")) or split_sentences(text, limit=2)
        published = parse_datetime(page.get("date"))
        content_hash = sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
        items.append(
            DigestItem(
                source=clean_text(page.get("source", "Watched Page")),
                kind=clean_text(page.get("kind", "feed")) or "feed",
                title=title,
                url=str(url),
                published=published,
                venue=clean_text(page.get("venue", "")),
                summary=summary,
                metadata={
                    "content_hash": content_hash,
                    "fingerprint_key": f"{url}#{content_hash}",
                },
            )
        )
    return items[: int(settings.get("max_results", 10))]


def _parse_rss(xml_text: str, source: str, default_kind: str, since: datetime) -> list[DigestItem]:
    root = ET.fromstring(xml_text)
    items: list[DigestItem] = []
    if root.tag.endswith("feed"):
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            published = parse_datetime(_find_text(entry, "{http://www.w3.org/2005/Atom}updated")) or parse_datetime(
                _find_text(entry, "{http://www.w3.org/2005/Atom}published")
            )
            if published and published < since:
                continue
            link = ""
            for link_el in entry.findall("{http://www.w3.org/2005/Atom}link"):
                if link_el.attrib.get("href"):
                    link = link_el.attrib["href"]
                    break
            items.append(
                DigestItem(
                    source=source,
                    kind=default_kind,
                    title=clean_text(_find_text(entry, "{http://www.w3.org/2005/Atom}title")),
                    url=link,
                    published=published,
                    summary=split_sentences(_find_text(entry, "{http://www.w3.org/2005/Atom}summary") or _find_text(entry, "{http://www.w3.org/2005/Atom}content"), limit=3),
                )
            )
        return items

    for entry in root.findall(".//item"):
        published = parse_datetime(entry.findtext("pubDate") or entry.findtext("date"))
        if published and published < since:
            continue
        items.append(
            DigestItem(
                source=source,
                kind=default_kind,
                title=clean_text(entry.findtext("title", default="")),
                url=clean_text(entry.findtext("link", default="")),
                published=published,
                summary=split_sentences(entry.findtext("description", default=""), limit=3),
            )
        )
    return items


def _parse_conference_alerts(html: str, default_year: int) -> list[DigestItem]:
    items: list[DigestItem] = []
    current_month = ""
    current_year = default_year
    chunks = re.split(r"(<h2[^>]*>.*?</h2>)", html, flags=re.I | re.S)
    for chunk in chunks:
        header = re.search(r"<h2[^>]*>(.*?)</h2>", chunk, flags=re.I | re.S)
        if header:
            month_text = clean_text(header.group(1))
            parts = month_text.split()
            if len(parts) >= 2:
                current_month = parts[0]
                current_year = int(parts[1])
            continue
        for block in re.findall(r'<div class="py-2 border-bottom">(.*?)</div>\s*</div>\s*</div>', chunk, flags=re.I | re.S):
            day_match = re.search(r'style="min-width:70px;">\s*([^<]+)', block)
            link_match = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not link_match:
                continue
            day = _ordinal_to_int(clean_text(day_match.group(1)) if day_match else "")
            published = _conference_date(current_month, current_year, day)
            title = clean_text(link_match.group(2))
            link = urllib.parse.urljoin("https://conferencealerts.com/", link_match.group(1))
            location = clean_text(" ".join(re.findall(r'<span[^>]*>([^<]+)</span>', block, flags=re.I | re.S)[:2]))
            mode_match = re.search(r'<span class="badge[^"]*"[^>]*>(.*?)</span>', block, flags=re.I | re.S)
            mode = clean_text(mode_match.group(1)) if mode_match else ""
            items.append(
                DigestItem(
                    source="Conference Alerts",
                    kind="conference",
                    title=title,
                    url=link,
                    published=published,
                    venue=location,
                    summary=mode,
                    metadata={"mode": mode},
                )
            )
    return items


def _parse_wikicfp_links(html: str) -> list[DigestItem]:
    parser = LinkExtractor()
    parser.feed(html)
    items: list[DigestItem] = []
    seen: set[str] = set()
    for href, text in parser.links:
        if "event.showcfp" not in href:
            continue
        url = urllib.parse.urljoin("http://www.wikicfp.com/cfp/", href)
        if url in seen:
            continue
        seen.add(url)
        items.append(
            DigestItem(
                source="WikiCFP",
                kind="conference",
                title=text,
                url=url,
                venue="WikiCFP",
            )
        )
    return items


def _html_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def _arxiv_term(keyword: str) -> str:
    cleaned = keyword.strip().strip('"')
    if " " in cleaned:
        return f'all:"{cleaned}"'
    return f"all:{cleaned}"


def _find_text(element: ET.Element, path: str) -> str:
    found = element.find(path, ATOM_NS)
    return found.text if found is not None and found.text else ""


def _first(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value or "")


def _crossref_date(record: dict[str, Any]) -> datetime | None:
    for key in ("published-print", "published-online", "published", "created"):
        parts = record.get(key, {}).get("date-parts")
        if parts and parts[0]:
            date_parts = [str(part) for part in parts[0]]
            return parse_datetime("-".join(date_parts))
    return None


def _pubmed_date(article: ET.Element) -> datetime | None:
    year = article.findtext(".//ArticleDate/Year") or article.findtext(".//PubDate/Year")
    month = article.findtext(".//ArticleDate/Month") or article.findtext(".//PubDate/Month") or "1"
    day = article.findtext(".//ArticleDate/Day") or article.findtext(".//PubDate/Day") or "1"
    month_map = {"Jan": "1", "Feb": "2", "Mar": "3", "Apr": "4", "May": "5", "Jun": "6", "Jul": "7", "Aug": "8", "Sep": "9", "Oct": "10", "Nov": "11", "Dec": "12"}
    month = month_map.get(month[:3], month)
    if not year:
        return None
    return parse_datetime(f"{year}-{month}-{day}")


def _google_search_date(result: dict[str, Any]) -> datetime | None:
    pagemap = result.get("pagemap") or {}
    for metatag in pagemap.get("metatags", []):
        for key in (
            "article:published_time",
            "article:modified_time",
            "citation_publication_date",
            "dc.date",
            "dc.date.issued",
            "date",
            "og:updated_time",
        ):
            parsed = parse_datetime(metatag.get(key))
            if parsed:
                return parsed
    return None


def _conference_date(month_name: str, year: int, day: int | None) -> datetime | None:
    if not month_name or not day:
        return None
    try:
        month = datetime.strptime(month_name[:3], "%b").month
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _ordinal_to_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _env_value(name: str | None) -> str:
    if not name:
        return ""
    import os

    return os.environ.get(str(name), "")
