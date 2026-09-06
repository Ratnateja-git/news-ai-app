"""Search providers, plus the priority registry pipeline.py walks for
automatic failover.

Adding a paid provider later means writing one
`search_x(query, limit) -> list[SearchResult]` function here and adding
it to PROVIDER_REGISTRY / DEFAULT_PROVIDER_PRIORITY — pipeline.py never
changes, because it only ever calls "the next provider in the list."
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import unescape

import requests
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "Priya-News-AI/1.0 (search)"
PROVIDER_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str  # provider name, e.g. "duckduckgo" / "wikipedia"


# --------------------------------------------------------------------
# Shared helper: every paid provider below follows the same contract —
# missing key, timeout, HTTP error, quota/rate-limit response, or any
# unexpected payload shape all resolve to an empty list, never a raised
# exception. This is what lets pipeline.py's failover "just work": an
# empty list looks identical to "provider had nothing to say", so the
# next provider in priority order is tried automatically, and provider
# failures are never exposed to the user.
# --------------------------------------------------------------------

def _get_api_key(env_var: str) -> str | None:
    key = os.getenv(env_var, "").strip()
    return key or None


# --------------------------------------------------------------------
# Tavily — search API built for LLM grounding, returns clean snippets.
# https://docs.tavily.com/documentation/api-reference/endpoint/search
# --------------------------------------------------------------------

TAVILY_URL = "https://api.tavily.com/search"


def search_tavily(query: str, limit: int = 6) -> list[SearchResult]:
    api_key = _get_api_key("TAVILY_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.post(
            TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )

        # Quota-exceeded / auth-failed responses (401/403) and rate
        # limits (429) fail the same way as any other bad response —
        # empty list, no exception raised to the caller.
        if response.status_code != 200:
            return []

        payload = response.json()

    except (requests.RequestException, ValueError):
        return []

    results = []

    for item in payload.get("results", [])[:limit]:
        title = clean_text(item.get("title", ""))
        url = (item.get("url") or "").strip()

        if not title or not url:
            continue

        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=clean_text(item.get("content", "")),
                source="tavily",
            )
        )

    return results


# --------------------------------------------------------------------
# Exa — neural/semantic search API.
# https://docs.exa.ai/reference/search
# --------------------------------------------------------------------

EXA_URL = "https://api.exa.ai/search"


def search_exa(query: str, limit: int = 6) -> list[SearchResult]:
    api_key = _get_api_key("EXA_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.post(
            EXA_URL,
            json={
                "query": query,
                "numResults": limit,
                "type": "auto",
                "contents": {"text": {"maxCharacters": 400}},
            },
            headers={
                "x-api-key": api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return []

        payload = response.json()

    except (requests.RequestException, ValueError):
        return []

    results = []

    for item in payload.get("results", [])[:limit]:
        title = clean_text(item.get("title", ""))
        url = (item.get("url") or "").strip()

        if not title or not url:
            continue

        snippet = clean_text(item.get("text", "") or item.get("summary", ""))

        results.append(
            SearchResult(title=title, url=url, snippet=snippet, source="exa")
        )

    return results




# --------------------------------------------------------------------
# DuckDuckGo — general web search, no key required.
# Uses the `ddgs` package (pip install ddgs) rather than hand-rolled
# HTML scraping, so a ToS/markup change upstream breaks a maintained
# library instead of our regex.
# --------------------------------------------------------------------

def search_duckduckgo(query: str, limit: int = 6) -> list[SearchResult]:
    try:
        from ddgs import DDGS
    except ImportError as error:
        raise RuntimeError(
            "The 'ddgs' package is required for DuckDuckGo search. "
            "Install it with: pip install ddgs"
        ) from error

    results = []

    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=limit):
            title = clean_text(item.get("title", ""))
            url = (item.get("href") or "").strip()
            snippet = clean_text(item.get("body", ""))

            if not title or not url:
                continue

            results.append(
                SearchResult(title=title, url=url, snippet=snippet, source="duckduckgo")
            )

    return results


# --------------------------------------------------------------------
# Wikipedia — free REST API, no key required. Strong for definitional /
# "what is X" questions; weak for breaking news or opinion.
# --------------------------------------------------------------------

WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


def search_wikipedia(query: str, limit: int = 3) -> list[SearchResult]:
    response = requests.get(
        WIKIPEDIA_SEARCH_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()

    hits = response.json().get("query", {}).get("search", [])

    entries = []
    for hit in hits[:limit]:
        title = clean_text(hit.get("title", ""))
        if not title:
            continue
        entries.append((title, clean_text(strip_wiki_markup(hit.get("snippet", "")))))

    # Each summary is independent. Fetching them concurrently preserves the
    # same ordered, grounded results without paying their network latency in
    # series for definition questions.
    with ThreadPoolExecutor(max_workers=min(3, len(entries) or 1)) as executor:
        summaries = list(executor.map(lambda entry: _fetch_wikipedia_summary(entry[0]), entries))

    results = []
    for (title, fallback_snippet), summary in zip(entries, summaries):
        results.append(
            SearchResult(
                title=title,
                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                snippet=summary or fallback_snippet,
                source="wikipedia",
            )
        )

    return results


def _fetch_wikipedia_summary(title: str) -> str:
    """Best-effort plain-language summary; falls back to '' on any failure
    so a slow/missing summary never breaks the whole search result."""
    try:
        response = requests.get(
            WIKIPEDIA_SUMMARY_URL.format(title=requests.utils.quote(title)),
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        response.raise_for_status()
        return clean_text(response.json().get("extract", ""))
    except requests.RequestException:
        return ""


def strip_wiki_markup(text: str) -> str:
    """Wikipedia search snippets wrap matched terms in <span class="searchmatch">."""
    return re.sub(r"<[^>]+>", "", unescape(text or ""))


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


# --------------------------------------------------------------------
# Registry — priority order pipeline.py walks. Override at runtime with
# the SEARCH_PROVIDER_PRIORITY env var (comma-separated provider names)
# without touching any code, e.g. SEARCH_PROVIDER_PRIORITY=wikipedia,duckduckgo
# --------------------------------------------------------------------

PROVIDER_REGISTRY = {
    "tavily": search_tavily,
    "exa": search_exa,
    "duckduckgo": search_duckduckgo,
    "wikipedia": search_wikipedia,
    # "bing": search_bing,  # slot in the same way once needed
}

DEFAULT_PROVIDER_PRIORITY = ["tavily", "exa", "duckduckgo", "wikipedia"]


def get_provider_priority() -> list[str]:
    """Ordered provider names to try, filtered to ones actually registered."""
    raw = os.getenv("SEARCH_PROVIDER_PRIORITY", "")
    names = [name.strip().lower() for name in raw.split(",") if name.strip()] or DEFAULT_PROVIDER_PRIORITY
    return [name for name in names if name in PROVIDER_REGISTRY]
