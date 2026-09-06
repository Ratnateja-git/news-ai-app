"""Multi-provider search with automatic failover.

Mirrors the rest of the codebase's stance on facts (see market.py's
module docstring): this module never invents results. A provider either
returns real results or the pipeline moves on to the next provider —
never a placeholder, never silently-empty-looking-like-success.
"""

import re

from . import cache
from .providers import SearchResult, get_provider_priority, PROVIDER_REGISTRY

DEFINITIONAL_MARKERS = ("what is", "what are", "who is", "who was", "define", "definition of", "meaning of")


class AllProvidersFailedError(RuntimeError):
    """Raised when every provider in the priority list errored or returned nothing."""


def _looks_definitional(query: str) -> bool:
    lowered = query.lower().strip()
    return any(lowered.startswith(marker) for marker in DEFINITIONAL_MARKERS)


def _ordered_providers(query: str) -> list[str]:
    """Provider names to try, in order.

    Wikipedia is strong for definitional questions and weak for breaking
    news/opinion, so definitional-looking queries try it first; everything
    else tries general web search first. This is the only place query
    shape affects provider choice — adding a new provider never requires
    touching this logic, since it just reorders whatever get_provider_priority()
    already returned.
    """
    priority = get_provider_priority()

    if _looks_definitional(query) and "wikipedia" in priority:
        return ["wikipedia"] + [name for name in priority if name != "wikipedia"]

    return priority


def _normalize_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/").lower()


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Drop near-duplicates by normalized URL, preserving first-seen order."""
    seen: set[str] = set()
    unique = []

    for result in results:
        key = _normalize_url(result.url)
        if key and key not in seen:
            seen.add(key)
            unique.append(result)

    return unique


def rank_results(results: list[SearchResult], query: str) -> list[SearchResult]:
    """Deterministic ranking by query-term overlap, snippet richness, and a
    small trust bonus for reference sources — same spirit as news.rank_articles,
    no ML, fully inspectable."""
    words = {word for word in re.findall(r"[a-z0-9]{3,}", query.lower())}

    def score(result: SearchResult) -> int:
        text = f"{result.title} {result.snippet}".lower()
        value = sum(3 if word in result.title.lower() else 1 for word in words if word in text)
        value += 2 if result.source == "wikipedia" else 0
        value += 1 if len(result.snippet) > 40 else 0
        return value

    return sorted(results, key=score, reverse=True)


def _log_search_result_size(results: list[SearchResult]) -> None:
    total_characters = sum(
        len(result.title) + len(result.snippet)
        for result in results
    )
    print(f"[PERF][SEARCH] result count: {len(results)}")
    print(f"[PERF][SEARCH] total characters: {total_characters}")


def web_search(query: str, limit: int = 6, use_cache: bool = True) -> list[SearchResult]:
    """Run the failover search pipeline and return ranked, deduped results.

    Tries providers in order; the first provider that returns at least one
    result wins for this call — matching "if Tavily fails, switch to Exa"
    semantics rather than always paying for every provider on every query.
    Raises AllProvidersFailedError only if every provider in the priority
    list either errored or returned zero results, so callers can show an
    honest "couldn't find anything" message instead of guessing.
    """
    query = query.strip()

    if not query:
        raise ValueError("Query cannot be empty.")

    cache_key = cache.make_key("web_search", query, limit)

    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            _log_search_result_size(cached)
            return cached

    errors: list[str] = []

    for provider_name in _ordered_providers(query):
        provider_fn = PROVIDER_REGISTRY[provider_name]

        try:
            results = provider_fn(query, limit)
        except Exception as error:  # noqa: BLE001 — any provider failure triggers failover
            errors.append(f"{provider_name}: {error}")
            continue

        if not results:
            continue

        ranked = rank_results(deduplicate_results(results), query)[:limit]
        _log_search_result_size(ranked)

        if use_cache:
            cache.set(cache_key, ranked)

        return ranked

    raise AllProvidersFailedError(
        "All search providers failed or returned no results. " + "; ".join(errors)
    )
