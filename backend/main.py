"""Main FastAPI application for Priya News AI."""

import json
import time
import logging
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .database import check_connection, get_stored_news
from .general import get_general_context, get_telugu_movie_recommendation_context
from .intent import analyze_question, classify_casual, get_assistant_response, get_conversational_response
from .llm import ask_best_stock_model, ask_chat_model, ask_general_model, ask_market_model, ask_model, ask_telugu_movie_recommendation, headline_response, warm_ollama
from .memory import add_image_turn, add_turn, clear_memory, format_recent_context, get_last_article, resolve_reference
from .market import (
    RESEARCH_CANDIDATES,
    build_market_detail_context,
    detect_company,
    get_company_news,
    get_market_headlines,
    has_sufficient_market_data,
    is_best_stock_question,
    research_candidates_context,
)
from .news import build_detail_context, find_matching_article, get_top_headlines, fetch_topic_news
from .session import get_state, update_state
from .tts import (
    TTS_UNAVAILABLE_DETAIL,
    TTSUnavailableError,
    generate_speech,
    get_kokoro,
    tts_is_available,
    MODEL_PATH,
    VOICES_PATH,
)
from .image_search import search_images
from .vision import VisionError, analyze_image
from .career.router import router as career_router


def _answer_payload(question: str, answer: str, intent, category: str, mode: str) -> dict:
    """Record useful non-identity turns and return the existing API shape."""
    state = get_state()
    if category != "assistant":
        add_turn(
            user_question=question,
            assistant_answer=answer,
            intent=intent.kind,
            topic=intent.topic,
            category=category,
            location=state.get("last_location"),
            article=state.get("last_article"),
        )
    return {"question": question, "category": category, "mode": mode, "answer": answer}


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Priya News AI API",
    version="2.1.0",
)
app.include_router(career_router)
log = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.on_event("startup")
def preload_tts_model() -> None:
    """Warm optional local services without making deployment depend on them."""
    if not tts_is_available():
        if not MODEL_PATH.is_file() or not VOICES_PATH.is_file():
            log.warning("[TTS] Kokoro model files not found; TTS disabled for this deployment.")
        else:
            log.warning("[TTS] Kokoro TTS is disabled or its dependencies are unavailable.")
    else:
        try:
            get_kokoro()
        except TTSUnavailableError as error:
            log.warning("[TTS] Kokoro warm-up skipped; TTS disabled: %s", error)
    Thread(target=warm_ollama, name="ollama-warmup", daemon=True).start()


# ============================================================
# MODELS
# ============================================================

class TTSRequest(BaseModel):
    text: str
    chunk: int | None = None


def _requests_image_search(question: str) -> bool:
    text = question.lower()
    phrases = (
        "find this", "find similar", "find this online", "show me images",
        "show images", "show pictures", "show me similar", "similar products",
        "similar images", "find this product", "buy this", "where can i buy",
    )
    return any(phrase in text for phrase in phrases)


# ============================================================
# HOME
# ============================================================

@app.get("/")
def welcome() -> RedirectResponse:

    return RedirectResponse(
        url="/app/"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "ok",
        "service": "Priya News AI",
    }


@app.post("/memory/clear")
def clear_conversation_memory():
    """Clear the temporary conversational context for this local app."""
    clear_memory()
    update_state(article=None, category="general", location=None, mode="headlines")
    return {"status": "cleared"}


@app.post("/vision/analyze")
async def vision_analyze(
    image: UploadFile = File(...),
    question: str | None = Form(default=None),
):
    """Analyze one in-memory image without changing the text /ask route."""
    try:
        image_bytes = await image.read()
        clean_question = (question or "").strip()
        if len(clean_question) > 500:
            raise VisionError("Image questions must be 500 characters or fewer.")
        result = analyze_image(image_bytes, clean_question)
        add_image_turn(clean_question, result["description"], result["answer"])
        if clean_question and _requests_image_search(clean_question):
            query = f"{clean_question} {result['description']}".strip()[:500]
            result["image_results"] = search_images(query, limit=5)
        else:
            result["image_results"] = []
        return result
    except VisionError as error:
        detail = str(error)
        client_error = ("upload", "valid", "large", "jpg", "question")
        status_code = 422 if any(term in detail.lower() for term in client_error) else 503
        raise HTTPException(status_code=status_code, detail=detail) from error
    finally:
        await image.close()


