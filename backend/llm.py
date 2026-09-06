"""gemma3 integration for Priya News AI.

gemma is used ONLY for detailed follow-up explanations. Normal headline
requests are handled entirely in Python via headline_response() and never
touch Ollama — see main.py for the routing decision.
"""

import json
import re
import time

import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "gemma3:4b"


def warm_ollama() -> None:
    """Ask Ollama to keep the configured local model ready without blocking startup."""
    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json={"model": MODEL_NAME, "keep_alive": "10m", "stream": False},
            timeout=10,
        )
        response.raise_for_status()
        print(f"[PERF][LLM] warm-up ready: {MODEL_NAME}")
    except requests.RequestException as error:
        print(f"[PERF][LLM] warm-up skipped: {type(error).__name__}")


def is_in_depth_question(question: str) -> bool:
    """Return True when the user explicitly asks for details.

    Kept for backward compatibility; routing in main.py now uses
    intent.analyze_question() instead, which is word-boundary safe.
    """
    text = question.lower().strip()

    detail_phrases = [
        "in depth",
        "in-depth",
        "in detail",
        "detailed",
        "more details",
        "more detail",
        "tell me more",
        "more about",
        "explain this",
        "explain that",
        "explain the",
        "explain about",
        "give me details",
        "give details",
        "full story",
        "full details",
        "elaborate",
        "what happened",
        "why did this happen",
        "how did this happen",
        "what does this mean",
    ]

    return any(phrase in text for phrase in detail_phrases)


def headline_response(context: str) -> str:
    """Build a deterministic, spoken-style headline list — NO Qwen call.

    `context` is the JSON string produced by news.get_news_context(), e.g.
    '{"articles": [{"title": "One"}, {"title": "Two"}]}'.
    """
    started = time.perf_counter()
    try:
        data = json.loads(context) if context else {}
    except (TypeError, ValueError):
        data = {}

    articles = data.get("articles", []) if isinstance(data, dict) else []
    titles = [a.get("title", "").strip() for a in articles if a.get("title")]
    titles = titles[:5]

    if not titles:
        print(f"[PERF][LLM] headline_response: {time.perf_counter() - started:.3f}s")
        return "Sorry, I couldn't find any current headlines for that."

    if len(titles) == 1:
        body = f"{titles[0]}."
    else:
        *head, last = titles
        body = ". ".join(head) + f". And {last}."

    answer = f"Sure. Here are the latest headlines. {body}"
    print(f"[PERF][LLM] headline_response: {time.perf_counter() - started:.3f}s")
    return answer


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks only — nothing else.

    Gemma3 sometimes emits a thinking block even with "think": False set.
    This is used BOTH by clean_answer() (cosmetic cleanup for the final
    spoken answer) AND, on its own, by the validator/retry flow BEFORE any
    other cleanup runs — so looks_like_reasoning() checks the model's real
    words instead of a version where leak phrases have already been
    scrubbed out by clean_answer()'s phrase removal.
    """
    if not text:
        return ""

    # Well-formed pairs.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Stray closing tag with no matching opening removed above — keep only
    # what follows the last closing tag.
    if re.search(r"</think>", text, re.IGNORECASE):
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]

    # Unclosed opening tag — everything from there on is unterminated
    # reasoning with no confirmed end. Keep only what came before it
    # rather than risk exposing raw reasoning text.
    if re.search(r"<think", text, re.IGNORECASE):
        text = re.split(r"<think", text, flags=re.IGNORECASE)[0]

    return text.strip()


def clean_answer(text: str) -> str:
    """Remove thinking, markdown and internal reasoning."""
    if not text:
        return ""

    # --------------------------------------------------------
    # Remove Qwen thinking blocks
    # --------------------------------------------------------
    text = strip_think_tags(text)

    # --------------------------------------------------------
    # Remove markdown
    # --------------------------------------------------------
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("###", "")
    text = text.replace("##", "")
    text = text.replace("#", "")

    # Remove URLs.
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)

    # The UI already identifies Priya; remove only a leading speaker label.
    text = re.sub(r"^\s*Priya\s*:\s*", "", text, flags=re.IGNORECASE)

    # --------------------------------------------------------
    # Remove obvious internal reasoning preambles
    # --------------------------------------------------------
    bad_patterns = [
        r"(?is)^.*?\bwe are given\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bthe user says\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bthe user wants\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bI need to\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bI should\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bLet me\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
        r"(?is)^.*?\bSteps:\b.*?(?=\bSure\b|\bHere are\b|\bOpenAI\b)",
    ]
    for pattern in bad_patterns:
        text = re.sub(pattern, "", text)

    unwanted_phrases = [
        "according to the context",
        "according to the supplied context",
        "based on the context",
        "based on the supplied context",
        "from the context",
        "from the supplied context",
        "the news context",
        "the news given",
        "the user asked",
        "the user wants",
        "the user's request",
        "understand the user's request",
        "act as priya",
        "i need to analyze",
        "i need to identify",
        "i need to understand",
        "i should identify",
        "i should pick",
        "let me analyze",
        "let me check",
        "let me look",
        "first, i need to",
        "the answer should",
        "my reasoning",
        "important rules",
        "important constraints",
        "strict rules",
        "response rules",
        "final answer only",
        "key points",
    ]
    for phrase in unwanted_phrases:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)

    # --------------------------------------------------------
    # Remove article numbering / lists
    # --------------------------------------------------------
    text = re.sub(r"(?i)\barticle\s+\d+\s*[:.)-]?\s*", "", text)
    text = re.sub(r"(?m)^\s*\d+[\.\)]\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*•]\s*", "", text)

    # --------------------------------------------------------
    # Clean whitespace
    # --------------------------------------------------------
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)

    return text.strip()


def build_prompt(question: str, context: str) -> str:
    """Build a SHORT prompt for a detailed explanation of a single article.

    Deliberately minimal: long "do not mention X / do not say Y" instruction
    blocks in the user turn are exactly what small local models like
    qwen3:4b tend to echo back. The rules live in the system message
    (ask_ollama) instead; this just supplies the facts and the question.
    """
    return f"""ARTICLE:
{context}

