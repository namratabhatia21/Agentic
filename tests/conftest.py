import os

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Keep a developer's .env and shell variables out of the tests."""
    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith(("LLM_", "HF_", "EMBEDDING", "ANTHROPIC_", "MODEL", "EFFORT")):
            monkeypatch.delenv(key, raising=False)
