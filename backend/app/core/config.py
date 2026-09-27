"""Application settings loaded from environment."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_email: str = "admin@example.com"
    admin_password: str = "ChangeMe_Admin_123!"

    jwt_secret: str = "dev-jwt-secret-change-in-production"
    encryption_key: str = ""
    access_token_expire_minutes: int = 1440

    database_url: str = "sqlite:////workspace/payment-qa-runner/data/payment_qa.db"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    app_version: str = "1.3.1"

    playwright_mock: int = 0
    live_testing_enabled: bool = False
    session_secret: str = ""
    proxy_test_url: str = "http://1.1.1.1/"
    session_heartbeat_stale_sec: int = 30
    worker_poll_interval_sec: float = 2.0
    max_concurrent_browsers: int = 1
    screenshot_dir: str = "/workspace/payment-qa-runner/data/screenshots"
    report_dir: str = "/workspace/payment-qa-runner/data/reports"
    log_dir: str = "/workspace/payment-qa-runner/data/logs"
    session_dir: str = "/workspace/payment-qa-runner/data/sessions"
    browser_debug: int = 0

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_data_dirs() -> None:
    s = get_settings()
    candidates = [s.screenshot_dir, s.report_dir, s.log_dir, s.session_dir]
    if s.database_url.startswith("sqlite"):
        # sqlite:////abs/path.db → /abs/path.db ; sqlite:///rel.db → rel.db
        if s.database_url.startswith("sqlite:////"):
            db_path = "/" + s.database_url[len("sqlite:////"):]
        else:
            db_path = s.database_url[len("sqlite:///"):]
        candidates.append(os.path.dirname(db_path) or ".")
    for d in candidates:
        if d and d not in (".", ""):
            try:
                os.makedirs(d, exist_ok=True)
            except PermissionError:
                pass