QUESTION: {question}

Answer in 3 to 5 short spoken sentences, using only the ARTICLE above."""


def build_retry_prompt(question: str, context: str) -> str:
    """Even shorter fallback prompt used once if the first answer leaks reasoning."""
    return f"""ARTICLE:
{context}

In 2 short sentences, state only the key fact that answers: {question}"""


REASONING_LEAK_MARKERS = (
    # Original markers
    "the user's request",
    "understand the user's request",
    "the user wants",
    "the user asked",
    "we are given",
    "the news given",
    "key points",
    "important constraint",
    "response rules",
    "the prompt",
    "the instructions",
    "system message",
    "system prompt",
    "steps:",
    "first, i need",
    "let me analyze",
    "let me check",
    "let me think",
    "i need to understand",
    "i need to analyze",
    "i need to identify",
    "i should",
    "according to the context",
    "understand the user",
    "act as priya",
    "my reasoning",
    "<think",
    # References to "the user" as a third party (a real answer never does this)
    "the user is asking",
    "the user is asking about",
    "the user wrote",
    "the user says",
    "the user's question",
    "the user's query",
    "the question asks",
    "the question is asking",
    "what the user wants",
    "what the user is asking",
    # Narrating the analysis process
    "i see that",
    "i notice that",
    "i realize that",
    "i need to be careful",
    "i need to figure out",
    "i need to determine",
    "i need to check",
    "i need to look at",
    "i need to find",
    "i need to make sure",
    "i want to make sure",
    "i have to consider",
    "i have to make sure",
    "i should be careful",
    "i should note",
    "i should mention",
    "i should focus",
    "i should make sure",
    "i must be careful",
    "i must make sure",
    "considering the question",
    "given the question",
    "in order to answer",
    "to answer this question",
    "to answer the question",
    "to respond to this question",
    "in response to the question",
    "my thought process",
    "my internal reasoning",
    "chain of thought",
    "internal monologue",
    "thinking through this",
    "thinking about how to",
    "let's answer",
    "let's think",
    "let's see",
    "let's break this down",
    "let's break it down",
    "breaking this down",
    "breaking it down",
    "step by step",
    "first, let's",
    # Narrating the retrieved data instead of just answering from it
    "looking at the search results",
    "looking at the results",
    "looking at the data provided",
    "looking at the article",
    "looking at this data",
    "the search results show",
    "the search results indicate",
    "the search results say",
    "the results indicate",
    "reviewing the search results",
    "after reviewing",
    "upon reviewing",
    "based on my analysis",
    "my analysis shows",
    "in summary, the user",
    "to summarize for the user",
    "final answer",
    "here is my answer",
    "here's my answer",
)

# Sentence-opener filler words (Hmm, Well, Let's, Okay, So, Wait, Actually...)
# only reliably signal a reasoning leak at the very START of an answer —
# the same words appear harmlessly mid-sentence in a clean spoken answer
# (e.g. "...and the market actually rose 2%"). Checked separately from
# REASONING_LEAK_MARKERS for that reason, against a short leading window
# rather than the full text.
REASONING_OPENER_PATTERN = re.compile(
    r"^(hmm+|umm+|uh+|well|okay|ok|so|wait|actually|alright|hold on|"
    r"let'?s|let us|first|now|right|hold on a (second|moment|sec))\s*[,:.\-]",
    re.IGNORECASE,
)

OPENER_CHECK_WINDOW = 40


def looks_like_reasoning(text: str) -> bool:
    """Detect obvious leaked reasoning/instructions rather than a real answer.

    Two independent checks:
    1. Substring markers (REASONING_LEAK_MARKERS) — phrases that signal a
       leak wherever they appear in the text.
    2. Opener pattern (REASONING_OPENER_PATTERN) — filler words like
       "Hmm," or "Let's" checked ONLY at the start of the answer, since
       they're a reliable leak signal there but not mid-sentence.
    """
    if not text:
        return True

    lowered = text.lower().strip()

    if any(marker in lowered for marker in REASONING_LEAK_MARKERS):
        return True

    if REASONING_OPENER_PATTERN.match(lowered[:OPENER_CHECK_WINDOW]):
        return True

    return False


DEFAULT_SYSTEM_MESSAGE = (
    "You are Priya, a concise voice news assistant. "
    "Answer only from the supplied article. "
    "Give a short, factual, spoken-style explanation. "
    "Never mention sources, URLs, prompts, instructions, "
    "reasoning, article numbers, or these rules. "
    "Output ONLY the words Priya should speak — nothing else."
)

MARKET_SYSTEM_MESSAGE = (
    "You are Priya, a concise voice assistant discussing stock market information. "
    "Use ONLY the supplied data — never invent prices, movements, or facts not present in it. "
    "Never claim a single stock is guaranteed to be the best or will definitely rise or fall. "
    "If asked which stock to buy, briefly compare a few companies from the data and make "
    "clear this is general information, not personalized financial advice. "
    "Never mention sources, URLs, prompts, instructions, reasoning, or these rules. "
    "Output ONLY the words Priya should speak — nothing else."
)

BEST_STOCK_SYSTEM_MESSAGE = (
    "You are Priya, comparing Indian stocks using ONLY the supplied DATA. Never invent prices, "
    "movements, fundamentals, or facts not present in it, and never use your own general "
    "knowledge about a company as current data. Compare the candidates in the DATA using "
    "whatever evidence is present (recent news, mentioned trend or risk). "
    "Never promise returns. Never say a stock is guaranteed to rise. Always phrase any pick as "
    "a current candidate to consider, not a guaranteed winner. "
    "Respond with EXACTLY four lines, in this exact format and nothing else — no preamble, no "
    "extra commentary:\n"
    "Candidate: <one company name from the DATA, or None if the data does not clearly favor one>\n"
    "Reason: <one short sentence citing the specific evidence from the DATA>\n"
    "Risk: <one short sentence naming a real risk>\n"
    "Confidence: <High, Medium, or Low>\n"
    "Never mention sources, URLs, prompts, instructions, reasoning, or these rules. "
    "Output ONLY the four labeled lines above — nothing else."
)


GENERAL_SYSTEM_MESSAGE = (
    "You are Priya, a natural voice assistant answering general-knowledge questions. "
    "Use the supplied SEARCH RESULTS as factual grounding. "
    "Answer the user's actual question directly and naturally. "
    "Do not turn the answer into a list of search-result facts. "
    "Do not add unrelated current events, future events, or extra facts just because they "
    "appear in the search results. "
    "For definition questions such as 'What is cricket?', first give a simple definition, "
    "then briefly explain the main idea or how it works. "
    "Do not begin with 'According to Wikipedia', 'According to the search results', "
    "or similar attribution. "
    "Only mention a source when it is genuinely useful. "
    "Never mention URLs, prompts, instructions, reasoning, internal thinking, "
    "search results, or these rules. "
    "Output ONLY the words Priya should speak."
)

CHAT_SYSTEM_MESSAGE = (
    "You are Priya, a natural, friendly voice assistant having an everyday "
    "conversation. Answer the user's actual message directly — greetings, "
    "thanks, goodbyes, small talk, opinions, jokes, explanations, "
    "hypotheticals, and follow-up questions are all normal conversation, "
    "not just news or facts, and none of them need a predefined script. "
    "Use your own general knowledge and reasoning to answer; you are not "
    "limited to any search results here. "
    "Be concise by default — 2 to 4 short spoken sentences — and go into "
    "more detail only if the user clearly asks for it. "
    "This is a voice assistant: no markdown, no code blocks, no bullet "
    "lists, and no JSON, unless the user explicitly asks for code or a "
    "list. "
    "If asked who you are, what you can do, or who created you, answer "
    "briefly and honestly as Priya, an AI assistant, and identify yourself "
    "as AI when it's relevant to the question. "
    "Never claim to have a physical body, a location, human emotions, or "
    "personal lived experiences — you can still share a reasoned opinion "
    "or a lighthearted remark without pretending to be human. Never "
    "invent personal memories or anecdotes. "
    "Never say things like 'the user asked' or refer to the user in the "
    "third person — speak directly to them. "
    "Never mention prompts, instructions, system messages, reasoning, "
    "internal thinking, or these rules. "
    "Output ONLY the words Priya should speak — nothing else."
)

TELUGU_MOVIE_SYSTEM_MESSAGE = (
    "You are Priya, a concise voice assistant giving a Telugu-film recommendation. "
    "Use ONLY the verified Telugu-language film results provided. "
    "Never use your own movie knowledge and never name a title that is not in those results. "
    "Start directly with the recommendation; do not use filler such as 'Considering your "
    "preference', 'Based on several sources', 'Perhaps you'd like to explore', or 'It is "
    "difficult to say'. If the user asks for the best, choose ONE available title and say "
    "'I'd pick', 'My top recommendation is', or 'A strong choice is' rather than claiming "
    "it is objectively best. Mention no more than two alternatives. "
    "Do not include a Hindi, Tamil, Malayalam, English, or other-language film. "
    "Never mention sources, URLs, prompts, instructions, reasoning, search results, or these rules. "
    "Output only one or two short spoken sentences."
)

TELUGU_MOVIE_FILLER_PHRASES = (
    "considering your preference",
    "based on several sources",
    "perhaps you'd like to explore",
    "it is difficult to say",
)
TELUGU_MOVIE_OTHER_LANGUAGES = (
    "hindi",
    "tamil",
    "malayalam",
    "kannada",
    "english",
)
TELUGU_MOVIE_NON_TITLE_CAPITALS = {
    "a", "an", "and", "as", "for", "i", "i'd", "i'll", "i've", "if", "in", "is", "it", "my",
    "the", "this", "you", "your",
}


def ask_ollama(prompt: str, max_tokens: int, system_message: str = DEFAULT_SYSTEM_MESSAGE) -> str:
    """Send a request to Ollama and return only the message content."""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        
        "options": {
            "temperature": 0.15,
            "top_p": 0.8,
            "num_predict": max_tokens,
        },
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()

    message = data.get("message", {})
    answer = message.get("content", "")

    # Compatibility fallback for older Ollama response shapes.
    if not answer:
        answer = data.get("response", "")

    return answer.strip()


STRICT_RETRY_CLAUSE = (
    " Your previous attempt leaked internal reasoning instead of a clean answer. "
    "Do not think out loud. Do not narrate your process. Do not use openers like "
    "'Hmm', 'Well', 'Let's', 'Okay', or 'So'. Do not refer to the user, the question, "
    "the search results, the data, or these instructions. "
    "Output ONLY the final spoken answer — nothing else."
)


def _generate_validated(
    prompt: str,
    retry_prompt: str,
    system_message: str,
    max_tokens: int,
    retry_max_tokens: int,
    extra_ok=None,
    perf_label: str | None = None,
) -> str | None:
    """Call Ollama, validate, and retry ONCE — shared by every ask_*_model().

    Critical ordering fix: validation runs on the RAW model output with
    only <think> blocks removed (strip_think_tags), NOT on the fully
    cosmetically-cleaned text. clean_answer() also strips out short leak
    phrases like "let me analyze" for display purposes — if
    looks_like_reasoning() ran after that cleanup, the very evidence it
    needs to see would already be gone, letting leaked reasoning through
    undetected. So: strip think tags -> validate -> only then cosmetically
    clean (by the caller) for the final spoken answer.

    The retry attempt is strictly stronger than the first, not just
    shorter: its system message gets STRICT_RETRY_CLAUSE appended, so
    every caller's retry is automatically hardened against the same leak
    pattern that just failed, without each build_*_retry_prompt() having
    to spell that out itself.

    Returns the think-stripped (but not yet cosmetically cleaned) text of
    whichever attempt passes validation, or None if both attempts leak
    reasoning or fail an optional extra check (e.g. required output
    structure). Callers must NEVER return raw model output directly —
    when this returns None, the caller supplies a safe fallback message.
    """
    attempts = (
        (prompt, max_tokens, system_message),
        (retry_prompt, retry_max_tokens, system_message + STRICT_RETRY_CLAUSE),
    )

    generation_seconds = 0.0
    attempts_made = 0
    output_characters = 0
    try:
        for attempt_prompt, tokens, attempt_system_message in attempts:
            attempts_made += 1
            generation_started = time.perf_counter()
            try:
                raw = ask_ollama(
                    attempt_prompt,
                    max_tokens=tokens,
                    system_message=attempt_system_message,
                )
            finally:
                generation_seconds += time.perf_counter() - generation_started
            output_characters += len(raw)
            candidate = strip_think_tags(raw)

            if not candidate or looks_like_reasoning(candidate):
                continue

            if extra_ok is not None and not extra_ok(candidate):
                continue

            return candidate

        return None
    finally:
        if perf_label:
            print(f"[PERF][LLM] {perf_label}: {generation_seconds:.3f}s")
            print(f"[PERF][LLM] attempts: {attempts_made}")
            print(f"[PERF][LLM] output characters: {output_characters}")


def _log_llm_input_size(label: str, prompt: str, context: str) -> None:
    """Log compact size measurements without exposing user/search content."""
    print(f"[PERF][LLM] {label} context characters: {len(context)}")
    print(f"[PERF][LLM] {label} prompt characters: {len(prompt)}")


def ask_model(question: str, context: str) -> str:
    """Generate Priya's detailed spoken explanation for a SINGLE article.

    This function is only ever called for detailed/follow-up requests.
    Normal headline requests must use headline_response() instead and
    never reach this function.

    Validates the output and retries ONCE with a shorter prompt if the
    first attempt looks like leaked reasoning rather than a real answer.
    If both attempts fail validation, returns a safe fallback message —
    never shows raw reasoning to the user.
    """
    question = question.strip()
    context = context.strip()

    if not question:
        return "What news would you like to hear about?"

    if not context:
        return "I couldn't find any news for that topic."

    try:
        prompt = build_prompt(question, context)
        retry_prompt = build_retry_prompt(question, context)
        _log_llm_input_size("ask_model", prompt, context)

        candidate = _generate_validated(
            prompt, retry_prompt, DEFAULT_SYSTEM_MESSAGE, 180, 120, perf_label="ask_model"
        )

        if candidate:
            return clean_answer(candidate)

        # Both attempts failed validation — never show raw reasoning.
        return "I have the story, but I couldn't put together a clean explanation right now."

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error

    except requests.RequestException as error:
        raise RuntimeError(
           "Could not connect to Ollama. Make sure Ollama is running and gemma3:4b is installed."
        ) from error


def build_market_prompt(question: str, context: str) -> str:
    """Short prompt for a market explanation/comparison — see build_prompt for why it's short."""
    return f"""DATA:
{context}

QUESTION: {question}

Answer in 3 to 6 short spoken sentences using only the DATA above. If comparing
companies, do not name one guaranteed best choice — compare them briefly instead."""


