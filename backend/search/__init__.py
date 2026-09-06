"""Multi-provider search subsystem.

Public API:
    from backend.search import web_search, AllProvidersFailedError, SearchResult

Everything else in this package (cache.py, providers.py) is internal —
main.py and future tools should only ever import from here.
"""

from .pipeline import AllProvidersFailedError, web_search
from .providers import SearchResult

__all__ = ["web_search", "AllProvidersFailedError", "SearchResult"]