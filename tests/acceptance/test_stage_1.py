"""Stage 1 - the skeleton.

Written by hand before the stage and never edited: it states what the stage
has to do. KORTEX.md says the same thing as a rule.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kese.core.settings import Settings
from kese.main import create_app


def test_health_answers_ok() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_app_is_named_kese() -> None:
    assert create_app().title == "kese"


def test_settings_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KESE_ENV", "test")

    assert Settings().env == "test"


def test_the_environment_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KESE_ENV", raising=False)

    assert Settings().env == "local"
