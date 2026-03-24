from __future__ import annotations

from types import SimpleNamespace

from app.core.observability import clip_text, summarize_chunks, summarize_provider


def test_summarize_provider_excludes_api_key():
    provider = SimpleNamespace(
        id="p-1",
        provider_type="openai",
        model_name="gpt-4o-mini",
        api_key="sk-super-secret",
        enable_embedding=True,
        embedding_model="text-embedding-3-small",
    )

    summary = summarize_provider(provider)

    assert "provider_id=p-1" in summary
    assert "chat_model=gpt-4o-mini" in summary
    assert "text-embedding-3-small" in summary
    assert "sk-super-secret" not in summary


def test_summarize_chunks_formats_preview_and_limit():
    chunks = [
        SimpleNamespace(document_name="a.txt", chunk_index=0, score=0.91),
        SimpleNamespace(document_name="b.txt", chunk_index=2, score=None),
        SimpleNamespace(document_name="c.txt", chunk_index=4, score=0.44),
        SimpleNamespace(document_name="d.txt", chunk_index=1, score=0.12),
    ]

    summary = summarize_chunks(chunks, limit=3)

    assert "a.txt#0@0.91" in summary
    assert "b.txt#2" in summary
    assert "c.txt#4@0.44" in summary
    assert "...(+1)" in summary


def test_clip_text_truncates_long_value():
    value = "x" * 300
    clipped = clip_text(value, max_len=20)
    assert len(clipped) == 20
    assert clipped.endswith("…")
