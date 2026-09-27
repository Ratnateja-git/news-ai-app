"""Deterministic question classification for Priya."""

import re
from dataclasses import dataclass

from .identity import CREATOR_NAME


# ============================================================
# LOCATIONS
# ============================================================

LOCATIONS = {
    "bangalore": "bengaluru",
    "bengaluru": "bengaluru",
    "mysore": "mysuru",
    "mysuru": "mysuru",
    "delhi": "delhi",
    "mumbai": "mumbai",
    "hyderabad": "hyderabad",
    "chennai": "chennai",
    "kolkata": "kolkata",
    "pune": "pune",
}


# ============================================================
# CATEGORIES
# ============================================================

CATEGORY_KEYWORDS = {
    "ai": (
        "ai",
        "artificial intelligence",
        "openai",
        "chatgpt",
        "anthropic",
        "claude",
        "gemini",
        "machine learning",
    ),
    "market": (
        "stock",
        "stocks",
        "share",
        "shares",
        "market",
        "stock market",
        "nifty",
        "sensex",
        "nse",
        "bse",
        "equity",
        "trading",
        "invest",
        "investing",
        "ipo",
        "mutual fund",
        "bank nifty",
        "banking sector",
        "trading news",
    ),
    "technology": (
        "technology",
        "tech",
        "cyber",
        "software",
        "startup",
        "gadget",
    ),
    "business": (
        "business",
        "economy",
        "finance",
    ),
    "sports": (
        "sports",
        "cricket",
        "football",
        "tennis",
        "ipl",
    ),
    "politics": (
        "politics",
        "election",
        "government",
        "minister",
        "parliament",
    ),
    "entertainment": (
        "entertainment",
        "movie",
        "movies",
        "film",
        "films",
        "celebrity",
        "bollywood",
    ),
    "science": (
        "science",
        "space",
        "nasa",
        "research",
    ),
    "health": (
        "health",
        "medical",
        "hospital",
        "disease",
    ),
    "world": (
        "world",
        "international",
        "global",
    ),
}


# ============================================================
# TOPICS
# ============================================================

TOPIC_KEYWORDS = {
    "cricket": "cricket",
    "ipl": "ipl",
    "football": "football",
    "tennis": "tennis",
}


# ============================================================
# QUESTION TYPES
# ============================================================

DEFINITIONAL_MARKERS = (
    "what is",
    "what are",
    "who is",
    "who are",
    "what does",
    "what do",
    "define",
    "definition of",
    "meaning of",
    "explain",
)

NEWS_REQUEST_MARKERS = (
    "news",
    "headline",
    "headlines",
    "top stories",
    "latest",
    "latest on",
    "current events",
    "happening today",
    "happening now",
    "recent news",
    "today's news",
)
FRESHNESS_MARKERS = (
    "latest",
    "new",
    "today",
    "trending",
    "current",
    "recent",
)

DETAIL_MARKERS = (
    "in detail",
    "detailed",
    "tell me more",
    "more details",
    "know more",
    "need to know more",
    "more about",
    "explain",
    "why is",
    "why did",
    "what happened",
    "full story",
    "elaborate",
)

FOLLOW_UP_MARKERS = (
    "tell me more",
    "know more",
    "more about that",
    "explain that",
    "why is that",
    "why did that",
    "what about that",
    "what happened next",
    "what happened after that",
    "give me more details",
    "elaborate",
    "who won",
    "who invented it",
    "how old is he",
    "how old is she",
)


# Movie recommendations are general knowledge, not entertainment news. Route
# them before generic search so their facts can be filtered by film language.
TELUGU_MOVIE_RECOMMENDATION_PATTERN = re.compile(
    r"\btelugu\b.*\b(?:movie|movies|film|films|cinema|thriller|thrillers|"
    r"horror|mystery|recommend|recommendation|best|good)\b|"
    r"\b(?:movie|movies|film|films|cinema|thriller|thrillers|horror|mystery|"
    r"recommend|recommendation|best|good)\b.*\btelugu\b",
    re.IGNORECASE,
)


# ============================================================
# ASSISTANT INTENT
# ============================================================