def build_market_retry_prompt(question: str, context: str) -> str:
    """Even shorter fallback prompt used once if the first market answer leaks reasoning."""
    return f"""DATA:
{context}

In 2 short sentences, answer only: {question}
Do not name one guaranteed best choice."""


def ask_market_model(question: str, context: str) -> str:
    """Generate Priya's market explanation/comparison from Python-retrieved data only.

    Qwen is never the source of prices or facts here — it only explains/
    compares the `context` that news.py/market.py already retrieved.
    Same validate + retry-once + safe-fallback pattern as ask_model().
    """
    question = question.strip()
    context = context.strip()

    if not question:
        return "What would you like to know about the market?"

    if not context:
        return "Live market data is currently unavailable."

    try:
        prompt = build_market_prompt(question, context)
        retry_prompt = build_market_retry_prompt(question, context)
        _log_llm_input_size("ask_market_model", prompt, context)

        candidate = _generate_validated(
            prompt, retry_prompt, MARKET_SYSTEM_MESSAGE, 220, 140, perf_label="ask_market_model"
        )

        if candidate:
            return clean_answer(candidate)

        return "I have some market data, but couldn't put together a clean comparison right now."

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error

    except requests.RequestException as error:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is running and qwen3:4b is installed."
        ) from error


def build_best_stock_prompt(question: str, context: str) -> str:
    """Prompt for the 'which stock should I buy' comparison — exact 4-line format required."""
    return f"""DATA:
{context}

QUESTION: {question}

Respond with EXACTLY these four lines and nothing else:
Candidate: <one company name from the DATA, or None>
Reason: <one short sentence citing evidence from the DATA>
Risk: <one short sentence naming a real risk>
Confidence: <High, Medium, or Low>"""