# ============================================================
# DATABASE HEALTH
# ============================================================

@app.get("/health/database")
def database_health():

    if check_connection():

        return {
            "status": "ok",
            "database": "MongoDB connected",
        }

    raise HTTPException(
        status_code=503,
        detail="Could not connect to MongoDB.",
    )


# ============================================================
# NEWS
# ============================================================

@app.get("/news")
def latest_news(
    limit: int = Query(
        default=10,
        ge=1,
        le=20,
    ),
    category: str = Query(
        default="general",
    ),
):

    try:

        selected_category = (
            category.lower().strip()
        )

        articles = get_top_headlines(
            limit=limit,
            category=selected_category,
        )

        return {
            "count": len(articles),
            "articles": articles,
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch news: {error}",
        ) from error


# ============================================================
# STORED NEWS
# ============================================================

@app.get("/news/stored")
def stored_news(
    category: str | None = None,
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
):

    try:

        articles = get_stored_news(
            category=category,
            limit=limit,
        )

        return {
            "count": len(articles),
            "articles": articles,
        }

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not retrieve stored news: "
                f"{error}"
            ),
        ) from error


# ============================================================
# MARKET NEWS
# ============================================================

@app.get("/market/news")
def market_news(
    limit: int = Query(
        default=10,
        ge=1,
        le=20,
    ),
):

    try:

        articles = get_market_headlines(limit=limit)

        return {
            "count": len(articles),
            "articles": articles,
        }

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch market news: {error}",
        ) from error


@app.get("/market/stock/{company}")
def market_stock(
    company: str,
    limit: int = Query(
        default=6,
        ge=1,
        le=15,
    ),
):

    try:

        canonical = detect_company(company) or company.strip()

        articles = get_company_news(canonical, limit=limit)

        return {
            "company": canonical,
            "count": len(articles),
            "articles": articles,
        }

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch stock news: {error}",
        ) from error


# ============================================================
# ASK PRIYA
# ============================================================

