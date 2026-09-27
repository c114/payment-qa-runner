"""FastAPI application entrypoint — Payment Test Runner 2.0.0."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import ensure_data_dirs, get_settings
from app.core.database import Base, SessionLocal, engine, ensure_schema
from app.seed.bootstrap import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("payment_runner")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    logger.info("Payment Test Runner 2.0.0 API started (LIVE)")
    yield


settings = get_settings()
app = FastAPI(title="Payment Test Runner", version="2.0.0", lifespan=lifespan)

_cors = settings.cors_origin_list
if not _cors or _cors == ["*"]:
    _cors_origins = ["*"]
    _cors_creds = False
else:
    _cors_origins = _cors
    _cors_creds = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

_docs = Path(__file__).resolve().parents[2] / "docs"
if not _docs.is_dir():
    _docs = Path("/app/docs")
_fix = _docs / "fixtures"
if _fix.is_dir():
    app.mount("/fixtures", StaticFiles(directory=str(_fix)), name="fixtures")


@app.get("/")
def root():
    return {
        "name": "Payment Test Runner",
        "version": "2.0.0",
        "mode": "LIVE",
        "docs": "/docs",
        "health": "/api/health",
    }
