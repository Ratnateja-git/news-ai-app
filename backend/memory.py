"""Lightweight, bounded conversation memory for the local Priya app."""

from __future__ import annotations

import re
from collections import deque
from typing import Any

MAX_TURNS = 8
_turns: deque[dict[str, Any]] = deque(maxlen=MAX_TURNS)
REFERENCE_WORDS = (" it", " that", " this", " he", " she", " they", " his ", " her ", " him", " its ", "the story", "the match", "the article", "that news")
FOLLOW_UP_PHRASES = ("tell me more", "explain that", "explain this", "why?", "why did", "what happened next", "what about", "when did that happen", "where did that happen", "how did that happen", "what does that mean", "and then", "what happened after that", "give me more details", "elaborate", "who won", "how old is", "who invented")
QUESTION_LEADS = {"what", "who", "where", "when", "why", "how", "tell", "explain"}
PERSON_QUESTION = re.compile(r"^\s*(?:who is|who are|tell me about)\s+", re.IGNORECASE)


def _subjects(question: str, topic: str | None) -> list[str]:
    subjects = [part.strip() for part in (topic or "").split(",") if part.strip()]
    for name in re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", question):
        if name.split()[0].lower() not in QUESTION_LEADS:
            subjects.append(name)
    return list(dict.fromkeys(subjects))


def _person_entities(question: str) -> list[str]:
    """Extract explicitly named people from a person-focused question."""
    if not PERSON_QUESTION.match(question):
        return []
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", question)
    return list(dict.fromkeys(name for name in names if name.split()[0].lower() not in QUESTION_LEADS))


def add_turn(*, user_question: str, assistant_answer: str, intent: str, topic: str | None = None, category: str | None = None, location: str | None = None, article: dict | None = None) -> None:
    """Store one compact turn; the deque automatically discards old turns."""
    entities = _person_entities(user_question)
    _turns.append({"user_question": user_question, "assistant_answer": assistant_answer, "intent": intent, "topic": topic or (entities[0] if entities else None), "category": category, "location": location, "article": article, "subjects": _subjects(user_question, topic), "entities": entities, "last_entity": entities[0] if len(entities) == 1 else None, "last_entity_type": "person" if len(entities) == 1 else None})


def add_image_turn(question: str, description: str, answer: str) -> None:
    """Remember only Priya's textual image context, never private image bytes."""
    add_turn(
        user_question=question or "Describe the uploaded image",
        assistant_answer=answer,
        intent="vision",
        topic=description[:180],
        category="vision",
    )


def get_recent_memory(limit: int = MAX_TURNS) -> list[dict[str, Any]]:
    return list(_turns)[-max(0, limit):]


def get_last_topic() -> str | None:
    for turn in reversed(_turns):
        if turn.get("topic"):
            return str(turn["topic"])
        if turn.get("subjects"):
            return str(turn["subjects"][0])
    return None


def get_last_entity() -> str | None:
    for turn in reversed(_turns):
        if turn.get("last_entity"):
            return str(turn["last_entity"])
    return None


def get_entity_state() -> dict[str, str | None]:
    """Expose the compact entity state used by deterministic resolution."""
    for turn in reversed(_turns):
        if turn.get("last_entity"):
            return {"last_entity": turn["last_entity"], "last_topic": turn.get("topic"), "last_entity_type": turn.get("last_entity_type"), "last_intent": turn.get("intent")}
    return {"last_entity": None, "last_topic": get_last_topic(), "last_entity_type": None, "last_intent": None}


def format_recent_context(limit: int = 3, max_answer_chars: int = 160) -> str:
    """Compact recent turns for the chat fallback prompt (llm.ask_chat_model).

    This is a loose conversational summary, not exact-fact grounding —
    each answer is truncated to keep the prompt small. Assistant-identity
    turns aren't stored (see main._answer_payload), so this only ever
    reflects real conversation content.
    """
    recent = get_recent_memory(limit)
    if not recent:
        return ""

    lines = []
    for turn in recent:
        question = (turn.get("user_question") or "").strip()
        answer = (turn.get("assistant_answer") or "").strip()
        if not question:
            continue
        if len(answer) > max_answer_chars:
            answer = answer[:max_answer_chars].rsplit(" ", 1)[0].rstrip() + "…"
        lines.append(f"- User asked: {question} | Priya said: {answer}")

    return "\n".join(lines)


def get_last_article() -> dict | None:
    return next((turn["article"] for turn in reversed(_turns) if turn.get("article")), None)


def clear_memory() -> None:
    _turns.clear()


def is_reference_question(question: str) -> bool:
    text = f" {question.lower().strip()} "
    return any(word in text for word in REFERENCE_WORDS) or any(phrase in text for phrase in FOLLOW_UP_PHRASES)


def get_relevant_memory(question: str) -> list[dict[str, Any]]:
    return list(reversed(_turns))[:1] if is_reference_question(question) else []


def resolve_reference(question: str) -> tuple[str, str | None]:
    """Expand an unambiguous reference; otherwise return a clarification."""
    relevant = get_relevant_memory(question)
    if not relevant:
        return question, None
    turn = relevant[0]
    entities = turn.get("entities") or []
    if len(entities) > 1:
        return question, f"Do you mean {entities[0]} or the other person we were discussing?"
    entity = turn.get("last_entity") or get_last_entity()
    subjects = turn.get("subjects") or []
    if not entity and len(subjects) > 1:
        return question, f"Do you mean {' or '.join(subjects[:2])}?"
    if not entity and not subjects:
        return question, None
    subject, lowered = entity or subjects[0], question.lower().strip()
    if re.search(r"\b(?:his|her)\b", lowered):
        return re.sub(r"\b(?:his|her)\b", f"{subject}'s", question, flags=re.IGNORECASE), None
    if re.search(r"\bhow old is (?:he|she)\b", lowered):
        return re.sub(r"\b(?:he|she)\b", subject, question, flags=re.IGNORECASE), None
    if re.search(r"\b(?:he|she|him|her)\b", lowered):
        return re.sub(r"\b(?:he|she|him|her)\b", subject, question, flags=re.IGNORECASE), None
    if re.search(r"\bwho invented it\b", lowered):
        return re.sub(r"\bit\b", subject, question, flags=re.IGNORECASE), None
    if "its " in lowered:
        return re.sub(r"\bits\b", f"{subject}'s", question, flags=re.IGNORECASE), None
    if any(word in lowered for word in ("it", "that", "this", "he", "she", "they", "him", "her")):
        return f"About {subject}: {question}", None
    return question, None