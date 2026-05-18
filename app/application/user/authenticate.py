from datetime import datetime, timedelta

import bcrypt
import structlog

from app.domain.user.entities import UserStatus
from app.domain.user.repository import IUserRepository
from app.infrastructure.api.middleware.auth import create_access_token, create_refresh_token

logger = structlog.get_logger()


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


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

        if not _verify_password(password, user.password_hash):
            logger.warning("authentication_failed_invalid_password", email=email)
            raise ValueError("Invalid credentials")

        user.record_login("unknown")
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
