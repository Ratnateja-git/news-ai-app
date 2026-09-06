"""Stock market and trading news for Priya News AI.

Architecture rule: Qwen is NEVER the source of prices, index levels, or
market "facts" here. Python retrieves real headlines via Google News RSS
(free, no API key); Qwen (llm.ask_market_model) is only ever used to
explain/compare data that was already retrieved — see main.py routing.

If live numeric index/price data isn't available from a free, reliable
source, we say so plainly rather than inventing numbers (see main.py).
"""

import re

from .news import fetch_google_news

MARKET_HEADLINE_QUERY = "Indian stock market Sensex Nifty BSE NSE news"

# Multi-word phrases first so "tata motors" wins over a bare "tata" —
# detect_company() sorts by length, so order here doesn't matter, but
# keeping related phrases grouped makes this easier to extend.
COMPANY_ALIASES: dict[str, str] = {
    "tata motors": "Tata Motors",
    "tata steel": "Tata Steel",
    "tata consultancy": "Tata Consultancy Services (TCS)",
    "tcs": "Tata Consultancy Services (TCS)",
    "reliance industries": "Reliance Industries",
    "reliance": "Reliance Industries",
    "infosys": "Infosys",
    "hdfc bank": "HDFC Bank",
    "icici bank": "ICICI Bank",
    "wipro": "Wipro",
    "adani": "Adani Group",
    "itc": "ITC",
    "state bank of india": "State Bank of India (SBI)",
    "sbi": "State Bank of India (SBI)",
    "axis bank": "Axis Bank",
    "bharti airtel": "Bharti Airtel",
    "hindustan unilever": "Hindustan Unilever",
}

# A small, fixed set of major large-cap companies used for "worth
# researching" style comparison questions. This is NOT live fundamentals
# data — just a starting point for pulling real, current headlines about
# each one, so the comparison is grounded in retrieved facts.
RESEARCH_CANDIDATES = [
    "Reliance Industries",
    "Tata Consultancy Services (TCS)",
    "HDFC Bank",
    "Infosys",
    "ICICI Bank",
]

BEST_STOCK_MARKERS = (
    "best stock to buy",
    "best share to buy",
    "which stock should i buy",
    "which share should i buy",
    "which stocks should i buy",
    "best stock right now",
    "which is the best stock",
    "what is the best stock",
    "best indian stocks",
    "stocks worth researching",
    "which stocks are worth researching",
)


def detect_company(text: str) -> str | None:
    """Return a canonical company name if the text clearly names one, else None."""
    lowered = text.lower()
    for phrase in sorted(COMPANY_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            return COMPANY_ALIASES[phrase]
    return None


def is_best_stock_question(text: str) -> bool:
    """True for 'which stock should I buy' / 'stocks worth researching' style questions."""
    lowered = text.lower()
    return any(marker in lowered for marker in BEST_STOCK_MARKERS)


def get_market_headlines(limit: int = 8) -> list[dict[str, str]]:
    """Fetch current general stock-market/trading headlines (India-focused)."""
    return fetch_google_news(MARKET_HEADLINE_QUERY, limit=limit, category="market")


def get_company_news(company: str, limit: int = 6) -> list[dict[str, str]]:
    """Fetch current news for a specific company."""
    return fetch_google_news(f"{company} share price news", limit=limit, category="market")


def build_market_detail_context(company: str | None, articles: list[dict[str, str]]) -> str:
    """Compact plain-text context for Qwen: only titles, no URLs/sources/IDs."""
    lines = []
    if company:
        lines.append(f"Company: {company}")
    lines.append("Recent headlines:")
    for article in articles[:5]:
        title = (article.get("title") or "").strip()
        if title:
            lines.append(f"- {title}")
    return "\n".join(lines)


def research_candidates_context(candidates_with_articles: list[tuple[str, list[dict[str, str]]]]) -> str:
    """Compact multi-company context for the 'best stock' comparison.

    Only ever built from headlines actually retrieved per company — never
    invented prices or fundamentals. Candidates with no retrieved data are
    left out entirely rather than padded with a placeholder, so Qwen never
    treats "no data" as if it were a data point. Returns "" if NONE of the
    candidates have any retrieved data — callers should treat that as
    "insufficient data" and skip calling Qwen entirely.
    """
    lines = ["Companies and their recent headlines (not investment advice):"]
    included = 0
    for company, articles in candidates_with_articles:
        headlines = [a["title"].strip() for a in articles[:2] if a.get("title")]
        if not headlines:
            continue
        lines.append(f"- {company}: " + " | ".join(headlines))
        included += 1
    return "\n".join(lines) if included else ""


def has_sufficient_market_data(candidates_with_articles: list[tuple[str, list[dict[str, str]]]]) -> bool:
    """True if at least one candidate has real retrieved headlines to compare."""
    return any(articles for _, articles in candidates_with_articles)