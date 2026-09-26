"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import ensure_data_dirs, get_settings
from app.core.database import Base, SessionLocal, engine, ensure_schema
from app.seed.bootstrap import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("payment_qa")


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
    logger.info("Payment QA Runner API started")
    yield


settings = get_settings()
app = FastAPI(title="Payment QA Runner", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Payment QA Runner", "docs": "/docs", "health": "/api/health"}
