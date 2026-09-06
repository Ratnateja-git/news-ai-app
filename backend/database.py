import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017"
)

DATABASE_NAME = os.getenv(
    "DATABASE_NAME",
    "newsai"
)

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)

db = client[DATABASE_NAME]

news_collection = db["news"]

try:
    news_collection.create_index("url", unique=True)
except PyMongoError:
    # MongoDB is optional; the live RSS experience still works without it.
    pass


def check_connection() -> bool:
    """Check whether MongoDB is reachable."""
    try:
        client.admin.command("ping")
        return True
    except PyMongoError:
        return False


def save_articles(
    articles: list[dict[str, str]]
) -> int:
    """Save new articles and skip duplicates."""

    inserted_count = 0

    for article in articles:
        try:
            result = news_collection.update_one(
                {"url": article["url"]},
                {"$setOnInsert": article},
                upsert=True,
            )

            if result.upserted_id is not None:
                inserted_count += 1

        except PyMongoError:
            continue

    return inserted_count


def get_stored_news(
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return recently stored news articles."""

    query = {}

    if category:
        query["category"] = category

    articles = list(
        news_collection.find(
            query,
            {"_id": 0},
        )
        .sort("collected_at", -1)
        .limit(limit)
    )

    return articles
