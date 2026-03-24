"""Provider API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.provider import ProviderCreate, ProviderUpdate, ProviderOut, mask_api_key
from app.services.provider_service import (
    list_providers,
    get_provider,
    create_provider,
    update_provider,
    set_default_provider,
    delete_provider,
    test_connection,
)

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
async def get_providers(db: AsyncSession = Depends(get_db)):
    return await list_providers(db)


@router.post("", response_model=ProviderOut, status_code=201)
async def add_provider(
    data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
):
    provider = await create_provider(db, data)
    out = ProviderOut.model_validate(provider)
    out.api_key = mask_api_key(provider.api_key)
    return out


@router.put("/{provider_id}", response_model=ProviderOut)
async def modify_provider(
    provider_id: str,
    data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    provider = await update_provider(db, provider_id, data)
    if not provider:
        raise HTTPException(status_code=404, detail="供应商不存在")
    out = ProviderOut.model_validate(provider)
    out.api_key = mask_api_key(provider.api_key)
    return out


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await test_connection(db, provider_id)


@router.post("/{provider_id}/set-default", status_code=204)
async def set_default(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
):
    ok = await set_default_provider(db, provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="供应商不存在")


@router.delete("/{provider_id}", status_code=204)
async def remove_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        deleted = await delete_provider(db, provider_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="供应商不存在")
