import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "")
os.environ.setdefault("PLAYWRIGHT_MOCK", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pqa_pytest.db")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ChangeMe_Admin_123!")
os.environ.setdefault("SCREENSHOT_DIR", "/tmp/pqa_screenshots")
os.environ.setdefault("REPORT_DIR", "/tmp/pqa_reports")
os.environ.setdefault("LOG_DIR", "/tmp/pqa_logs")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.core.database import Base, engine, SessionLocal
    from app.seed.bootstrap import seed_all
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    from app.main import app
    with TestClient(app) as c:
        yield c