@app.get("/ask")
def ask_news(
    question: str = Query(
        min_length=1,
        max_length=500,
    ),
    category: str | None = Query(
        default=None,
    ),
):

    request_started = time.perf_counter()
    print("[PERF] /ask started")
    question = question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:

        # ----------------------------------------------------
        # Deterministic intent classification (Python, no Qwen).
        # Word-boundary safe: "Mumbai" never matches the "ai" category.
        # ----------------------------------------------------

        original_question = question
        question, clarification = resolve_reference(question)
        if clarification:
            return {
                "question": original_question,
                "category": "general",
                "mode": "clarification",
                "answer": clarification,
            }

        intent_started = time.perf_counter()
        state = get_state()
        previous_article = get_last_article() or state.get("last_article")
        intent = analyze_question(question, previous_article)
        print(f"[PERF] intent: {time.perf_counter() - intent_started:.3f}s")

        if intent.kind == "assistant":

            answer = get_assistant_response(question)

            update_state(
                article=None,
                category="assistant",
                location=None,
                mode="assistant",
            )

            return _answer_payload(original_question, answer, intent, "assistant", "assistant")
        if intent.kind == "casual":
            casual_responses = {
                "greeting": "Hi! I'm Priya. How can I help you today?",
                "wellbeing": "I'm doing well and ready to help. What would you like to know?",
                "thanks": "You're welcome! Anything else I can help with?",
                "bye": "Goodbye! Talk soon.",
                "ack": "Got it. What would you like to do next?",
            }

            casual_category = classify_casual(question)
            answer = casual_responses.get(casual_category, casual_responses["greeting"])

            update_state(
                article=None,
                category="assistant",
                location=None,
                mode="casual",
            )

            return _answer_payload(original_question, answer, intent, "assistant", "casual")

        if intent.kind == "conversational":
            answer = get_conversational_response(question)
            update_state(
                article=None,
                category="assistant",
                location=None,
                mode="conversational",
            )
            return _answer_payload(original_question, answer, intent, "assistant", "conversational")

        # ----------------------------------------------------
        # MARKET / STOCK PATH
        # Triggered by a named company OR the "market" category.
        # Qwen is never the source of prices/facts here — only Python-
        # retrieved headlines are ever sent to it, and only when an
        # explanation/comparison is actually needed.
        # ----------------------------------------------------

        company = detect_company(question)
        is_market_question = bool(company) or intent.category == "market"

        if is_market_question:

            if is_best_stock_question(question):

                search_started = time.perf_counter()
                candidates_with_articles = [
                    (name, get_company_news(name, limit=3))
                    for name in RESEARCH_CANDIDATES
                ]
                print(f"[PERF] search: {time.perf_counter() - search_started:.3f}s")

                context_started = time.perf_counter()
                comparison_context = research_candidates_context(candidates_with_articles)
                print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

                mode = "market_comparison"

                if not has_sufficient_market_data(candidates_with_articles):

                    # No retrieved data at all — say so instead of guessing.
                    answer = "Live market information is currently insufficient for a reliable comparison."

                else:

                    llm_started = time.perf_counter()
                    answer = ask_best_stock_model(question, comparison_context)
                    print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

                update_state(
                    article=None,
                    category="market",
                    location=None,
                    mode=mode,
                )

                return _answer_payload(original_question, answer, intent, "market", mode)

            search_started = time.perf_counter()
            market_articles = (
                get_company_news(company, limit=6)
                if company
                else get_market_headlines(limit=8)
            )
            print(f"[PERF] search: {time.perf_counter() - search_started:.3f}s")

            if not market_articles:

                answer = "Live market data is currently unavailable."

                update_state(
                    article=state.get("last_article"),
                    category="market",
                    location=None,
                    mode="headlines",
                )

                return _answer_payload(original_question, answer, intent, "market", "headlines")

            if intent.kind in ("follow_up", "detailed_news", "specific_article"):

                if intent.kind == "follow_up" and state.get("last_article"):
                    target_article = state["last_article"]
                else:
                    target_article = find_matching_article(market_articles, question) or market_articles[0]

                context_started = time.perf_counter()
                market_detail_context = build_market_detail_context(company, [target_article])
                print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

                llm_started = time.perf_counter()
                answer = ask_market_model(question, market_detail_context)
                print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

                mode = "detailed"

                update_state(
                    article=target_article,
                    category="market",
                    location=None,
                    mode=mode,
                )

            else:

                context_started = time.perf_counter()
                market_headline_context = json.dumps(
                    {"articles": market_articles},
                    ensure_ascii=False,
                )
                print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

                answer = headline_response(market_headline_context)

                mode = "headlines"

                update_state(
                    article=market_articles[0],
                    category="market",
                    location=None,
                    mode=mode,
                )

            return _answer_payload(original_question, answer, intent, "market", mode)

        # ----------------------------------------------------
        # GENERAL KNOWLEDGE PATH
        # "What is Kubernetes?", "Compare Apple and Samsung", etc. — no
        # RSS fetch here; grounded entirely in search/pipeline.py results.
        # ----------------------------------------------------

        if intent.kind == "telugu_movie_recommendation":

            context_started = time.perf_counter()
            context = get_telugu_movie_recommendation_context(question)
            print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

            if not context:
                answer = "I couldn't find a reliable Telugu-language film recommendation right now."
            else:
                llm_started = time.perf_counter()
                answer = ask_telugu_movie_recommendation(question, context)
                print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

            update_state(
                article=None,
                category="general",
                location=None,
                mode="telugu_movie_recommendation",
            )

            return _answer_payload(original_question, answer, intent, "general", "telugu_movie_recommendation")

        if intent.kind == "general_knowledge":

            context_started = time.perf_counter()
            context = get_general_context(question)
            print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")


            if not context:
                answer = "I couldn't find anything reliable about that."
            else:
                llm_started = time.perf_counter()
                answer = ask_general_model(question, context)
                print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

            update_state(
                article=None,
                category="general",
                location=None,
                mode="general_knowledge",
            )

            return _answer_payload(original_question, answer, intent, "general", "general_knowledge")

        # ----------------------------------------------------
        # GENERAL CONVERSATION FALLBACK
        # The broad catch-all: greetings/goodbyes/etc. are already handled
        # above by the fast "casual" path, so anything landing here is
        # everything else — small talk, opinions, hypotheticals, "explain
        # X simply", or any other reasonable message that isn't news,
        # market, or a search-groundable definition. Answered by Gemma
        # from its own knowledge, NOT the search-grounded general_knowledge
        # pipeline above. See intent.analyze_question steps 9-10.
        # ----------------------------------------------------

        if intent.kind == "chat":

            memory_context = format_recent_context()

            llm_started = time.perf_counter()
            answer = ask_chat_model(question, memory_context)
            print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

            update_state(
                article=None,
                category="general",
                location=None,
                mode="chat",
            )

            return _answer_payload(original_question, answer, intent, "general", "chat")

        # ----------------------------------------------------
        # GENERAL / LOCATION / CATEGORY NEWS PATH
        # ----------------------------------------------------

        selected_category = (
            category.lower().strip() if category else intent.category
        )
        location = intent.location

        # ----------------------------------------------------
        # Get current news (Python-side fetch, always needed either way)
        # ----------------------------------------------------

        search_started = time.perf_counter()
        articles = get_top_headlines(
            limit=8,
            category=selected_category,
            location=location,
        )
        print(f"[PERF] search: {time.perf_counter() - search_started:.3f}s")

        if not articles:

            answer = (
                "Sorry, I couldn't find any "
                "current news for that topic."
            )

            update_state(
                article=state.get("last_article"),
                category=selected_category,
                location=location,
                mode="headlines",
            )

            return _answer_payload(original_question, answer, intent, selected_category, "headlines")

        # ----------------------------------------------------
        # Route: detailed / follow-up / specific article -> Qwen,
        #        ONLY on the one relevant article.
        # Everything else (plain headlines, category, location news)
        # is handled entirely in Python -> ZERO Qwen calls.
        # ----------------------------------------------------

        if intent.kind in ("follow_up", "detailed_news", "specific_article"):

            if intent.kind == "follow_up" and state.get("last_article"):
                target_article = state["last_article"]
            else:
                target_article = find_matching_article(articles, question) or articles[0]

            context_started = time.perf_counter()
            detail_context = build_detail_context(target_article)
            print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

            llm_started = time.perf_counter()
            answer = ask_model(
                question=question,
                context=detail_context,
            )
            print(f"[PERF] llm: {time.perf_counter() - llm_started:.3f}s")

            mode = "detailed"

            update_state(
                article=target_article,
                category=selected_category,
                location=location,
                mode=mode,
            )

        else:

            context_started = time.perf_counter()
            headline_context = json.dumps(
                {"articles": articles},
                ensure_ascii=False,
            )
            print(f"[PERF] context: {time.perf_counter() - context_started:.3f}s")

            answer = headline_response(headline_context)

            mode = "headlines"

            update_state(
                article=articles[0],
                category=selected_category,
                location=location,
                mode=mode,
            )

        # ----------------------------------------------------
        # Return clean response
        # ----------------------------------------------------

        return _answer_payload(original_question, answer, intent, selected_category, mode)

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:

        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not answer the question: "
                f"{error}"
            ),
        ) from error
    finally:
        print(f"[PERF] /ask total: {time.perf_counter() - request_started:.3f}s")


