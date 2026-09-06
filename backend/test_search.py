"""Offline regression tests for the search pipeline. No network needed —
providers are monkeypatched with fakes, same spirit as test_market.py."""

import unittest

from backend.search import pipeline, cache
from backend.search.providers import SearchResult


def fake_provider(results=None, error=None):
    def _provider(query, limit):
        if error:
            raise error
        return (results or [])[:limit]
    return _provider


class ProviderOrderingTests(unittest.TestCase):
    def test_definitional_query_tries_wikipedia_first(self):
        order = pipeline._ordered_providers("What is Kubernetes?")
        self.assertEqual(order[0], "wikipedia")

    def test_normal_query_keeps_default_order(self):
        order = pipeline._ordered_providers("Latest Reliance stock news")
        self.assertEqual(order, pipeline.get_provider_priority())


class FailoverTests(unittest.TestCase):
    def setUp(self):
        cache.clear()
        self.original_registry = dict(pipeline.PROVIDER_REGISTRY)

    def tearDown(self):
        pipeline.PROVIDER_REGISTRY.clear()
        pipeline.PROVIDER_REGISTRY.update(self.original_registry)
        cache.clear()

    def test_falls_back_when_first_provider_errors(self):
        good_result = SearchResult(title="Kubernetes", url="https://kubernetes.io", snippet="Container orchestration.", source="wikipedia")

        pipeline.PROVIDER_REGISTRY["duckduckgo"] = fake_provider(error=ConnectionError("quota exceeded"))
        pipeline.PROVIDER_REGISTRY["wikipedia"] = fake_provider(results=[good_result])

        results = pipeline.web_search("Kubernetes", use_cache=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "wikipedia")

    def test_falls_back_when_first_provider_returns_nothing(self):
        good_result = SearchResult(title="Kubernetes", url="https://kubernetes.io", snippet="Container orchestration.", source="wikipedia")

        pipeline.PROVIDER_REGISTRY["duckduckgo"] = fake_provider(results=[])
        pipeline.PROVIDER_REGISTRY["wikipedia"] = fake_provider(results=[good_result])

        results = pipeline.web_search("Kubernetes", use_cache=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "wikipedia")

    def test_raises_when_every_provider_fails(self):
        pipeline.PROVIDER_REGISTRY["duckduckgo"] = fake_provider(error=ConnectionError("down"))
        pipeline.PROVIDER_REGISTRY["wikipedia"] = fake_provider(results=[])

        with self.assertRaises(pipeline.AllProvidersFailedError):
            pipeline.web_search("anything", use_cache=False)

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.web_search("   ", use_cache=False)


class DedupeAndRankTests(unittest.TestCase):
    def test_duplicate_urls_are_removed(self):
        results = [
            SearchResult(title="A", url="https://example.com/x", snippet="", source="duckduckgo"),
            SearchResult(title="A dup", url="https://www.example.com/x/", snippet="", source="duckduckgo"),
        ]
        self.assertEqual(len(pipeline.deduplicate_results(results)), 1)

    def test_ranking_prefers_title_term_matches(self):
        results = [
            SearchResult(title="Unrelated topic", url="https://a.com", snippet="mentions kubernetes once", source="duckduckgo"),
            SearchResult(title="Kubernetes basics", url="https://b.com", snippet="An intro.", source="duckduckgo"),
        ]
        ranked = pipeline.rank_results(results, "kubernetes")
        self.assertEqual(ranked[0].title, "Kubernetes basics")


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def test_set_then_get_returns_value(self):
        key = cache.make_key("q", "search term", 5)
        cache.set(key, ["result"])
        self.assertEqual(cache.get(key), ["result"])

    def test_missing_key_returns_none(self):
        self.assertIsNone(cache.get(cache.make_key("nope")))

    def test_lru_eviction_drops_oldest(self):
        cache.MAX_ENTRIES_BACKUP = cache.MAX_ENTRIES
        cache.MAX_ENTRIES = 2
        try:
            cache.set("a", 1)
            cache.set("b", 2)
            cache.set("c", 3)  # evicts "a"
            self.assertIsNone(cache.get("a"))
            self.assertEqual(cache.get("c"), 3)
        finally:
            cache.MAX_ENTRIES = cache.MAX_ENTRIES_BACKUP


if __name__ == "__main__":
    unittest.main()