from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.auth import require_role
from app.infrastructure.database.models.config import GlobalConfigModel

router = APIRouter(prefix="/config", tags=["Configuration"])


class ConfigResponse(BaseModel):
    key: str
    value: str
    description: str | None


class UpdateConfigRequest(BaseModel):
    value: str


@router.get("", dependencies=[Depends(require_role("admin"))])
async def get_all_config(
    session: AsyncSession = Depends(get_current_session),
):
    result = await session.execute(select(GlobalConfigModel))
    configs = result.scalars().all()

    return [
        ConfigResponse(
            key=config.key,
            value=str(config.value),
            description=None,
        )
        for config in configs
    ]


@router.get("/{key}")
async def get_config(
    key: str,
    session: AsyncSession = Depends(get_current_session),
):
    result = await session.execute(
        select(GlobalConfigModel).where(GlobalConfigModel.key == key)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found"
        )

    return ConfigResponse(
        key=config.key,
        value=str(config.value),
        description=None,
    )


@router.put("/{key}", dependencies=[Depends(require_role("admin"))])
async def update_config(
    key: str,
    request: UpdateConfigRequest,
    session: AsyncSession = Depends(get_current_session),
):
    result = await session.execute(
        select(GlobalConfigModel).where(GlobalConfigModel.key == key)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found"
        )

    config.value = request.value
    await session.flush()
    await session.refresh(config)

    return ConfigResponse(
        key=config.key,
        value=str(config.value),
        description=None,
    )