def build_best_stock_retry_prompt(question: str, context: str) -> str:
    """Even shorter fallback prompt used once if the first best-stock answer leaks reasoning
    or doesn't come back in the required 4-line format."""
    return f"""DATA:
{context}

Answer only: {question}
Respond with EXACTLY these four lines, nothing else:
Candidate: <name from the DATA, or None>
Reason: <short sentence>
Risk: <short sentence>
Confidence: <High, Medium, or Low>"""


BEST_STOCK_FIELD_PATTERNS = {
    "candidate": r"candidate\s*:\s*(.+)",
    "reason": r"reason\s*:\s*(.+)",
    "risk": r"risk\s*:\s*(.+)",
    "confidence": r"confidence\s*:\s*(.+)",
}


def parse_best_stock_fields(text: str) -> dict[str, str] | None:
    """Extract Candidate/Reason/Risk/Confidence from a model answer.

    Returns None if any of the four fields is missing or empty, so the
    caller can retry or fall back rather than show a malformed answer.
    Tolerant of the model running fields together on one line by trimming
    a captured value at the next field label, if any.
    """
    if not text:
        return None

    fields: dict[str, str] = {}

    for key, pattern in BEST_STOCK_FIELD_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        value = match.group(1).strip()
        # Trim at the next field label in case the model put everything
        # on one line without newlines between labels.
        value = re.split(r"\s*(?:candidate|reason|risk|confidence)\s*:", value, flags=re.IGNORECASE)[0].strip()
        if not value:
            return None
        fields[key] = value

    return fields


