import os
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pqa_smoke.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.core.database import Base, engine, SessionLocal
from app.seed.bootstrap import seed_all
from app.models.models import AdminUser, NetworkProfile, PageMapping, WorkflowStep


def test_create_all_and_seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
        assert db.query(AdminUser).count() == 1
        assert db.query(NetworkProfile).filter_by(name="Direct").count() == 1
        assert db.query(PageMapping).count() >= 10
        assert db.query(WorkflowStep).count() >= 5
    finally:
        db.close()
