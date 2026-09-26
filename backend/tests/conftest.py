import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("PLAYWRIGHT_MOCK", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pqa_pytest.db")