def format_best_stock_answer(fields: dict[str, str]) -> str:
    """Render the parsed fields in the exact required output shape."""
    return (
        f"Candidate: {fields['candidate']}\n"
        f"Reason: {fields['reason']}\n"
        f"Risk: {fields['risk']}\n"
        f"Confidence: {fields['confidence']}"
    )


def ask_best_stock_model(question: str, context: str) -> str:
    """Answer 'which stock should I buy' style questions.

    May name ONE current candidate to consider — but ONLY drawn from
    `context` (real retrieved headlines news.py/market.py already fetched),
    never from Qwen's own training knowledge, and never as a guarantee.
    Same validate + retry-once + safe-fallback pattern as ask_model().
    Caller (main.py) is responsible for checking market.has_sufficient_market_data()
    first and skipping this call entirely when there's no usable data.
    """
    question = question.strip()
    context = context.strip()

    if not question:
        return "What would you like to know about the market?"

    if not context:
        return "Live market information is currently insufficient for a reliable comparison."

    try:
        prompt = build_best_stock_prompt(question, context)
        retry_prompt = build_best_stock_retry_prompt(question, context)
        _log_llm_input_size("ask_best_stock_model", prompt, context)

        def _has_required_fields(candidate: str) -> bool:
            return parse_best_stock_fields(clean_answer(candidate)) is not None

        candidate = _generate_validated(
            prompt,
            retry_prompt,
            BEST_STOCK_SYSTEM_MESSAGE,
            200,
            130,
            extra_ok=_has_required_fields,
            perf_label="ask_best_stock_model",
        )

        if candidate:
            fields = parse_best_stock_fields(clean_answer(candidate))
            return format_best_stock_answer(fields)

        # Both attempts failed to produce the required structured format —
        # never show a malformed or free-text answer for this question type.
        return "Live market information is currently insufficient for a reliable comparison."

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error

    except requests.RequestException as error:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is running and gemma3:4b is installed."
        ) from error

