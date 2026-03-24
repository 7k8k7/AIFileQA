"""Provider CRUD + test-connection service."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderConfig
from app.schemas.provider import ProviderCreate, ProviderUpdate, ProviderOut, mask_api_key


async def list_providers(db: AsyncSession) -> list[ProviderOut]:
    rows = (
        await db.execute(select(ProviderConfig).order_by(ProviderConfig.created_at))
    ).scalars().all()
    out = []
    for r in rows:
        p = ProviderOut.model_validate(r)
        p.api_key = mask_api_key(r.api_key)
        out.append(p)
    return out


async def get_provider(db: AsyncSession, provider_id: str) -> ProviderConfig | None:
    return (
        await db.execute(select(ProviderConfig).where(ProviderConfig.id == provider_id))
    ).scalar_one_or_none()


async def create_provider(db: AsyncSession, data: ProviderCreate) -> ProviderConfig:
    # If this is the first provider, make it default
    count = (await db.execute(select(ProviderConfig))).scalars().all()
    is_first = len(count) == 0

    provider = ProviderConfig(
        provider_type=data.provider_type,
        base_url=data.base_url,
        model_name=data.model_name,
        api_key=data.api_key,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        timeout_seconds=data.timeout_seconds,
        is_default=data.is_default or is_first,
    )

    # If setting as default, clear other defaults
    if provider.is_default:
        await _clear_defaults(db)

    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    return provider


async def update_provider(
    db: AsyncSession, provider_id: str, data: ProviderUpdate
) -> ProviderConfig | None:
    provider = await get_provider(db, provider_id)
    if not provider:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)

    await db.flush()
    await db.refresh(provider)
    return provider


async def set_default_provider(db: AsyncSession, provider_id: str) -> bool:
    provider = await get_provider(db, provider_id)
    if not provider:
        return False
    await _clear_defaults(db)
    provider.is_default = True
    await db.flush()
    return True


async def delete_provider(db: AsyncSession, provider_id: str) -> bool:
    provider = await get_provider(db, provider_id)
    if not provider:
        return False
    if provider.is_default:
        raise ValueError("无法删除默认供应商，请先设置其他供应商为默认")
    await db.delete(provider)
    await db.flush()
    return True


async def test_connection(db: AsyncSession, provider_id: str) -> dict:
    """Send a lightweight request to the provider to verify connectivity."""
    provider = await get_provider(db, provider_id)
    if not provider:
        return {"success": False, "message": "供应商不存在"}

    # Build test request based on provider type
    url = provider.base_url.rstrip("/")
    headers: dict[str, str] = {}
    if provider.api_key:
        if provider.provider_type == "claude":
            headers["x-api-key"] = provider.api_key
            headers["anthropic-version"] = "2023-06-01"
            url += "/v1/messages"
        else:
            headers["Authorization"] = f"Bearer {provider.api_key}"
            url += "/v1/models"

    try:
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
                return {"success": True, "message": "连接成功"}
            else:
                body = resp.text[:200]
                return {"success": False, "message": f"HTTP {resp.status_code}: {body}"}
    except httpx.TimeoutException:
        return {"success": False, "message": "连接超时"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)[:200]}"}


async def _clear_defaults(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
        )
    ).scalars().all()
    for r in rows:
        r.is_default = False
