from __future__ import annotations

import importlib
import sys


def _reload_config_module():
    sys.modules.pop("app.core.config", None)
    return importlib.import_module("app.core.config")


def test_prefixed_settings_ignore_global_debug(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.setenv("DOCQA_DEBUG", "true")

    config = _reload_config_module()

    assert config.settings.debug is True


def test_unprefixed_database_url_is_ignored(monkeypatch):
    monkeypatch.delenv("DOCQA_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./wrong.db")

    config = _reload_config_module()

    assert config.settings.database_url == "sqlite+aiosqlite:///./data/docqa.db"
