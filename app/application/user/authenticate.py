from datetime import datetime, timedelta

import structlog
from passlib.context import CryptContext

from app.domain.user.entities import UserStatus
from app.domain.user.repository import IUserRepository
from app.infrastructure.api.middleware.auth import create_access_token, create_refresh_token

logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticateUser:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def execute(self, email: str, password: str) -> dict:
        user = await self.user_repository.get_by_email(email)
        
        if not user:
            logger.warning("authentication_failed_user_not_found", email=email)
            raise ValueError("Invalid credentials")

        if user.status != UserStatus.ACTIVE:
            logger.warning("authentication_failed_user_inactive", email=email, status=user.status.value)
            raise ValueError("User account is not active")

        if not pwd_context.verify(password, user.password_hash):
            logger.warning("authentication_failed_invalid_password", email=email)
            raise ValueError("Invalid credentials")

        user.update_last_login()
        await self.user_repository.update(user)

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)}
        )

        logger.info(
            "user_authenticated",
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
            },
        }
