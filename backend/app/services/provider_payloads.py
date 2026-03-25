"""Helpers for provider-specific request payload differences."""

from __future__ import annotations

import json
import re
from typing import Any

_UNSUPPORTED_PARAMETER_RE = re.compile(
    r"Unsupported parameter:\s*[\"']?(?P<param>[\w.-]+)[\"']?",
    re.IGNORECASE,
)
_USE_INSTEAD_RE = re.compile(
    r"Use\s+[\"'](?P<param>[\w.-]+)[\"']\s+instead",
    re.IGNORECASE,
)
_NON_REMOVABLE_FIELDS = {"model", "messages", "stream", "system"}


def build_completion_limit_payload(provider_type: str, max_tokens: int) -> dict[str, int]:
    """OpenAI official models use max_completion_tokens; others still use max_tokens."""
    if provider_type == "openai":
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def adapt_payload_for_unsupported_parameter(
    payload: dict[str, Any],
    body: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    error_message, error_param = extract_error_details(body)
    if not error_message or "unsupported parameter" not in error_message.lower():
        return None, None

    suggested_param = _extract_suggested_parameter(error_message)
    next_payload = dict(payload)

    if error_param and suggested_param and error_param in next_payload:
        value = next_payload.pop(error_param)
        next_payload[suggested_param] = value
        if next_payload != payload:
            return next_payload, f"{error_param} -> {suggested_param}"

    if error_param == "temperature" and "temperature" in next_payload:
        next_payload.pop("temperature", None)
        if next_payload != payload:
            return next_payload, "removed temperature"

    if error_param and error_param in next_payload and error_param not in _NON_REMOVABLE_FIELDS:
        next_payload.pop(error_param, None)
        if next_payload != payload:
            return next_payload, f"removed {error_param}"

    return None, None


def extract_error_details(body: str | None) -> tuple[str | None, str | None]:
    normalized_body = (body or "").strip()
    if not normalized_body:
        return None, None

    error_message: str | None = None
    error_param: str | None = None

    try:
        parsed = json.loads(normalized_body)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        error_obj = parsed.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            param = error_obj.get("param")
            if isinstance(message, str) and message.strip():
                error_message = message.strip()
            if isinstance(param, str) and param.strip():
                error_param = param.strip()

    error_message = error_message or normalized_body
    if not error_param:
        match = _UNSUPPORTED_PARAMETER_RE.search(error_message)
        if match:
            error_param = match.group("param")

    return error_message, error_param


def _extract_suggested_parameter(error_message: str) -> str | None:
    match = _USE_INSTEAD_RE.search(error_message)
    if not match:
        return None
    return match.group("param")
