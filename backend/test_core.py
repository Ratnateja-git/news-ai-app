"""Offline regression tests for Priya's deterministic behaviour."""

import json
import unittest

from backend.intent import analyze_question, get_assistant_response
from backend.llm import clean_answer, headline_response
from backend.memory import add_turn, clear_memory, resolve_reference
from backend.news import deduplicate_articles, find_matching_article


class PriyaCoreTests(unittest.TestCase):
    def setUp(self):
        clear_memory()

    def test_creator_identity_is_deterministic(self):
        for question in ("Who created you?", "Who made you?", "Who developed Priya?"):
            self.assertIn("Ratnateja", get_assistant_response(question))

    def test_priya_identity_questions_remain_supported(self):
        self.assertIn("Priya", get_assistant_response("Who are you?"))
        self.assertIn("Priya", get_assistant_response("What is your name?"))

    def test_resolves_a_topic_reference(self):
        add_turn(user_question="What is cricket?", assistant_answer="A sport.", intent="general_knowledge", topic="cricket")
        resolved, clarification = resolve_reference("Who invented it?")
        self.assertEqual(resolved, "Who invented cricket?")
        self.assertIsNone(clarification)

    def test_resolves_a_person_reference(self):
        add_turn(user_question="Who is Virat Kohli?", assistant_answer="A cricketer.", intent="general_knowledge")
        resolved, clarification = resolve_reference("How old is he?")
        self.assertEqual(resolved, "How old is Virat Kohli?")
        self.assertIsNone(clarification)

    def test_resolves_person_possessive_reference(self):
        add_turn(user_question="Who is Virat Kohli?", assistant_answer="A cricketer.", intent="general_knowledge")
        resolved, clarification = resolve_reference("What is his age?")
        self.assertEqual(resolved, "What is Virat Kohli's age?")
        self.assertIsNone(clarification)

    def test_resolves_person_origin_reference(self):
        add_turn(user_question="Who is Virat Kohli?", assistant_answer="A cricketer.", intent="general_knowledge")
        resolved, clarification = resolve_reference("Where was he born?")
        self.assertEqual(resolved, "Where was Virat Kohli born?")
        self.assertIsNone(clarification)

    def test_ambiguous_people_require_clarification(self):
        add_turn(user_question="Who are Virat Kohli and Rohit Sharma?", assistant_answer="Cricketers.", intent="general_knowledge")
        _, clarification = resolve_reference("What is his age?")
        self.assertEqual(clarification, "Do you mean Virat Kohli or the other person we were discussing?")

    def test_keeps_related_topic_in_a_what_about_question(self):
        add_turn(user_question="What is AI?", assistant_answer="Artificial intelligence.", intent="general_knowledge", topic="AI")
        resolved, clarification = resolve_reference("What about machine learning?")
        self.assertEqual(resolved, "What about machine learning?")
        self.assertIsNone(clarification)

    def test_ambiguous_reference_asks_for_clarification(self):
        add_turn(user_question="Tell me about cricket and football.", assistant_answer="Both are sports.", intent="general_knowledge", topic="cricket, football")
        _, clarification = resolve_reference("Who won?")
        self.assertEqual(clarification, "Do you mean cricket or football?")

    def test_latest_question_is_not_rewritten_from_memory(self):
        add_turn(user_question="Yesterday's cricket news", assistant_answer="Old story.", intent="topic_news", topic="cricket")
        resolved, clarification = resolve_reference("Latest cricket news")
        self.assertEqual(resolved, "Latest cricket news")
        self.assertIsNone(clarification)

    def test_bangalore_normalizes_to_bengaluru(self):
        intent = analyze_question("What's the news in Bangalore?")
        self.assertEqual(intent.location, "bengaluru")
        self.assertEqual(intent.kind, "location_news")

    def test_ai_news_is_headlines_mode(self):
        intent = analyze_question("Tell me today's AI news")
        self.assertEqual(intent.category, "ai")
        self.assertFalse(intent.detailed)

    def test_detail_request_is_marked_detailed(self):
        self.assertTrue(analyze_question("Explain that news in detail", {"title": "A"}).detailed)

    def test_headlines_are_concise(self):
        context = json.dumps({"articles": [{"title": "One"}, {"title": "Two"}]})
        self.assertEqual(headline_response(context), "Sure. Here are the latest headlines. One. And Two.")

    def test_reasoning_is_removed(self):
        self.assertEqual(clean_answer("<think>private</think> **Answer** https://example.com"), "Answer")

    def test_duplicates_are_removed(self):
        self.assertEqual(len(deduplicate_articles([{"title": "Same news"}, {"title": "Same News"}])), 1)

    def test_matching_prefers_openai_article(self):
        articles = [{"title": "Sports update", "summary": ""}, {"title": "OpenAI launches a tool", "summary": "AI"}]
        self.assertEqual(find_matching_article(articles, "Tell me about OpenAI")["title"], "OpenAI launches a tool")


if __name__ == "__main__":
    unittest.main()
