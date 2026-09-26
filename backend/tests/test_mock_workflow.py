import asyncio
import os
from pathlib import Path

# Ensure backend on path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("PLAYWRIGHT_MOCK", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pqa_test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.core.database import Base, engine, SessionLocal
from app.models.models import Environment, TestCase, PayrailsConfig, PageMapping, WorkflowStep
from app.seed.bootstrap import PAGE_MAPPINGS, WORKFLOW_STEPS
from worker.runner import mock_run_case


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_mock_workflow_pass_and_threeds(tmp_path):
    env = Environment(
        name="Sandbox", base_url="https://qa.example.com",
        allowed_domains=["qa.example.com"], env_type="sandbox",
    )
    case_ok = TestCase(case_id="M1", name="ok", payment_test_ref="SUCCESS_VISA", expected_result="SUCCESS", pan_masked="**** **** **** 4242")
    case_3ds = TestCase(case_id="M2", name="3ds", payment_test_ref="3DS_CHALLENGE", expected_result="SUCCESS")
    case_dec = TestCase(case_id="M3", name="dec", payment_test_ref="DECLINED_CARD", expected_result="DECLINED")
    mappings = {m["key"]: PageMapping(**m) for m in PAGE_MAPPINGS}
    steps = [WorkflowStep(**s) for s in WORKFLOW_STEPS]
    payrails = PayrailsConfig()

    r1 = asyncio.run(
        mock_run_case(case_ok, env, payrails, mappings, steps, tmp_path)
    )
    assert r1["status"] == "PASS" and r1["actual"] == "SUCCESS"

    r2 = asyncio.run(
        mock_run_case(case_3ds, env, payrails, mappings, steps, tmp_path)
    )
    assert r2["actual"] == "3DS" and r2["status"] == "FAIL"
    assert any(s.get("step") == "threeds_abort" for s in r2["steps"])

    r3 = asyncio.run(
        mock_run_case(case_dec, env, payrails, mappings, steps, tmp_path)
    )
    assert r3["status"] == "PASS" and r3["actual"] == "DECLINED"


def test_mock_blocks_outside_allowlist(tmp_path):
    env = Environment(
        name="Bad", base_url="https://evil.com",
        allowed_domains=["qa.example.com"], env_type="sandbox",
    )
    case_ok = TestCase(case_id="M4", name="x", payment_test_ref="SUCCESS", expected_result="SUCCESS")
    r = asyncio.run(
        mock_run_case(case_ok, env, PayrailsConfig(), {}, [], tmp_path)
    )
    assert r["status"] == "ERROR"
    assert "allowlist" in (r["error_message"] or "").lower() or "refused" in (r["error_message"] or "").lower()
