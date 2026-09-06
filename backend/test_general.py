"""Offline regression tests for the general-knowledge feature. No network —
web_search is monkeypatched, same spirit as test_market.py."""

import unittest
from unittest.mock import patch

from backend import general
from backend import llm
from backend.intent import analyze_question
from backend.search import AllProvidersFailedError
from backend.search.providers import SearchResult


class GeneralIntentRoutingTests(unittest.TestCase):
    def test_what_is_question_is_general_knowledge(self):
        intent = analyze_question("What is Kubernetes?")
        self.assertEqual(intent.kind, "general_knowledge")

    def test_compare_question_is_general_knowledge(self):
        intent = analyze_question("Compare Apple and Samsung")
        self.assertEqual(intent.kind, "general_knowledge")

    def test_explain_topic_is_general_knowledge(self):
        intent = analyze_question("Explain quantum computing")
        self.assertEqual(intent.kind, "general_knowledge")

    def test_ai_news_request_stays_category_news(self):
        # Regression: must not swallow real news requests into general_knowledge.
        intent = analyze_question("Tell me today's AI news")
        self.assertEqual(intent.kind, "category_news")

    def test_bengaluru_news_stays_location_news(self):
        intent = analyze_question("What's the news in Bangalore?")
        self.assertEqual(intent.kind, "location_news")

    def test_plain_headlines_request_is_not_general_knowledge(self):
        intent = analyze_question("Give me today's top stories")
        self.assertEqual(intent.kind, "headlines")

    def test_telugu_thriller_is_a_movie_recommendation(self):
        intent = analyze_question("Which is the best thriller in Telugu movie?")
        self.assertEqual(intent.kind, "telugu_movie_recommendation")

    def test_best_telugu_horror_routes_to_movie_recommendation(self):
        intent = analyze_question("which is the best Telugu horror movie")
        self.assertEqual(intent.kind, "telugu_movie_recommendation")

    def test_telugu_recommendation_is_not_news(self):
        intent = analyze_question("Recommend a Telugu thriller")
        self.assertEqual(intent.kind, "telugu_movie_recommendation")

    def test_conversational_telugu_song_does_not_use_general_knowledge(self):
        intent = analyze_question("do you know any Telugu song")
        self.assertEqual(intent.kind, "conversational")

    def test_latest_telugu_songs_stays_search_backed_general_knowledge(self):
        intent = analyze_question("latest Telugu songs")
        self.assertEqual(intent.kind, "general_knowledge")

    def test_assistant_intent_remains_deterministic(self):
        intent = analyze_question("what can you do")
        self.assertEqual(intent.kind, "assistant")

    def test_casual_intent_remains_deterministic(self):
        intent = analyze_question("hello")
        self.assertEqual(intent.kind, "casual")

    def test_best_telugu_thriller_is_a_movie_recommendation(self):
        intent = analyze_question("Best Telugu thriller movie")
        self.assertEqual(intent.kind, "telugu_movie_recommendation")

    def test_cricket_definition_remains_general_knowledge(self):
        intent = analyze_question("What is cricket?")
        self.assertEqual(intent.kind, "general_knowledge")

    def test_cricket_news_remains_topic_news(self):
        intent = analyze_question("Tell me cricket news")
        self.assertEqual(intent.kind, "topic_news")


class GeneralContextBuilderTests(unittest.TestCase):
    def setUp(self):
        self.original_web_search = general.web_search

    def tearDown(self):
        general.web_search = self.original_web_search

    def test_context_includes_source_names(self):
        # Unlike market context, general context keeps sources so Qwen
        # can attribute the answer (e.g. "According to Wikipedia...").
        general.web_search = lambda query, limit=5: [
            SearchResult(title="Kubernetes", url="https://kubernetes.io", snippet="Container orchestration platform.", source="wikipedia")
        ]
        context = general.get_general_context("What is Kubernetes?")
        self.assertIn("wikipedia", context)
        self.assertIn("Kubernetes", context)

    def test_empty_when_all_providers_fail(self):
        def _raise(query, limit=5):
            raise AllProvidersFailedError("all down")
        general.web_search = _raise
        self.assertEqual(general.get_general_context("anything"), "")

    def test_empty_when_no_results(self):
        general.web_search = lambda query, limit=5: []
        self.assertEqual(general.get_general_context("anything"), "")

    def test_empty_question_raises_value_error_is_handled(self):
        def _raise(query, limit=5):
            raise ValueError("empty")
        general.web_search = _raise
        self.assertEqual(general.get_general_context(""), "")

    def test_resolved_person_question_is_used_for_search(self):
        seen_queries = []
        general.web_search = lambda query, limit=5: (seen_queries.append(query) or [])
        general.get_general_context("What is Virat Kohli's age?")
        self.assertIn("Virat Kohli", seen_queries[0])

    def test_telugu_movie_context_excludes_non_telugu_results(self):
        seen_queries = []

        def _search(query, limit=5):
            seen_queries.append(query)
            return [
            SearchResult(title="Telugu thriller picks", url="https://example.com/telugu", snippet="A guide to Telugu-language thriller films.", source="duckduckgo"),
            SearchResult(title="Mukhbir", url="https://example.com/mukhbir", snippet="Hindi spy drama.", source="duckduckgo"),
            SearchResult(title="Tamil thriller picks", url="https://example.com/tamil", snippet="Tamil-language thriller films.", source="duckduckgo"),
            ]

        general.web_search = _search

        context = general.get_telugu_movie_recommendation_context("Recommend a Telugu thriller")

        self.assertIn("Telugu thriller picks", context)
        self.assertNotIn("Mukhbir", context)
        self.assertNotIn("Tamil thriller picks", context)
        self.assertEqual(seen_queries, ["Telugu-language thriller films recommendations"])


class TeluguMovieRecommendationTests(unittest.TestCase):
    context = """Verified Telugu-language film results:
- Jatadhara: A Telugu-language horror movie.
- Kishkindhapuri: A Telugu-language horror film."""

    @patch("backend.llm.ask_ollama")
    def test_best_horror_answer_is_direct_concise_and_grounded(self, ask_ollama):
        ask_ollama.return_value = (
            "I'd pick Jatadhara. Kishkindhapuri is another good choice if you want an alternative."
        )

        answer = llm.ask_telugu_movie_recommendation(
            "which is the best Telugu horror movie", self.context
        )

        self.assertEqual(
            answer,
            "I'd pick Jatadhara. Kishkindhapuri is another good choice if you want an alternative.",
        )
        self.assertLessEqual(len([s for s in answer.split(".") if s.strip()]), 2)
        self.assertFalse(any(phrase in answer.lower() for phrase in llm.TELUGU_MOVIE_FILLER_PHRASES))
        self.assertTrue(llm._is_safe_telugu_movie_recommendation(answer, self.context))

    @patch(
        "backend.llm.ask_ollama",
        side_effect=["I'd pick Invented Movie.", "I'd pick Hindi Film."],
    )
    def test_invented_or_non_telugu_title_is_not_returned(self, _ask_ollama):
        answer = llm.ask_telugu_movie_recommendation(
            "which is the best Telugu horror movie", self.context
        )

        self.assertNotIn("Invented Movie", answer)
        self.assertNotIn("Hindi Film", answer)
        self.assertEqual(
            answer,
            "I found Telugu-language film information, but couldn't make a clean recommendation right now.",
        )


if __name__ == "__main__":
    unittest.main()
