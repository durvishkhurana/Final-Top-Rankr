import importlib.util
from pathlib import Path

from api.schemas import LoginIn


def test_demo_accounts_have_addresses_that_can_sign_in() -> None:
    # reserved domains such as .invalid fail the sign-in form's email check
    path = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("seed_script", path)
    assert spec and spec.loader
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    emails = [seed.demo_email(i, role) for i, (_, role, *_) in enumerate(seed.DEMO_PEOPLE)]
    assert set(seed.STUDENTS) <= set(emails) and len(set(emails)) == len(emails)
    for email in emails:
        LoginIn(email=email, password="x")
