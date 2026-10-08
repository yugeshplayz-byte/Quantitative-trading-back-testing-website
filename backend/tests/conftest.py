import os
import tempfile
from pathlib import Path

# Must be set before `app` is imported: the DB engine is created at import time.
_tmp = tempfile.mkdtemp(prefix="qbt_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["ENABLE_CUSTOM_CODE"] = "false"
os.environ["CUSTOM_CODE_TOKEN"] = ""
os.environ["SEED_DEMO_DATA"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
