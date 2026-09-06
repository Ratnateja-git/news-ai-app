"""General-knowledge answering for Priya.

Architecture rule (same as market.py): gemma is never the source of facts
here — only Python-retrieved search results (search/pipeline.py) are ever
sent to it, and only to explain/summarize what was already retrieved.
"""

import re
import time

from .search import AllProvidersFailedError, web_search

EDUCATION_ABBREVIATIONS = {
    "mca": "Master of Computer Applications degree",
    "bca": "Bachelor of Computer Applications degree",
    "mba": "Master of Business Administration degree",
    "mtech": "Master of Technology degree",
    "btech": "Bachelor of Technology degree",
}
GENERAL_CONTEXT_RESULT_LIMIT = 3
GENERAL_CONTEXT_SNIPPET_LIMIT = 360
TELUGU_CONTEXT_RESULT_LIMIT = 3
TELUGU_CONTEXT_SNIPPET_LIMIT = 300

MOVIE_GENRES = ("thriller", "horror", "mystery")
TELUGU_FILM_EVIDENCE_PATTERN = re.compile(
    r"\btelugu(?:-language|\s+(?:language|film|films|movie|movies|cinema|"
    r"thriller|thrillers|horror|mystery))\b",
    re.IGNORECASE,
)
OTHER_FILM_LANGUAGE_PATTERN = re.compile(
    r"\b(?:hindi|tamil|malayalam|kannada|english|hollywood|bollywood)\b",
    re.IGNORECASE,
)


def get_telugu_movie_recommendation_context(
    question: str,
    limit: int = TELUGU_CONTEXT_RESULT_LIMIT,
) -> str:
    """Fetch only explicitly Telugu-language film results for a recommendation."""

    lowered = question.lower()
    genres = [genre for genre in MOVIE_GENRES if re.search(rf"\b{genre}\b", lowered)]
    genre_query = " ".join(genres) if genres else "film"
    search_query = f"Telugu-language {genre_query} films recommendations"

    try:
        results = web_search(search_query, limit=max(limit * 2, 6))
    except (AllProvidersFailedError, ValueError):
        return ""

    # A result is only allowed through when its own title or snippet says
    # Telugu. This prevents similarly-ranked Hindi/Tamil/etc. results from
    # entering the LLM context.
    telugu_results = []
    for result in results:
        title = result.title.strip()
        snippet = result.snippet.strip()
        evidence = f"{title} {snippet}".lower()

        if (
            title
            and TELUGU_FILM_EVIDENCE_PATTERN.search(evidence)
            and not OTHER_FILM_LANGUAGE_PATTERN.search(evidence)
        ):
            telugu_results.append(result)

    lines = ["Verified Telugu-language film results:"]

    seen_content: set[tuple[str, str]] = set()
    for result in telugu_results[:min(limit, TELUGU_CONTEXT_RESULT_LIMIT)]:
        line = f"- {result.title.strip()}"
        snippet = _compact_snippet(result.snippet)[:TELUGU_CONTEXT_SNIPPET_LIMIT].rstrip()
        content_key = (result.title.strip().lower(), snippet.lower())
        if content_key in seen_content:
            continue
        seen_content.add(content_key)
        if snippet:
            line += f": {snippet}"
        lines.append(line)

    return "\n".join(lines) if len(lines) > 1 else ""


def normalize_education_query(question: str) -> str:
    """Expand common degree abbreviations for search only."""
    normalized = question
    for abbreviation, expansion in EDUCATION_ABBREVIATIONS.items():
        normalized = re.sub(
            rf"\b{abbreviation}\b(?:\s+degree\b)?",
            expansion,
            normalized,
            flags=re.IGNORECASE,
        )
    return normalized


def _compact_snippet(snippet: str) -> str:
    """Keep grounding concise enough for fast, voice-sized answers."""
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if len(snippet) <= GENERAL_CONTEXT_SNIPPET_LIMIT:
        return snippet

    shortened = snippet[:GENERAL_CONTEXT_SNIPPET_LIMIT].rsplit(" ", 1)[0].strip()
    return f"{shortened or snippet[:GENERAL_CONTEXT_SNIPPET_LIMIT].strip()}…"


def get_general_context(question: str, limit: int = GENERAL_CONTEXT_RESULT_LIMIT) -> str:
    """Fetch focused search results for a general-knowledge question."""
    total_started = time.perf_counter()
    query_started = time.perf_counter()
    normalized_question = normalize_education_query(question)
    print(f"[PERF][GENERAL] query preparation: {time.perf_counter() - query_started:.3f}s")

    try:
        search_started = time.perf_counter()
        results = web_search(
            normalized_question,
            limit=limit,
        )
        print(f"[PERF][GENERAL] search: {time.perf_counter() - search_started:.3f}s")

        if not results:
            print("[PERF][GENERAL] filtering: 0.000s")
            print(f"[PERF][GENERAL] total: {time.perf_counter() - total_started:.3f}s")
            return ""
        
    except (AllProvidersFailedError, ValueError):
        print(f"[PERF][GENERAL] search: {time.perf_counter() - search_started:.3f}s")
        print("[PERF][GENERAL] filtering: 0.000s")
        print(f"[PERF][GENERAL] total: {time.perf_counter() - total_started:.3f}s")
        return ""

    filtering_started = time.perf_counter()
    lines = [
        "User question:",
        question.strip(),
        "",
        "Relevant search results:",
    ]

    seen_content: set[tuple[str, str]] = set()
    for result in results[:min(limit, GENERAL_CONTEXT_RESULT_LIMIT)]:
        title = result.title.strip()
        snippet = _compact_snippet(result.snippet)

        if not title:
            continue
        content_key = (title.lower(), snippet.lower())
        if content_key in seen_content:
            continue
        seen_content.add(content_key)

        line = f"- ({result.source}) {title}"

        if snippet:
            line += f": {snippet}"

        lines.append(line)

    context = "\n".join(lines) if len(lines) > 3 else ""
    print(f"[PERF][GENERAL] filtering: {time.perf_counter() - filtering_started:.3f}s")
    print(f"[PERF][GENERAL] total: {time.perf_counter() - total_started:.3f}s")
    return context