def build_general_prompt(question: str, context: str) -> str:
    """Short prompt for a general-knowledge answer grounded in search results."""
    return f"""SEARCH RESULTS:
{context}

QUESTION: {question}

Answer the QUESTION directly using the SEARCH RESULTS as factual grounding.

Keep the answer natural and conversational for a voice assistant.
For a "what is" or "define" question, start with a simple definition and
briefly explain the main idea or how it works.

Do not mention the search results or URLs.
Do not add unrelated facts.
Do not mention sports tournaments, dates, recent news, or future events
unless the question explicitly asks about them.
Answer only what the user asked.

Answer in 2 to 4 short spoken sentences."""

def build_general_retry_prompt(question: str, context: str) -> str:
    """Even shorter fallback prompt used once if the first general answer leaks reasoning."""
    return f"""SEARCH RESULTS:
{context}

In 2 short sentences, state only the key fact that answers: {question}"""


def ask_general_model(question: str, context: str) -> str:
    """Generate Priya's answer to a general-knowledge question from
    Python-retrieved search results only (see search/pipeline.py).

    Same architecture rule as ask_market_model(): Qwen is never the
    source of the facts, only the explanation of facts already retrieved.
    Same validate + retry-once + safe-fallback pattern as ask_model().
    """
    question = question.strip()
    context = context.strip()

    if not question:
        return "What would you like to know?"

    if not context:
        return "I couldn't find anything reliable about that."

    try:
        prompt = build_general_prompt(question, context)
        retry_prompt = build_general_retry_prompt(question, context)
        _log_llm_input_size("ask_general_model", prompt, context)

        candidate = _generate_validated(
            prompt, retry_prompt, GENERAL_SYSTEM_MESSAGE, 90, 60, perf_label="ask_general_model"
        )

        if candidate:
            return clean_answer(candidate)

        return "I found some information, but couldn't put together a clean answer right now."

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error

    except requests.RequestException as error:
        raise RuntimeError(
           "Could not connect to Ollama. Make sure Ollama is running and gemma3:4b is installed."
        ) from error


