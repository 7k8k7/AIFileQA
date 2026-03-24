"""Provider CRUD + test-connection service."""

import httpx
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderConfig
from app.core.observability import summarize_provider
from app.schemas.provider import (
    ProviderCreate,
    ProviderUpdate,
    ProviderOut,
    ProviderDetailOut,
    mask_api_key,
    validate_provider_values,
)
from app.services.provider_url import build_provider_url, normalize_provider_base_url

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_provider_out(provider: ProviderConfig) -> ProviderOut:
    out = ProviderOut.model_validate(provider)
    out.api_key = mask_api_key(provider.api_key)
    return out


async def list_providers(db: AsyncSession) -> list[ProviderOut]:
    rows = (
        await db.execute(select(ProviderConfig).order_by(ProviderConfig.created_at))
    ).scalars().all()
    out = []
    for r in rows:
        out.append(to_provider_out(r))
    return out


async def get_provider(db: AsyncSession, provider_id: str) -> ProviderConfig | None:
    return (
        await db.execute(select(ProviderConfig).where(ProviderConfig.id == provider_id))
    ).scalar_one_or_none()


async def get_provider_detail(
    db: AsyncSession, provider_id: str
) -> ProviderDetailOut | None:
    provider = await get_provider(db, provider_id)
    if not provider:
        return None
    return ProviderDetailOut.model_validate(provider)


async def create_provider(db: AsyncSession, data: ProviderCreate) -> ProviderConfig:
    provider = ProviderConfig(
        provider_type=data.provider_type,
        base_url=normalize_provider_base_url(data.base_url),
        model_name=data.model_name,
        api_key=data.api_key,
        embedding_model=data.embedding_model.strip(),
        enable_embedding=data.enable_embedding,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        timeout_seconds=data.timeout_seconds,
        is_default=False,
        last_test_success=False,
        last_test_message="尚未测试连接",
        last_test_at=None,
    )

    if data.is_default:
        raise ValueError("请先测试连接成功，再设为默认供应商")

    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    logger.info("Provider created: %s default=%s", summarize_provider(provider), provider.is_default)
    return provider


async def update_provider(
    db: AsyncSession, provider_id: str, data: ProviderUpdate
) -> ProviderConfig | None:
    provider = await get_provider(db, provider_id)
    if not provider:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("api_key") == "":
        update_data.pop("api_key")

    merged_provider_type = update_data.get("provider_type", provider.provider_type)
    merged_api_key = update_data.get("api_key", provider.api_key)
    merged_enable_embedding = update_data.get("enable_embedding", provider.enable_embedding)
    merged_embedding_model = update_data.get("embedding_model", provider.embedding_model)
    validate_provider_values(
        provider_type=merged_provider_type,
        api_key=merged_api_key,
        enable_embedding=merged_enable_embedding,
        embedding_model=merged_embedding_model,
    )

    connectivity_fields = {"provider_type", "base_url", "model_name", "api_key", "timeout_seconds"}
    connectivity_changed = bool(connectivity_fields & set(update_data.keys()))

    for key, value in update_data.items():
        if key == "base_url" and value is not None:
            value = normalize_provider_base_url(value)
        if key == "embedding_model" and value is not None:
            value = value.strip()
        setattr(provider, key, value)

    if connectivity_changed:
        provider.last_test_success = False
        provider.last_test_message = "配置已修改，请重新测试连接"
        provider.last_test_at = None
        if provider.is_default:
            provider.is_default = False

    await db.flush()
    await db.refresh(provider)
    logger.info(
        "Provider updated: %s changed_fields=%s",
        summarize_provider(provider),
        ",".join(sorted(update_data.keys())) if update_data else "<none>",
    )
    return provider


async def set_default_provider(db: AsyncSession, provider_id: str) -> bool:
    provider = await get_provider(db, provider_id)
    if not provider:
        return False
    if not provider.last_test_success:
        raise ValueError("请先测试连接成功，再设为默认供应商")
    await _clear_defaults(db)
    provider.is_default = True
    await db.flush()
    logger.info("Provider set as default: %s", summarize_provider(provider))
    return True


async def delete_provider(db: AsyncSession, provider_id: str) -> bool:
    provider = await get_provider(db, provider_id)
    if not provider:
        return False
    if provider.is_default:
        raise ValueError("无法删除默认供应商，请先设置其他供应商为默认")
    logger.info("Provider deleted: %s", summarize_provider(provider))
    await db.delete(provider)
    await db.flush()
    return True


async def test_connection(db: AsyncSession, provider_id: str) -> dict:
    """Send a lightweight request to the provider to verify connectivity."""
    provider = await get_provider(db, provider_id)
    if not provider:
        return {"success": False, "message": "供应商不存在"}

    # Build test request based on provider type
    url = normalize_provider_base_url(provider.base_url)
    headers: dict[str, str] = {}
    if provider.provider_type == "claude":
        url = build_provider_url(url, "/v1/messages")
        headers["anthropic-version"] = "2023-06-01"
        if provider.api_key:
            headers["x-api-key"] = provider.api_key
    else:
        url = build_provider_url(url, "/v1/models")
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

    try:
        logger.info("Provider connectivity test started: %s", summarize_provider(provider))
        async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
            if provider.provider_type == "claude":
                # Anthropic: minimal messages request
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": provider.model_name,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
            else:
                # OpenAI-compatible: list models
                resp = await client.get(url, headers=headers)

            if resp.status_code < 400:
                provider.last_test_success = True
                provider.last_test_message = "连接成功"
                provider.last_test_at = _utcnow()
                await db.flush()
                await db.refresh(provider)
                logger.info("Provider connectivity test succeeded: %s", summarize_provider(provider))
                return {
                    "success": True,
                    "message": "连接成功",
                    "provider": to_provider_out(provider),
                }
            else:
                body = resp.text[:200]
                provider.last_test_success = False
                provider.last_test_message = f"HTTP {resp.status_code}: {body}"
                provider.last_test_at = _utcnow()
                if provider.is_default:
                    provider.is_default = False
                await db.flush()
                await db.refresh(provider)
                logger.warning(
                    "Provider connectivity test failed: %s status=%s body=%s",
                    summarize_provider(provider),
                    resp.status_code,
                    body,
                )
                return {
                    "success": False,
                    "message": f"HTTP {resp.status_code}: {body}",
                    "provider": to_provider_out(provider),
                }
    except httpx.TimeoutException:
        provider.last_test_success = False
        provider.last_test_message = "连接超时"
        provider.last_test_at = _utcnow()
        if provider.is_default:
            provider.is_default = False
        await db.flush()
        await db.refresh(provider)
        logger.warning("Provider connectivity test timed out: %s", summarize_provider(provider))
        return {
            "success": False,
            "message": "连接超时",
            "provider": to_provider_out(provider),
        }
    except Exception as e:
        provider.last_test_success = False
        provider.last_test_message = f"连接失败: {str(e)[:200]}"
        provider.last_test_at = _utcnow()
        if provider.is_default:
            provider.is_default = False
        await db.flush()
        await db.refresh(provider)
        logger.warning(
            "Provider connectivity test errored: %s error=%s",
            summarize_provider(provider),
            str(e)[:200],
        )
        return {
            "success": False,
            "message": f"连接失败: {str(e)[:200]}",
            "provider": to_provider_out(provider),
        }


async def _clear_defaults(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
        )
    ).scalars().all()
    for r in rows:
        r.is_default = False
