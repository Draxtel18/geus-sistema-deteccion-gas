from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit.entities import ActionType
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.audit import audit_action
from app.infrastructure.api.middleware.auth import TokenData, get_current_user
from app.infrastructure.database.repositories.push_token_repository import PushTokenRepository

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class RegisterPushTokenRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=255)
    platform: str = Field(default="expo", max_length=20)


class UnregisterPushTokenRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=255)


@router.post("/push/register")
@audit_action(action_type=ActionType.CONFIG_UPDATED, resource_type="push_token")
async def register_push_token(
    request: Request,
    body: RegisterPushTokenRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = PushTokenRepository(session)
    push_token = await repo.create(
        user_id=current_user.user_id,
        token=body.token,
        platform=body.platform,
    )
    return {
        "id": str(push_token.id),
        "token": push_token.token,
        "platform": push_token.platform,
        "is_active": push_token.is_active,
    }


@router.post("/push/unregister")
@audit_action(action_type=ActionType.CONFIG_UPDATED, resource_type="push_token")
async def unregister_push_token(
    request: Request,
    body: UnregisterPushTokenRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = PushTokenRepository(session)
    deactivated = await repo.deactivate(body.token)
    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Push token not found",
        )
    return {"message": "Push token deactivated successfully"}


@router.get("/push/tokens")
async def list_push_tokens(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = PushTokenRepository(session)
    tokens = await repo.list_active_by_user(current_user.user_id)
    return [
        {
            "id": str(t.id),
            "token": t.token,
            "platform": t.platform,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]
