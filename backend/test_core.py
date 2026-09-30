"""Offline regression tests for Priya's deterministic behaviour."""

import json
import unittest

from backend.intent import analyze_question, get_assistant_response, is_interview_learning_request
from backend.llm import build_interview_help_prompt, clean_answer, headline_response
from backend.memory import add_turn, clear_memory, resolve_reference
from backend.news import deduplicate_articles, find_matching_article
from backend.career.core import analyze_job_description, extract_projects, interview_question, questions_are_similar


class PriyaCoreTests(unittest.TestCase):
    def setUp(self):
        clear_memory()

    def test_creator_identity_is_deterministic(self):
        for question in ("Who created you?", "Who made you?", "Who developed Priya?"):
            self.assertIn("Ratnateja", get_assistant_response(question))

    def test_priya_identity_questions_remain_supported(self):
        self.assertIn("Priya", get_assistant_response("Who are you?"))
        self.assertIn("Priya", get_assistant_response("What is your name?"))

    def test_priya_identity_and_capabilities_are_context_aware(self):
        self.assertEqual(
            get_assistant_response("Who are you?"),
            "I'm Priya, an AI assistant and interview coach.",
        )
        self.assertIn("resume analysis", get_assistant_response("What can you do?"))

    def test_interview_help_detection_is_specific(self):
        self.assertTrue(is_interview_learning_request("I don't understand this question. Explain it."))
        self.assertTrue(is_interview_learning_request("Give me a hint but don't give me the answer."))
        self.assertTrue(is_interview_learning_request("What does this question mean?"))
        self.assertTrue(is_interview_learning_request("Can you explain what the interviewer is asking?"))
        self.assertFalse(is_interview_learning_request("What is today's news?"))

    def test_active_question_and_rephrasing_use_interview_help(self):
        active = "If an AI feature became too slow, how would you investigate and improve latency?"
        self.assertTrue(is_interview_learning_request(active, active))
        self.assertTrue(is_interview_learning_request("How would you investigate and reduce AI feature latency?", active))
        self.assertFalse(is_interview_learning_request("I would profile database and network latency first.", active))

    def test_interview_question_duplicate_matching_handles_all_prior_questions(self):
        asked = [
            "What is your strongest skill?",
            "Tell me about a difficult technical problem you faced and how you worked through it.",
        ]
        self.assertTrue(questions_are_similar("  TELL me about a difficult technical problem you faced and how you worked through it! ", asked))
        self.assertTrue(questions_are_similar("Describe a difficult technical problem and how you solved it.", asked))
        self.assertFalse(questions_are_similar("How would you validate a machine learning model?", asked))

    def test_duplicate_generated_question_is_skipped_for_a_new_question(self):
        profile = {"projects": ["Priya News AI | Python"], "skills": ["python"], "tools": []}
        job = {"required_skills": ["python"], "technical_domains": []}
        duplicate = "Tell me about a difficult technical problem you faced and how you worked through it."
        question, category = interview_question(profile, job, "intermediate", round_name="behavioral", asked_questions=[duplicate])
        self.assertNotEqual(question, duplicate)
        self.assertEqual(category, "behavioral")

    def test_interview_help_prompt_keeps_the_current_question(self):
        prompt = build_interview_help_prompt("Give me a hint.", "What is overfitting?")
        self.assertIn("What is overfitting?", prompt)
        self.assertIn("Do not evaluate or score", prompt)

    def test_project_extraction_counts_titles_not_project_bullets(self):
        resume = """EDUCATION
Bachelor of Technology

PROJECTS
Priya News AI
- Built a voice-based news assistant.
- Used FastAPI, Ollama and Kokoro.

MarketMind AI
- Built a business-location recommendation system.
- Used Python and PostgreSQL.

SKILLS
Python, FastAPI
"""
        self.assertEqual(extract_projects(resume), ["Priya News AI", "MarketMind AI"])

    def test_contradictory_jd_is_flagged_without_a_silent_interpretation(self):
        result = analyze_job_description({"skills": ["python"], "projects": ["AI Coach"], "experience": [], "internships": [], "education": []}, "Senior Architect with 5+ years experience. Entry-level candidates willing to learn are welcome.")
        self.assertTrue(result["contradiction"]["contradiction_detected"])
        self.assertTrue(result["contradiction"]["should_warn_user"])
        self.assertIsNone(result["contradiction"]["recommended_interpretation"])
        self.assertIn("do not rewrite your resume to appear senior", result["recommendations"]["recommendations"][0].lower())

    def test_entry_level_jd_is_not_flagged(self):
        profile = {"skills": ["python"], "projects": [], "experience": [], "internships": [], "education": []}
        self.assertFalse(analyze_job_description(profile, "Entry-level AI Engineer. 0-1 years experience.")["contradiction"]["contradiction_detected"])

    def test_senior_jd_is_not_flagged(self):
        profile = {"skills": ["python"], "projects": [], "experience": [], "internships": [], "education": []}
        self.assertFalse(analyze_job_description(profile, "Senior Software Engineer. 5+ years experience.")["contradiction"]["contradiction_detected"])

    def test_senior_architect_mentoring_jd_is_not_flagged(self):
        profile = {"skills": ["python"], "projects": [], "experience": [], "internships": [], "education": []}
        self.assertFalse(analyze_job_description(profile, "Senior Architect. 5+ years experience. Must mentor junior engineers.")["contradiction"]["contradiction_detected"])

    def test_semantic_equivalent_conflict_is_flagged(self):
        profile = {"skills": ["python"], "projects": [], "experience": [], "internships": [], "education": []}
        result = analyze_job_description(profile, "Lead platform engineer with 6 years of experience. Recent graduates are encouraged to apply.")
        self.assertTrue(result["contradiction"]["contradiction_detected"])

    def test_conflict_recommendation_never_requests_invented_experience(self):
        profile = {"skills": ["python"], "projects": [], "experience": [], "internships": [], "education": []}
        result = analyze_job_description(profile, "Senior Architect with 5+ years experience. Entry-level candidates welcome.")
        advice = " ".join(result["recommendations"]["recommendations"]).lower()
        self.assertIn("do not rewrite your resume to appear senior", advice)
        self.assertNotIn("claim 5 years", advice)

    def test_conflict_interview_question_does_not_assume_senior_years(self):
        question, _ = interview_question({"projects": ["AI Coach"], "skills": ["python"], "tools": []}, {"required_skills": ["python"], "technical_domains": [], "contradiction": {"contradiction_detected": True}}, "intermediate")
        self.assertIn("entry-level expectations", question)
        self.assertNotIn("5 years", question.lower())

    def test_project_extraction_ignores_experience_without_a_projects_section(self):
        resume = """EXPERIENCE
Software Intern
- Developed an internal application.

SKILLS
Python, FastAPI, SQL

CERTIFICATIONS
Cloud Fundamentals
"""
        self.assertEqual(extract_projects(resume), [])

    def test_project_extraction_recognizes_academic_projects_and_bulleted_titles(self):
        resume = """ACADEMIC PROJECTS
• Spam Detection API | Python, FastAPI | 2024
- Built a spam classifier.

• VisionCart AI | PyTorch, OpenCV
- Built an object detection application.

EDUCATION
Bachelor of Science
"""
        self.assertEqual(extract_projects(resume), ["Spam Detection API", "VisionCart AI"])

    def test_project_extraction_keeps_multiple_detail_bullets_with_one_title(self):
        resume = """TECHNICAL PROJECTS
Portfolio Tracker
- Designed the data model.
- Implemented the dashboard.
- Tested error handling.

ACHIEVEMENTS
Hackathon finalist
"""
        self.assertEqual(extract_projects(resume), ["Portfolio Tracker"])

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
