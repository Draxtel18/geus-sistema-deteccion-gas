from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import PushTokenModel


class PushTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: UUID, token: str, platform: str = "expo") -> PushTokenModel:
        result = await self._session.execute(
            select(PushTokenModel).where(PushTokenModel.token == token)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_active = True
            existing.user_id = user_id
            existing.platform = platform
            await self._session.commit()
            return existing

        push_token = PushTokenModel(
            user_id=user_id,
            token=token,
            platform=platform,
            is_active=True,
        )
        self._session.add(push_token)
        await self._session.commit()
        await self._session.refresh(push_token)
        return push_token

    async def deactivate(self, token: str) -> bool:
        result = await self._session.execute(
            select(PushTokenModel).where(PushTokenModel.token == token)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_active = False
            await self._session.commit()
            return True
        return False

    async def list_active_by_user(self, user_id: UUID) -> list[PushTokenModel]:
        result = await self._session.execute(
            select(PushTokenModel).where(
                PushTokenModel.user_id == user_id,
                PushTokenModel.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def list_active_for_sensor_operators(self, sensor_id: UUID) -> list[PushTokenModel]:
        from app.infrastructure.database.models import UserSensorAssignmentModel

        result = await self._session.execute(
            select(PushTokenModel)
            .join(
                UserSensorAssignmentModel,
                PushTokenModel.user_id == UserSensorAssignmentModel.user_id,
            )
            .where(
                UserSensorAssignmentModel.sensor_id == sensor_id,
                PushTokenModel.is_active.is_(True),
            )
        )
        return list(result.scalars().all())
