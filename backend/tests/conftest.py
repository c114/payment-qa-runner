"""Pytest fixtures for Payment Test Runner 2.0.0."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use temp sqlite before importing app
_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["JWT_SECRET"] = "test-jwt-secret-for-pytest"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "TestAdmin_123!"
os.environ["PLAYWRIGHT_MOCK"] = "0"
os.environ["LIVE_TESTING_ENABLED"] = "true"
os.environ["APP_VERSION"] = "2.0.0"

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.database import Base, get_db
from app.main import app
from app.seed.bootstrap import seed_all


@pytest.fixture()
def db_engine():
    engine = create_engine(
        f"sqlite:///{_db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    seed_all(session)
    yield session
    session.close()


@pytest.fixture()
def client(db_engine, db):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "TestAdmin_123!"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