ASSISTANT_INTENT_RESPONSES = (
    (
        r"\bwhat(?:'s| is) your name\b",
        "My name is Priya. I'm your AI assistant, and I can help you with news, technology, general knowledge, stock market information, and much more.",
    ),
    (
        r"\bwho are you\b|\btell me about yourself\b",
        "I'm Priya, your AI assistant. I can help you with news, technology, general knowledge, stock market information, and much more.",
    ),
    (
        r"\bwhat can you do\b|\bhow can you help me\b|\bcan you help me\b",
        "I can help you with news, technology, general knowledge, stock market information, and much more.",
    ),
    (
        r"\b(?:who (?:created|made|developed|built) (?:you|priya)|who is (?:your|the) (?:creator|developer)|who is behind (?:you|priya))\b",
        f"I was developed by {CREATOR_NAME}.",
    ),
    (
        r"\bare you (?:an? )?ai\b",
        "Yes, I'm Priya, an AI assistant. I can help you with news, technology, general knowledge, stock market information, and much more.",
    ),
    (
        r"\bwhat are you (?:doing|up to)\b",
        "I'm right here, ready to help. I can look up news, market updates, or just chat — what would you like?",
    ),
)

CONVERSATIONAL_INTENT_RESPONSES = (
    (
        r"\b(?:do you know|can you tell me|tell me)\b.*\btelugu songs?\b",
        "Yes. I know many Telugu songs. If you want, I can suggest songs by mood or genre.",
    ),
    (
        r"\bdo you know cricket\b",
        "Yes. I can talk about cricket, explain the game, or help with cricket news when you ask for it.",
    ),
    (
        r"\btell me something interesting\b",
        "I can share something interesting about science, history, sports, or technology. Which topic would you like?",
    ),
)
# ============================================================
# CASUAL / GREETING INTENT
# ============================================================
# Everyday conversational openers/closers, answered instantly in Python —
# no Gemma call needed. Grouped by category (not just "is this casual")
# so main.py can reply with something that actually fits what was said,
# instead of one generic greeting for every kind of small talk. Patterns
# are loose (repeated letters, optional punctuation, an optional trailing
# "priya") but still whole-message matches, so a real question is never
# mistaken for small talk.

CASUAL_GREETING_PATTERNS = (
    r"h+i+(?: there)?",
    r"h+e+y+a?(?: there)?",
    r"h+e+l+l+o+(?: there)?",
    r"yo",
    r"sup",
    r"what'?s up",
    r"whats up",
    r"good morning",
    r"good afternoon",
    r"good evening",
    r"namaste",
    r"greetings",
    r"howdy",
)

CASUAL_WELLBEING_PATTERNS = (
    r"how are you(?: doing)?(?: today)?",
    r"how'?s it going",
    r"hows it going",
    r"how are things(?: with you)?",
    r"how have you been",
    r"how (?:are|'?re) you feeling",
    r"how you doin'?",
    r"you good",
    r"you okay",
    r"you ok",
    r"what'?s up with you",
)

CASUAL_THANKS_PATTERNS = (
    r"thanks?(?: you)?(?: so much| a lot| a ton)?",
    r"thank you",
    r"thanks a bunch",
    r"thx",
    r"ty",
    r"appreciate it",
    r"much appreciated",
    r"you'?re a lifesaver",
)

CASUAL_BYE_PATTERNS = (
    r"bye+",
    r"bye bye",
    r"goodbye",
    r"good night",
    r"see you(?: later| soon| around)?",
    r"see ya",
    r"talk(?: to you)? later",
    r"catch you later",
    r"i'?m (?:leaving|off|heading out|done(?: for now)?)",
    r"gotta go",
    r"take care",
)

CASUAL_ACK_PATTERNS = (
    r"ok(?:ay)?",
    r"okay cool",
    r"cool",
    r"nice",
    r"great",
    r"got it",
    r"alright",
    r"sounds good",
    r"fair enough",
)

_CASUAL_GROUPS = (
    ("greeting", CASUAL_GREETING_PATTERNS),
    ("wellbeing", CASUAL_WELLBEING_PATTERNS),
    ("thanks", CASUAL_THANKS_PATTERNS),
    ("bye", CASUAL_BYE_PATTERNS),
    ("ack", CASUAL_ACK_PATTERNS),
)

# "hey priya", "thanks priya" etc. are common — strip a trailing "priya"
# (and surrounding punctuation) before matching so it doesn't need to be
# spelled out in every single pattern above.
_TRAILING_PRIYA = re.compile(r"[\s,]*priya[.!?]*$", re.IGNORECASE)
_EDGE_PUNCT = re.compile(r"^[\s.!?,]+|[\s.!?,]+$")


def classify_casual(text: str) -> str | None:
    """Return which everyday-conversation category `text` is, or None.

    Used both to decide the "casual" intent (see analyze_question) and,
    in main.py, to pick a reply that actually matches what was said
    (greeting vs. thanks vs. goodbye) instead of one generic response.
    """
    cleaned = _EDGE_PUNCT.sub("", _TRAILING_PRIYA.sub("", text.strip()))
    if not cleaned:
        return None
    for category, patterns in _CASUAL_GROUPS:
        if any(re.fullmatch(pattern, cleaned) for pattern in patterns):
            return category
    return None


