from __future__ import annotations

from pathlib import Path

import config
from adapters.generic import GenericHTTPAdapter
from adapters.huggingface import HuggingFaceTGIAdapter


def test_load_adapters_builds_registered_types(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
adapters:
  - model_name: "demo-tgi"
    type: "huggingface_tgi"
    base_url: "http://localhost:8082"
  - model_name: "demo-generic"
    type: "generic"
    base_url: "http://localhost:9090"
    chat_endpoint: "/chat"
    request_template: |
      {"prompt": {{ prompt | tojson }}, "max_tokens": {{ max_tokens }}}
    response_content_path: "data.text"
    stream: true
    stream_content_path: "token.text"
    stream_done_field: "done"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", str(config_path))

    adapters = config.load_adapters()

    assert set(adapters) == {"demo-tgi", "demo-generic"}
    assert isinstance(adapters["demo-tgi"], HuggingFaceTGIAdapter)
    assert isinstance(adapters["demo-generic"], GenericHTTPAdapter)
    assert adapters["demo-generic"].chat_endpoint == "/chat"
    assert adapters["demo-generic"].stream_enabled is True
    assert adapters["demo-generic"].response_content_path == "data.text"


def test_load_adapters_skips_unknown_type_and_missing_fields(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
adapters:
  - model_name: "unknown"
    type: "unknown_type"
    base_url: "http://localhost:9999"
  - model_name: ""
    type: "generic"
    base_url: "http://localhost:9090"
  - model_name: "valid"
    type: "generic"
    base_url: "http://localhost:9090"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", str(config_path))

    adapters = config.load_adapters()

    assert list(adapters) == ["valid"]


def test_load_adapters_returns_empty_when_config_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "missing.yaml"
    monkeypatch.setattr(config, "CONFIG_PATH", str(missing_path))

    adapters = config.load_adapters()

    assert adapters == {}