# ============================================================
# KOKORO / TTS
# ============================================================

@app.post("/tts")
def text_to_speech(
    request: TTSRequest,
):

    text = request.text.strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty.",
        )

    if len(text) > 2000:

        raise HTTPException(
            status_code=400,
            detail="Text is too long for speech generation.",
        )

    try:

        audio = generate_speech(
            text,
            chunk_number=request.chunk,
        )

        return StreamingResponse(
            iter([audio]),
            media_type="audio/wav",
            headers={
                "Content-Disposition": (
                    'inline; filename="priya.wav"'
                )
            },
        )

    except TTSUnavailableError as error:

        raise HTTPException(
            status_code=503,
            detail=TTS_UNAVAILABLE_DETAIL,
        ) from error

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Kokoro could not generate speech.",
        ) from error


# ============================================================
# TEST TTS
# ============================================================

@app.get("/tts/test")
def test_tts():

    try:

        audio = generate_speech(
            "Hello. I am Priya. "
            "I am ready with today's latest news."
        )

        return StreamingResponse(
            iter([audio]),
            media_type="audio/wav",
        )

    except TTSUnavailableError as error:

        raise HTTPException(
            status_code=503,
            detail=TTS_UNAVAILABLE_DETAIL,
        ) from error

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Kokoro could not generate speech.",
        ) from error


# ============================================================
# FRONTEND
# ============================================================

app.mount(
    "/app",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)
