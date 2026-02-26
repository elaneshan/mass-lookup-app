"""
API Dependencies
================
Shared resources injected into route handlers.
SearchEngine is instantiated once at startup and reused —
SQLite connections are opened/closed per query inside SearchEngine.
"""

from pathlib import Path
from functools import lru_cache
import os

# DB path: prefer environment variable so Docker can override it
# Default falls back to local dev path
DB_PATH = os.environ.get("DB_PATH", "database/compounds.db")


@lru_cache(maxsize=1)
def get_search_engine():
    """
    Return a singleton SearchEngine instance.
    lru_cache ensures this is only created once per process.
    Raises FileNotFoundError if DB doesn't exist.
    """
    import sys
    # Make sure search/ is importable whether running from project root or api/
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from search.search_engine import SearchEngine
    return SearchEngine(db_path=DB_PATH)