def _is_casual(text: str) -> bool:
    return classify_casual(text) is not None


def _is_conversational(text: str) -> bool:
    """Match a few safe, non-time-sensitive requests without retrieval."""
    return (
        not any(_contains_phrase(text, marker) for marker in FRESHNESS_MARKERS)
        and any(re.search(pattern, text) for pattern, _ in CONVERSATIONAL_INTENT_RESPONSES)
    )

# ============================================================
# INTENT MODEL
# ============================================================

@dataclass(frozen=True)
class Intent:
    kind: str
    category: str
    location: str | None
    detailed: bool
    topic: str | None = None


# ============================================================
# HELPERS
# ============================================================

def _contains_phrase(text: str, phrase: str) -> bool:
    """
    Match a phrase safely.

    Single-word terms use word boundaries.
    Multi-word phrases use escaped substring matching.
    """
    if " " not in phrase:
        return bool(re.search(rf"\b{re.escape(phrase)}\b", text))

    return phrase in text


def _detect_category(text: str) -> str:
    for category, words in CATEGORY_KEYWORDS.items():
        if any(_contains_phrase(text, word) for word in words):
            return category

    return "general"


def _detect_topic(text: str) -> str | None:
    """
    Detect a specific topic such as cricket or football.
    """
    topics = [topic for phrase, topic in TOPIC_KEYWORDS.items() if _contains_phrase(text, phrase)]
    return ", ".join(dict.fromkeys(topics)) or None


def _is_definitional(text: str) -> bool:
    return any(
        marker in text
        for marker in DEFINITIONAL_MARKERS
    )


def _is_news_request(text: str) -> bool:
    return any(
        marker in text
        for marker in NEWS_REQUEST_MARKERS
    )


def is_telugu_movie_recommendation(text: str) -> bool:
    """Return True for Telugu-film recommendation queries, never news."""

    return bool(TELUGU_MOVIE_RECOMMENDATION_PATTERN.search(text))


# ============================================================
# MAIN CLASSIFIER
# ============================================================

