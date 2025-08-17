# tests/conftest.py
import os
import sys
import importlib
import pytest
from pathlib import Path

# Ensure repo root is on sys.path so `import src...` works
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    """
    Force the app to use an in-memory SQLite DB for tests.
    """
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ.pop("USE_SQLITE", None)  # don't let this override DATABASE_URL

    # Reload config so create_app reads the new env
    import src.config as cfg
    importlib.reload(cfg)

    yield  # session-scoped setup only

@pytest.fixture()
def app(_set_test_env):
    from src.app import create_app
    from src.db import db

    app = create_app()

    # Fresh schema per test
    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    # Cleanup
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def db_session(app):
    from src.db import db
    with app.app_context():
        yield db.session
        db.session.rollback()
