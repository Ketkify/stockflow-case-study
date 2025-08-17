import os

DEFAULT_DB_URL = "postgresql://postgres:password@localhost:5432/stockflow"

# Use an absolute path for SQLite to avoid CWD surprises
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SQLITE_PATH = os.path.join(REPO_ROOT, "stockflow.db")
SQLITE_DB_URL = f"sqlite:///{SQLITE_PATH}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
if os.getenv("USE_SQLITE", "0") == "1":
    DATABASE_URL = SQLITE_DB_URL

DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