def build_chat_prompt(question: str, memory_context: str) -> str:
    """Prompt for the free-form conversational fallback.

    Deliberately NOT grounded in search results (unlike build_general_prompt) —
    this is the broad catch-all for everyday conversation, opinions, and
    hypotheticals, answered from the model's own knowledge. `memory_context`
    is a short, optional summary of recent turns (see memory.format_recent_context)
    so follow-ups like "what did we talk about earlier" can be answered.
    """
    if memory_context:
        return f"""RECENT CONVERSATION:
{memory_context}

QUESTION: {question}

Answer the QUESTION naturally. Use RECENT CONVERSATION only if it helps
resolve a follow-up or reference — otherwise ignore it.
Answer in 2 to 4 short spoken sentences unless more detail is clearly requested."""

    return f"""QUESTION: {question}

Answer naturally in 2 to 4 short spoken sentences unless more detail is
clearly requested."""


def build_chat_retry_prompt(question: str, memory_context: str) -> str:
    """Shorter fallback prompt used once if the first chat answer leaks reasoning."""
    return f"""In 1 to 2 short spoken sentences, answer naturally: {question}"""


def ask_chat_model(question: str, memory_context: str = "") -> str:
    """Generate Priya's answer for the general conversation fallback.

    This is the broad catch-all so Priya never refuses a reasonable
    natural-language message just because it wasn't predefined. Unlike
    ask_general_model(), it is not grounded in retrieved search results —
    it answers from the model's own knowledge, the same way a natural
    conversational assistant would. Same validate + retry-once +
    safe-fallback pattern as every other ask_*_model().
    """
    question = question.strip()

    if not question:
        return "I'm here — what would you like to talk about?"

    try:
        prompt = build_chat_prompt(question, memory_context)
        retry_prompt = build_chat_retry_prompt(question, memory_context)
        _log_llm_input_size("ask_chat_model", prompt, memory_context)

        candidate = _generate_validated(
            prompt, retry_prompt, CHAT_SYSTEM_MESSAGE, 160, 90, perf_label="ask_chat_model"
        )

        if candidate:
            return clean_answer(candidate)

        return "I'm not sure how to put that into words right now — could you ask that again?"

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error

    except requests.RequestException as error:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is running and gemma3:4b is installed."
        ) from error


