"""Offline regression tests for the market/trading feature and the
reasoning-leak fix. No network needed — pure logic only."""

import unittest

from backend.intent import analyze_question
from backend.llm import looks_like_reasoning
from backend.market import (
    RESEARCH_CANDIDATES,
    build_market_detail_context,
    detect_company,
    has_sufficient_market_data,
    is_best_stock_question,
    research_candidates_context,
)


class MarketIntentTests(unittest.TestCase):
    def test_stock_market_question_is_market_category(self):
        intent = analyze_question("What's happening in the stock market?")
        self.assertEqual(intent.category, "market")

    def test_sensex_and_nifty_are_market_category(self):
        self.assertEqual(analyze_question("Give me Sensex news").category, "market")
        self.assertEqual(analyze_question("Nifty news today").category, "market")

    def test_ai_news_is_not_market_category(self):
        self.assertEqual(analyze_question("Tell me today's AI news").category, "ai")

    def test_mumbai_news_is_not_market_category(self):
        # Regression check: "market" category must not swallow unrelated news.
        intent = analyze_question("What's the news in Mumbai?")
        self.assertNotEqual(intent.category, "market")
        self.assertEqual(intent.location, "mumbai")

    def test_business_no_longer_overlaps_market_keywords(self):
        # "markets"/"stocks" moved to the dedicated market category.
        self.assertEqual(analyze_question("Give me today's stock news").category, "market")


class CompanyDetectionTests(unittest.TestCase):
    def test_detects_tata_motors_specifically(self):
        self.assertEqual(detect_company("Tell me about Tata Motors"), "Tata Motors")

    def test_detects_reliance(self):
        self.assertEqual(detect_company("Should I buy Reliance?"), "Reliance Industries")

    def test_no_false_positive_on_unrelated_text(self):
        self.assertIsNone(detect_company("What's the weather like today?"))

    def test_longer_phrase_wins_over_shorter(self):
        # "tata motors" should win, not accidentally match a shorter alias.
        self.assertEqual(detect_company("news about Tata Motors today"), "Tata Motors")


class BestStockQuestionTests(unittest.TestCase):
    def test_detects_best_stock_phrasing(self):
        self.assertTrue(is_best_stock_question("Which is the best stock to buy?"))
        self.assertTrue(is_best_stock_question("Which stocks are worth researching?"))

    def test_which_stock_should_i_buy(self):
        self.assertTrue(is_best_stock_question("Which stock should I buy?"))

    def test_what_is_the_best_stock_right_now(self):
        self.assertTrue(is_best_stock_question("What is the best stock right now?"))

    def test_normal_market_question_is_not_best_stock(self):
        self.assertFalse(is_best_stock_question("What's happening in the stock market?"))


class ReasoningLeakValidatorTests(unittest.TestCase):
    def test_flags_known_leak_phrases(self):
        self.assertTrue(looks_like_reasoning("First, I need to understand the user's request."))
        self.assertTrue(looks_like_reasoning("The NEWS given is about a building collapse."))
        self.assertTrue(looks_like_reasoning("Key points from the NEWS: it happened today."))

    def test_flags_leak_in_best_stock_style_answer(self):
        self.assertTrue(looks_like_reasoning("Let me analyze the DATA to compare the candidates."))
        self.assertTrue(looks_like_reasoning("According to the context, Reliance looks strong."))

    def test_does_not_flag_a_normal_answer(self):
        self.assertFalse(
            looks_like_reasoning(
                "A building collapsed in Mumbai's Kurla area this morning, and rescue teams are on site."
            )
        )

    def test_does_not_flag_a_normal_best_stock_answer(self):
        self.assertFalse(
            looks_like_reasoning(
                "Reliance Industries looks like one of the stronger candidates to consider right now "
                "because of recent positive earnings news. However, it still carries market risk, so "
                "there's no guaranteed best stock."
            )
        )

    def test_empty_text_is_treated_as_invalid(self):
        self.assertTrue(looks_like_reasoning(""))


class MarketContextBuildersTests(unittest.TestCase):
    def test_market_detail_context_has_no_urls_or_sources(self):
        article = {"title": "Reliance posts strong quarterly results", "url": "https://example.com/x", "source": "Reuters"}
        context = build_market_detail_context("Reliance Industries", [article])
        self.assertIn("Reliance posts strong quarterly results", context)
        self.assertNotIn("https://", context)
        self.assertNotIn("Reuters", context)

    def test_research_context_includes_only_companies_with_real_data(self):
        # Company B has no retrieved articles — it must be left out entirely,
        # never padded with a placeholder Qwen could mistake for a data point.
        candidates = [("Company A", [{"title": "A posts record profit"}]), ("Company B", [])]
        context = research_candidates_context(candidates)
        self.assertIn("Company A", context)
        self.assertNotIn("Company B", context)
        self.assertIn("not investment advice", context)

    def test_research_context_never_invents_price_data(self):
        # Only the actual retrieved headline text should appear — no numbers,
        # currency symbols, or price-like content the article didn't contain.
        candidates = [("Company A", [{"title": "A posts record profit"}])]
        context = research_candidates_context(candidates)
        self.assertNotIn("₹", context)
        self.assertNotIn("$", context)
        for word in context.split():
            self.assertFalse(word.strip(".,:-").isdigit(), f"unexpected numeric token in context: {word}")


class InsufficientMarketDataTests(unittest.TestCase):
    def test_no_data_for_any_candidate_is_insufficient(self):
        candidates = [(name, []) for name in RESEARCH_CANDIDATES]
        self.assertFalse(has_sufficient_market_data(candidates))
        self.assertEqual(research_candidates_context(candidates), "")

    def test_data_for_at_least_one_candidate_is_sufficient(self):
        candidates = [(RESEARCH_CANDIDATES[0], [{"title": "Some real headline"}])] + [
            (name, []) for name in RESEARCH_CANDIDATES[1:]
        ]
        self.assertTrue(has_sufficient_market_data(candidates))
        self.assertNotEqual(research_candidates_context(candidates), "")


class NormalStockNewsDoesNotNeedQwenTests(unittest.TestCase):
    def test_general_market_question_is_not_a_qwen_triggering_kind(self):
        # main.py only calls Qwen when intent.kind is one of these three.
        QWEN_TRIGGERING_KINDS = {"follow_up", "detailed_news", "specific_article"}
        intent = analyze_question("What's happening in the stock market?")
        self.assertNotIn(intent.kind, QWEN_TRIGGERING_KINDS)
        self.assertFalse(is_best_stock_question("What's happening in the stock market?"))

    def test_company_headline_question_is_not_a_qwen_triggering_kind(self):
        QWEN_TRIGGERING_KINDS = {"follow_up", "detailed_news", "specific_article"}
        intent = analyze_question("Tell me about Tata Motors")
        self.assertNotIn(intent.kind, QWEN_TRIGGERING_KINDS)


if __name__ == "__main__":
    unittest.main()