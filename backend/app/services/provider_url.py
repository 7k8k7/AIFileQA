"""Helpers for building provider API URLs without duplicating /v1."""


def normalize_provider_base_url(base_url: str) -> str:
    """Accept provider root URLs with or without a trailing /v1."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def build_provider_url(base_url: str, suffix: str) -> str:
    base = normalize_provider_base_url(base_url).rstrip("/")
    return f"{base}{suffix}"
