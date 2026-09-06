"""News retrieval, normalization, ranking, and matching."""

import json
import re
from datetime import datetime, timezone
from html import unescape
from xml.etree import ElementTree

import requests

from .database import save_articles

RSS_FEEDS = {
    "general": "https://feeds.bbci.co.uk/news/rss.xml",
    "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "ai": "https://www.wired.com/feed/tag/ai/latest/rss",
}
SEARCH_CATEGORIES = {"business", "sports", "politics", "entertainment", "science", "health"}


def detect_category(question: str) -> str:
    """Legacy category helper retained for existing callers."""
    from .intent import analyze_question
    return analyze_question(question).category


def clean_text(value: str | None) -> str:
    """Remove RSS markup and normalize whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", unescape(value or ""))).strip()


def _search_feed(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + requests.utils.quote(query) + "&hl=en-IN&gl=IN&ceid=IN:en"


def _feed_for(category: str, location: str | None) -> tuple[str, str, bool]:
    if location:
        return _search_feed(f"{location} news"), "Google News", True
    if category in SEARCH_CATEGORIES:
        return _search_feed(f"{category} news"), "Google News", True
    if category not in RSS_FEEDS:
        raise ValueError(f"Unsupported category: {category}")
    return RSS_FEEDS[category], "WIRED" if category == "ai" else "BBC News", False


HEADLINE_PREFIX_PATTERNS = (
    r"^today'?s\s+market\s*:\s*",
    r"^breaking\s+news\s*:\s*",
    r"^breaking\s*:\s*",
)


def strip_headline_prefix(title: str) -> str:
    """Remove known lead-in labels some feeds prepend to the real headline,
    e.g. "Today's Market: Sensex rises 200 points" or "Breaking: Nifty
    crosses 25000", so Priya never reads the label out loud.
    """
    for pattern in HEADLINE_PREFIX_PATTERNS:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    return title.strip()


def strip_source_suffix(title: str) -> str:
    """Strip a trailing source marker so Priya never reads it out as part
    of the headline.

    Google News formats titles as 'Headline - Source Name'. Some feeds
    (e.g. market-focused aggregators) instead append '| Source Name'
    (CNBCTV18, Reuters, BBC, NDTV, etc.). Both trailing forms are removed;
    a leading label like "Breaking:" is also stripped via
    strip_headline_prefix.
    """
    title = re.sub(r"\s*\|\s*[^|]+$", "", title)
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    return strip_headline_prefix(title.strip())


def fetch_feed(category: str = "general", location: str | None = None, limit: int = 10) -> list[dict[str, str]]:
    """Fetch a feed and return a consistent article shape."""
    url, default_source, is_google_news = _feed_for(category, location)
    response = requests.get(url, timeout=15, headers={"User-Agent": "Priya-News-AI/1.0"})
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    articles = []
    for item in root.findall("./channel/item")[:limit]:
        title = clean_text(item.findtext("title", default=""))
        if is_google_news:
            title = strip_source_suffix(title)
        if not title:
            continue
        source = clean_text(item.findtext("source", default="")) or default_source
        articles.append({"title": title, "summary": clean_text(item.findtext("description", default="")), "url": item.findtext("link", default="").strip(), "source": source, "published_at": item.findtext("pubDate", default="").strip(), "category": category, "location": location or "", "collected_at": datetime.now(timezone.utc).isoformat()})
    return deduplicate_articles(articles)


TOPIC_KEYWORDS = {
    "cricket": (
        "cricket",
        "ipl",
        "test cricket",
        "odi",
        "t20",
        "icc",
    ),
    "football": (
        "football",
        "soccer",
        "fifa",
        "premier league",
        "champions league",
    ),
    "tennis": (
        "tennis",
        "wimbledon",
        "atp",
        "wta",
        "us open",
        "french open",
        "australian open",
    ),
}


def fetch_google_news(
    query: str,
    limit: int = 10,
    category: str = "market",
    location: str | None = None,
) -> list[dict[str, str]]:
    """Fetch and clean an arbitrary Google News search feed."""

    url = _search_feed(query)

    response = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "Priya-News-AI/1.0"},
    )

    response.raise_for_status()

    root = ElementTree.fromstring(response.content)

    articles = []

    for item in root.findall("./channel/item")[:limit]:

        title = strip_source_suffix(
            clean_text(
                item.findtext("title", default="")
            )
        )

        if not title:
            continue

        source = (
            clean_text(
                item.findtext("source", default="")
            )
            or "Google News"
        )

        articles.append(
            {
                "title": title,
                "summary": clean_text(
                    item.findtext(
                        "description",
                        default="",
                    )
                ),
                "url": item.findtext(
                    "link",
                    default="",
                ).strip(),
                "source": source,
                "published_at": item.findtext(
                    "pubDate",
                    default="",
                ).strip(),
                "category": category,
                "location": location or "",
                "collected_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

    return deduplicate_articles(articles)


def is_relevant_to_topic(
    article: dict[str, str],
    topic: str,
) -> bool:
    """Return True when the article is clearly relevant to the topic."""

    topic = topic.lower().strip()

    keywords = TOPIC_KEYWORDS.get(
        topic,
        (topic,),
    )

    text = (
        f"{article.get('title', '')} "
        f"{article.get('summary', '')}"
    ).lower()

    return any(
        re.search(
            rf"\b{re.escape(keyword)}\b",
            text,
        )
        for keyword in keywords
    )


def fetch_topic_news(
    topic: str,
    category: str = "general",
    location: str | None = None,
    limit: int = 8,
) -> list[dict[str, str]]:
    """Fetch topic-specific news and filter irrelevant results."""

    topic = topic.strip().lower()

    if not topic:
        return []

    query = f"{topic} news"

    if location:
        query = f"{location} {topic} news"

    articles = fetch_google_news(
        query,
        limit=limit * 2,
        category=category,
        location=location,
    )

    articles = [
        article
        for article in articles
        if is_relevant_to_topic(
            article,
            topic,
        )
    ]

    articles = deduplicate_articles(
        articles
    )

    return rank_articles(
        articles,
        query,
        category=category,
        location=location,
    )[:limit]

def deduplicate_articles(articles: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop near-duplicates by canonicalized headline, preserving feed order."""
    unique, seen = [], set()
    for article in articles:
        key = re.sub(r"[^a-z0-9]+", "", article.get("title", "").lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(article)
    return unique


def rank_articles(articles: list[dict[str, str]], question: str, category: str = "general", location: str | None = None) -> list[dict[str, str]]:
    """Rank articles deterministically by requested words, category, and location."""
    words = {word for word in re.findall(r"[a-z0-9]{3,}", question.lower()) if word not in {"news", "tell", "about", "latest", "today", "what", "that", "this"}}
    def score(article: dict[str, str]) -> int:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        result = sum(3 if word in article.get("title", "").lower() else 1 for word in words if word in text)
        result += 2 if category != "general" and article.get("category") == category else 0
        result += 4 if location and location.lower() in text else 0
        return result
    return sorted(articles, key=score, reverse=True)


def find_matching_article(articles: list[dict[str, str]], question: str) -> dict[str, str] | None:
    """Choose the best matching article, returning None for no meaningful match."""
    ranked = rank_articles(articles, question)
    return ranked[0] if ranked else None


def get_top_headlines(limit: int = 10, category: str = "general", location: str | None = None) -> list[dict[str, str]]:
    articles = fetch_feed(category, location, limit)
    if articles:
        save_articles(articles)
    return articles


def get_news_context(limit: int = 8, category: str = "general", location: str | None = None) -> str:
    """Return article context as JSON; no prompt text or URLs need be spoken."""
    return json.dumps({"articles": get_top_headlines(limit, category, location)}, ensure_ascii=False)


def build_detail_context(article: dict[str, str]) -> str:
    """Compact plain-text context for a SINGLE article, for detailed Qwen questions.

    Deliberately omits url/source/category/collected_at so Qwen never sees
    (and can't leak) fields the user shouldn't hear.
    """
    title = (article.get("title") or "").strip()
    summary = (article.get("summary") or "").strip()
    lines = [f"Title: {title}"]
    if summary:
        lines.append(f"Summary: {summary}")
    return "\n".join(lines)