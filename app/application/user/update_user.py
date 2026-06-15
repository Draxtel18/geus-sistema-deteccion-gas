from uuid import UUID

import bcrypt
import structlog

from app.domain.user.entities import UserRole, UserStatus
from app.domain.user.repository import IUserRepository

logger = structlog.get_logger()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class UpdateUser:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def execute(
        self,
        user_id: UUID,
        email: str | None = None,
        password: str | None = None,
        full_name: str | None = None,
        role: str | None = None,
        status: str | None = None,
    ) -> dict:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if email and email != user.email:
            existing = await self.user_repository.get_by_email(email)
            if existing:
                raise ValueError(f"Email {email} already in use")
            user.email = email

        if password:
            user.password_hash = _hash_password(password)

        if full_name:
            user.full_name = full_name

        if role:
            try:
                user.role = UserRole(role)
            except ValueError:
                raise ValueError(f"Invalid role: {role}")

        if status:
            try:
                user.status = UserStatus(status)
            except ValueError:
                raise ValueError(f"Invalid status: {status}")

        updated_user = await self.user_repository.update(user)

        logger.info(
            "user_updated",
            user_id=str(updated_user.id),
            email=updated_user.email,
            role=updated_user.role.value,
        )

        return {
            "id": str(updated_user.id),
            "email": updated_user.email,
            "full_name": updated_user.full_name,
            "role": updated_user.role.value,
            "status": updated_user.status.value,
            "updated_at": updated_user.updated_at.isoformat(),
        }
