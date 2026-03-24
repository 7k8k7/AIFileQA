from __future__ import annotations

from app.core.security import (
    decrypt_provider_secret,
    encrypt_provider_secret,
    is_encrypted_provider_secret,
)


def test_provider_secret_roundtrip():
    encrypted = encrypt_provider_secret("sk-secret-123")
    assert encrypted != "sk-secret-123"
    assert is_encrypted_provider_secret(encrypted) is True
    assert decrypt_provider_secret(encrypted) == "sk-secret-123"


def test_provider_secret_keeps_legacy_plaintext_compatible():
    assert is_encrypted_provider_secret("plain-secret") is False
    assert decrypt_provider_secret("plain-secret") == "plain-secret"