def analyze_question(
    question: str,
    previous_article: dict | None = None,
) -> Intent:

    text = question.lower().strip()
    # Career phrases are checked before news/general routing, so existing
    # headline and knowledge intents retain their current behavior.
    career_patterns = (
        ("resume_analyze", ("analyze my resume", "review my resume")),
        ("resume_tailor", ("tailor my resume", "improve my resume")),
        ("job_match", ("match my resume", "compare my resume")),
        ("skill_gap", ("skills am i missing", "skill gaps")),
        ("interview_start", ("start my mock interview", "start an interview")),
        ("interview_continue", ("continue the interview", "continue my interview")),
        ("interview_report", ("how did i perform", "interview report")),
    )
    for kind, phrases in career_patterns:
        if any(phrase in text for phrase in phrases):
            return Intent(kind=kind, category="career", location=None, detailed=False, topic=None)
       
    # --------------------------------------------------------
    # 1. ASSISTANT QUESTIONS
    # --------------------------------------------------------

    if any(
        re.search(pattern, text)
        for pattern, _ in ASSISTANT_INTENT_RESPONSES
    ):
        return Intent(
            kind="assistant",
            category="assistant",
            location=None,
            detailed=False,
            topic=None,
        )
        # --------------------------------------------------------
    # 2. CASUAL / GREETING
    # --------------------------------------------------------

    if _is_casual(text):
        return Intent(
            kind="casual",
            category="assistant",
            location=None,
            detailed=False,
            topic=None,
        )

    if _is_conversational(text):
        return Intent(
            kind="conversational",
            category="assistant",
            location=None,
            detailed=False,
            topic=None,
        )

    # --------------------------------------------------------
    # 2. DETECT BASIC ATTRIBUTES
    # --------------------------------------------------------

    location = next(
        (
            normalized
            for phrase, normalized in LOCATIONS.items()
            if _contains_phrase(text, phrase)
        ),
        None,
    )

    category = _detect_category(text)
    topic = _detect_topic(text)

    is_news_request = _is_news_request(text)

    follow_up = (
        bool(previous_article)
        and any(
            marker in text
            for marker in FOLLOW_UP_MARKERS
        )
    )

    detailed = (
        follow_up
        or any(
            marker in text
            for marker in DETAIL_MARKERS
        )
    )

    specific = (
        bool(previous_article)
        and (
            follow_up
            or "that" in text
        )
    ) or any(
        marker in text
        for marker in (
            "the openai story",
            "the story",
            "about openai",
            "about chatgpt",
            "about anthropic",
        )
    )

    # --------------------------------------------------------
    # 3. FOLLOW-UP
    # --------------------------------------------------------

    if follow_up:
        return Intent(
            kind="follow_up",
            category=category,
            location=location,
            detailed=True,
            topic=topic,
        )

    # --------------------------------------------------------
    # 4. EXPLICIT NEWS REQUEST
    #
    # News words take priority over category words.
    #
    # "cricket news"
    # -> topic_news
    #
    # "AI news"
    # -> category_news
    # --------------------------------------------------------

    if is_news_request:

        if topic:
            return Intent(
                kind="topic_news",
                category=category,
                location=location,
                detailed=detailed,
                topic=topic,
            )

        if location:
            return Intent(
                kind="location_news",
                category=category,
                location=location,
                detailed=detailed,
                topic=topic,
            )

        if category != "general":
            return Intent(
                kind="category_news",
                category=category,
                location=location,
                detailed=detailed,
                topic=topic,
            )

        return Intent(
            kind="headlines",
            category="general",
            location=location,
            detailed=detailed,
            topic=None,
        )

    # --------------------------------------------------------
    # 5. TELUGU FILM RECOMMENDATIONS
    # --------------------------------------------------------

    if is_telugu_movie_recommendation(text):
        return Intent(
            kind="telugu_movie_recommendation",
            category="general",
            location=None,
            detailed=False,
            topic=None,
        )

    # --------------------------------------------------------
    # 6. DEFINITIONS / GENERAL KNOWLEDGE
    #
    # This happens BEFORE category routing.
    #
    # "What is cricket?"
    # -> general_knowledge
    #
    # "Explain football"
    # -> general_knowledge
    #
    # "What is AI?"
    # -> general_knowledge
    # --------------------------------------------------------

    if _is_definitional(text):
        return Intent(
            kind="general_knowledge",
            category="general",
            location=None,
            detailed=False,
            topic=topic,
        )

    # --------------------------------------------------------
    # 6. SPECIFIC ARTICLE
    # --------------------------------------------------------

    if specific:
        return Intent(
            kind="specific_article",
            category=category,
            location=location,
            detailed=detailed,
            topic=topic,
        )

    # --------------------------------------------------------
    # 7. DETAILED NEWS
    # --------------------------------------------------------

    if detailed and (
        location
        or category != "general"
        or specific
    ):
        return Intent(
            kind="detailed_news",
            category=category,
            location=location,
            detailed=True,
            topic=topic,
        )

    # --------------------------------------------------------
    # 8. LOCATION NEWS
    # --------------------------------------------------------

    if location:
        return Intent(
            kind="location_news",
            category=category,
            location=location,
            detailed=detailed,
            topic=topic,
        )

    # --------------------------------------------------------
    # 9. CATEGORY MENTION WITHOUT EXPLICIT NEWS OR A DEFINITION
    #
    # A category word alone (no "news"/"latest" and no "what is"/
    # "explain") is normally just conversation about the topic —
    # an opinion, a passing remark, a follow-up thought — not a
    # request to look something up. That belongs to the general
    # chat fallback (Gemma, no search grounding required).
    #
    # Example:
    # "cricket news"          -> topic_news / category_news (step 4)
    # "what is cricket"       -> general_knowledge (step 6, search-grounded)
    # "do you think AI is useful" -> chat
    # --------------------------------------------------------

    if category != "general":
        return Intent(
            kind="chat",
            category="general",
            location=None,
            detailed=False,
            topic=topic,
        )

    # --------------------------------------------------------
    # 10. FALLBACK — the general conversation fallback
    #
    # Nothing above matched: not a greeting, not news, not a
    # definition, not a category mention. This is the broad catch-
    # all so Priya never says "I don't understand" just because a
    # question wasn't predefined — it goes to Gemma as free-form
    # conversation (greetings already handled, so this covers things
    # like small talk, opinions, hypotheticals, "explain X simply",
    # follow-ups that don't fit a specific pattern, and any other
    # reasonable natural-language message).
    # --------------------------------------------------------

    return Intent(
        kind="chat",
        category="general",
        location=location,
        detailed=detailed,
        topic=topic,
    )


# ============================================================
# ASSISTANT RESPONSE
# ============================================================

def get_assistant_response(question: str) -> str:

    text = question.lower().strip()

    for pattern, response in ASSISTANT_INTENT_RESPONSES:
        if re.search(pattern, text):
            return response

    return "I'm Priya, your AI assistant. How can I help you today?"


def get_conversational_response(question: str) -> str:
    """Return a deterministic response for non-time-sensitive conversation."""
    text = question.lower().strip()
    for pattern, response in CONVERSATIONAL_INTENT_RESPONSES:
        if re.search(pattern, text):
            return response

    return "I'm here to help. What would you like to know?"
