"""Shared test fixtures for backend unit tests."""

from __future__ import annotations

import importlib
import os
import sys
from types import SimpleNamespace

import pytest


os.environ["DEBUG"] = "true"
os.environ["PROVIDER_SECRET_KEY"] = "5dPAlWTMwVzKhI1-w4n1vCtbmZh9rqx8pFazc2DSES0="


def _load_app_modules(monkeypatch, tmp_path) -> SimpleNamespace:
    """Reload app modules with test-specific environment variables."""
    db_path = (tmp_path / "test.db").as_posix()
    upload_dir = (tmp_path / "uploads").as_posix()
    vector_dir = (tmp_path / "chroma").as_posix()
    secret_file = (tmp_path / "provider_secret.key").as_posix()

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", upload_dir)
    monkeypatch.setenv("VECTOR_STORE_DIR", vector_dir)
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("PROVIDER_SECRET_KEY", "5dPAlWTMwVzKhI1-w4n1vCtbmZh9rqx8pFazc2DSES0=")
    monkeypatch.setenv("PROVIDER_SECRET_FILE", secret_file)

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    return SimpleNamespace(
        main=importlib.import_module("app.main"),
        database=importlib.import_module("app.core.database"),
        document_models=importlib.import_module("app.models.document"),
        job_models=importlib.import_module("app.models.job"),
        provider_models=importlib.import_module("app.models.provider"),
        chat_models=importlib.import_module("app.models.chat"),
        documents_api=importlib.import_module("app.api.documents"),
        providers_api=importlib.import_module("app.api.providers"),
        chat_api=importlib.import_module("app.api.chat"),
        parsing_task=importlib.import_module("app.services.parsing_task"),
    )


@pytest.fixture
def app_ctx(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Provide a clean app context with in-memory test database."""
    return _load_app_modules(monkeypatch, tmp_path)
