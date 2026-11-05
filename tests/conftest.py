import os
from pathlib import Path

import pytest

FAKE_BASE_URL = "https://panopto.example.edu"
FAKE_CLIENT_ID = "test-client-id"
FAKE_CLIENT_SECRET = "test-secret-do-not-print-0001"
FAKE_TOKEN = "test-token-do-not-print-0002"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No test reads the developer's real environment or a real .env file."""
    for name in list(os.environ):
        if name.startswith("ROOMSYNC_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def panopto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOMSYNC_PANOPTO_BASE_URL", FAKE_BASE_URL)
    monkeypatch.setenv("ROOMSYNC_PANOPTO_CLIENT_ID", FAKE_CLIENT_ID)
    monkeypatch.setenv("ROOMSYNC_PANOPTO_CLIENT_SECRET", FAKE_CLIENT_SECRET)
