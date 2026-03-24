from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    normalized = (level or "INFO").upper()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": normalized,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": normalized,
            },
        }
    )


def summarize_provider(provider: Any | None) -> str:
    if provider is None:
        return "provider=<none>"

    provider_id = getattr(provider, "id", "<unknown>")
    provider_type = getattr(provider, "provider_type", "<unknown>")
    model_name = getattr(provider, "model_name", "<unknown>")
    enable_embedding = bool(getattr(provider, "enable_embedding", False))
    embedding_model = getattr(provider, "embedding_model", "") if enable_embedding else ""
    embedding_desc = embedding_model if embedding_model else ("disabled" if not enable_embedding else "unset")
    return (
        f"provider_id={provider_id} "
        f"type={provider_type} "
        f"chat_model={model_name} "
        f"embedding={embedding_desc}"
    )


def summarize_chunks(chunks: list[Any], *, limit: int = 3) -> str:
    if not chunks:
        return "chunks=[]"

    preview: list[str] = []
    for chunk in chunks[:limit]:
        document_name = getattr(chunk, "document_name", "未知文档")
        chunk_index = getattr(chunk, "chunk_index", "?")
        score = getattr(chunk, "score", None)
        if score is None:
            preview.append(f"{document_name}#{chunk_index}")
        else:
            preview.append(f"{document_name}#{chunk_index}@{float(score):.2f}")

    suffix = "" if len(chunks) <= limit else f" ...(+{len(chunks) - limit})"
    return f"chunks=[{', '.join(preview)}]{suffix}"


def clip_text(value: str | None, *, max_len: int = 160) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max(max_len - 1, 1)].rstrip() + "…"
