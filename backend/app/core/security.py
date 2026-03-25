from __future__ import annotations

from functools import lru_cache
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

SECRET_PREFIX = "enc:"


@lru_cache(maxsize=1)
def _get_provider_fernet() -> Fernet:
    configured_key = (settings.provider_secret_key or "").strip()
    if configured_key:
        return Fernet(configured_key.encode("utf-8"))

    secret_path = settings.provider_secret_path
    if secret_path.exists():
        return Fernet(secret_path.read_text(encoding="utf-8").strip().encode("utf-8"))

    generated_key = Fernet.generate_key()
    secret_path.write_text(generated_key.decode("utf-8"), encoding="utf-8")
    logger.warning(
        "DOCQA_PROVIDER_SECRET_KEY 未配置，已生成本地 provider 密钥文件：%s。生产环境建议改用环境变量注入固定密钥。",
        secret_path,
    )
    return Fernet(generated_key)


def encrypt_provider_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith(SECRET_PREFIX):
        return value
    token = _get_provider_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def decrypt_provider_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(SECRET_PREFIX):
        return value

    token = value[len(SECRET_PREFIX):]
    try:
        return _get_provider_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Provider 密钥解密失败，请检查 DOCQA_PROVIDER_SECRET_KEY 或本地密钥文件是否变化。")
        raise ValueError("Provider 密钥解密失败") from exc


def is_encrypted_provider_secret(value: str | None) -> bool:
    return bool(value and value.startswith(SECRET_PREFIX))


def reset_provider_fernet_cache() -> None:
    _get_provider_fernet.cache_clear()
