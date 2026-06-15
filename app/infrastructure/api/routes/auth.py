from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.user.authenticate import AuthenticateUser
from app.domain.audit.entities import ActionType
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.audit import audit_action
from app.infrastructure.api.middleware.auth import create_access_token, get_current_user, TokenData
from app.infrastructure.database.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=LoginResponse)
@audit_action(action_type=ActionType.USER_LOGIN, resource_type="user")
async def login(
    request: Request,
    login_request: LoginRequest,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    use_case = AuthenticateUser(repo)

    try:
        result = await use_case.execute(login_request.email, login_request.password)
        return LoginResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from e


@router.post("/refresh")
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_current_session),
):
    from jose import JWTError, jwt
    from app.infrastructure.api.middleware.auth import settings

    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.refresh_secret_key,
            algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        repo = UserRepository(session)
        from uuid import UUID
        user = await repo.get_by_id(UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(current_user.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "status": user.status.value,
    }
