from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from app.domain.user.services import Permission, permission_checker
from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.repositories.user_repository import UserRepository


class AuthSettings(BaseSettings):
    secret_key: str = "change_me_in_production_secret_key_min_32_chars"
    refresh_secret_key: str = "change_me_in_production_refresh_key_min_32_chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"


settings = AuthSettings()
security = HTTPBearer()


class TokenData(BaseModel):
    user_id: UUID
    email: str
    role: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.refresh_secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role")
        if user_id is None or email is None or role is None:
            raise credentials_exception
        token_data = TokenData(user_id=UUID(user_id), email=email, role=role)
    except (JWTError, ValueError):
        raise credentials_exception

    request.state.user = token_data
    return token_data


def require_role(required_role: str):
    async def role_checker(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
    ) -> TokenData:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            role = payload.get("role")
            if role != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            return TokenData(user_id=UUID(user_id), email=email, role=role)
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return role_checker


def require_permission(required_permission: Permission):
    async def permission_checker_dep(
        current_user: Annotated[TokenData, Depends(get_current_user)]
    ) -> TokenData:
        from app.domain.user.entities import UserRole

        user_role = UserRole(current_user.role)
        if not permission_checker.has_permission(user_role, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {required_permission.value}"
            )
        return current_user
    return permission_checker_dep


async def require_sensor_access(
    sensor_id: UUID,
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> TokenData:
    from app.domain.user.entities import UserRole

    if current_user.role == UserRole.ADMIN.value:
        return current_user

    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        assigned = await repo.get_assigned_sensors(current_user.user_id)
        if sensor_id in assigned:
            return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this sensor"
    )
