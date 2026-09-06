"""Provider-backed online image search; it never creates or fabricates images."""

from __future__ import annotations

from urllib.parse import urlparse


def _safe_url(value: object) -> str:
    url = str(value or "").strip()
    return url if urlparse(url).scheme in {"http", "https"} else ""


def search_images(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Return real DuckDuckGo image results through its maintained client library."""
    clean_query = query.strip()
    if not clean_query:
        return []
    try:
        from ddgs import DDGS
        raw_results = DDGS().images(clean_query, max_results=max(1, min(limit, 8)))
    except Exception:  # Provider/network failures should not break image analysis.
        return []

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_results:
        image_url = _safe_url(item.get("image"))
        source_url = _safe_url(item.get("url"))
        if not image_url or image_url in seen:
            continue
        seen.add(image_url)
        results.append({
            "title": str(item.get("title") or "Image result").strip(),
            "image_url": image_url,
            "source_url": source_url or image_url,
            "source": str(item.get("source") or "Web").strip(),
        })
        if len(results) >= limit:
            break
    return results