def ask_telugu_movie_recommendation(question: str, context: str) -> str:
    """Give a grounded, concise Telugu-film recommendation."""

    question = question.strip()
    context = context.strip()

    if not context:
        return "I couldn't find a reliable Telugu-language film recommendation right now."

    prompt = f"""VERIFIED TELUGU-LANGUAGE FILM RESULTS:
{context}

QUESTION: {question}

Start directly with one recommendation from the verified results. Keep the
answer to one or two short spoken sentences and give at most two alternatives.
For a "best" question, choose one strong recommendation, using wording such as
"I'd pick" or "My top recommendation is"; never call it objectively best. Do
not use filler phrases and do not mention any other-language film."""
    retry_prompt = f"""VERIFIED TELUGU-LANGUAGE FILM RESULTS:
{context}

For {question}, give one direct, short recommendation using only a title in
these results. Use no filler, no more than two sentences, and do not call any
film objectively best."""

    try:
        _log_llm_input_size("ask_telugu_movie_recommendation", prompt, context)
        candidate = _generate_validated(
            prompt,
            retry_prompt,
            TELUGU_MOVIE_SYSTEM_MESSAGE,
            80,
            55,
            extra_ok=lambda candidate: _is_safe_telugu_movie_recommendation(candidate, context),
            perf_label="ask_telugu_movie_recommendation",
        )

        if candidate:
            return clean_answer(candidate)

        return "I found Telugu-language film information, but couldn't make a clean recommendation right now."

    except requests.Timeout as error:
        raise RuntimeError("Ollama took too long to respond.") from error
    except requests.RequestException as error:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is running and gemma3:4b is installed."
        ) from error


def _is_safe_telugu_movie_recommendation(candidate: str, context: str) -> bool:
    """Reject verbose, filler-heavy, or ungrounded movie recommendations."""
    answer = candidate.strip()
    lowered = answer.lower()

    if not answer or any(phrase in lowered for phrase in TELUGU_MOVIE_FILLER_PHRASES):
        return False
    if any(language in lowered for language in TELUGU_MOVIE_OTHER_LANGUAGES):
        return False
    if re.search(r"\b(?:the\s+)?best\b", lowered):
        return False

    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", answer) if sentence.strip()]
    if len(sentences) > 2 or len(re.findall(r"\b[\w'-]+\b", answer)) > 55:
        return False

    # A title is normally capitalized. Requiring its significant capitalized words
    # to be present in the already-filtered context prevents a model-added title.
    capitalized_words = re.findall(r"\b[A-Z][A-Za-z0-9'-]*\b", answer)
    title_words = [
        word for word in capitalized_words
        if word.lower() not in TELUGU_MOVIE_NON_TITLE_CAPITALS
    ]
    context_words = set(re.findall(r"\b[\w'-]+\b", context.lower()))
    return bool(title_words) and all(word.lower() in context_words for word in title_words)