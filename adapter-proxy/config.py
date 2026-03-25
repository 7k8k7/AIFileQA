"""Configuration loader — reads YAML and builds adapter instances."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from adapters.base import BaseAdapter
from adapters.huggingface import HuggingFaceTGIAdapter
from adapters.generic import GenericHTTPAdapter

logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("ADAPTER_CONFIG", "config.yaml")

ADAPTER_TYPES: dict[str, type] = {
    "huggingface_tgi": HuggingFaceTGIAdapter,
    "generic": GenericHTTPAdapter,
}


def load_adapters() -> dict[str, BaseAdapter]:
    """Load config.yaml and return {model_name: adapter_instance}."""
    path = Path(CONFIG_PATH)
    if not path.exists():
        logger.warning("Config file not found: %s — no adapters loaded", path)
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    adapters: dict[str, BaseAdapter] = {}
    for entry in raw.get("adapters", []):
        adapter_type = entry.get("type", "")
        model_name = entry.get("model_name", "")
        base_url = entry.get("base_url", "")

        if not model_name or not base_url:
            logger.warning("Skipping adapter with missing model_name or base_url: %s", entry)
            continue

        cls = ADAPTER_TYPES.get(adapter_type)
        if cls is None:
            logger.warning("Unknown adapter type '%s' for model '%s'", adapter_type, model_name)
            continue

        if adapter_type == "generic":
            adapter = GenericHTTPAdapter(
                model_name=model_name,
                base_url=base_url,
                chat_endpoint=entry.get("chat_endpoint", "/generate"),
                request_template=entry.get(
                    "request_template",
                    '{"prompt": {{ prompt | tojson }}, "max_tokens": {{ max_tokens }}}',
                ),
                response_content_path=entry.get("response_content_path", "text"),
                stream=entry.get("stream", False),
                stream_content_path=entry.get("stream_content_path", "token.text"),
                stream_done_field=entry.get("stream_done_field", ""),
            )
        else:
            adapter = cls(model_name=model_name, base_url=base_url)

        adapters[model_name] = adapter
        logger.info("Loaded adapter: %s (%s) → %s", model_name, adapter_type, base_url)

    logger.info("Total adapters loaded: %d", len(adapters))
    return adapters
