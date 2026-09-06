"""Small in-memory conversation state for the single-user local app."""

_state: dict[str, object] = {"last_article": None, "last_category": "general", "last_location": None, "last_mode": "headlines"}


def get_state() -> dict[str, object]:
    return _state.copy()


def update_state(*, article: dict | None, category: str, location: str | None, mode: str) -> None:
    _state.update({"last_article": article, "last_category": category, "last_location": location, "last_mode": mode})
