from uuid import uuid4

import bcrypt
import structlog

from app.domain.user.entities import UserRole, User, UserStatus
from app.domain.user.repository import IUserRepository

logger = structlog.get_logger()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class CreateUser:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def execute(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        phone: str | None = None,
    ) -> dict:
        existing_user = await self.user_repository.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")

        try:
            user_role = UserRole(role)
        except ValueError:
            raise ValueError(f"Invalid role: {role}")

        password_hash = _hash_password(password)

        user = User(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=user_role,
            phone=phone,
            status=UserStatus.ACTIVE,
        )

        saved_user = await self.user_repository.save(user)

        logger.info(
            "user_created",
            user_id=str(saved_user.id),
            email=saved_user.email,
            role=saved_user.role.value,
        )

        return {
            "id": str(saved_user.id),
            "email": saved_user.email,
            "full_name": saved_user.full_name,
            "role": saved_user.role.value,
            "phone": saved_user.phone,
            "status": saved_user.status.value,
            "created_at": saved_user.created_at.isoformat(),
        }
