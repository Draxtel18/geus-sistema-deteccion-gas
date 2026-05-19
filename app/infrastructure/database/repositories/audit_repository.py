from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit.entities import ActionType, AuditLog
from app.domain.audit.repository import IAuditRepository
from app.infrastructure.database.models.audit import AuditLogModel


class AuditRepository(IAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, audit_log: AuditLog) -> AuditLog:
        model = self._to_model(audit_log)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def list_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.user_id == user_id)
            .order_by(AuditLogModel.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_action_type(
        self, action_type: ActionType, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.action == action_type.value)
            .order_by(AuditLogModel.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLogModel)
            .where(
                AuditLogModel.timestamp >= start_date,
                AuditLogModel.timestamp <= end_date,
            )
            .order_by(AuditLogModel.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLogModel)
            .order_by(AuditLogModel.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def count_by_action_type(self, action_type: ActionType) -> int:
        result = await self.session.execute(
            select(func.count(AuditLogModel.id)).where(
                AuditLogModel.action == action_type.value
            )
        )
        return result.scalar() or 0

    async def get_security_metrics(self, days: int = 7) -> dict:
        start_date = datetime.utcnow() - timedelta(days=days)

        total_result = await self.session.execute(
            select(func.count(AuditLogModel.id)).where(
                AuditLogModel.timestamp >= start_date
            )
        )
        total_actions = total_result.scalar() or 0

        login_result = await self.session.execute(
            select(func.count(AuditLogModel.id)).where(
                AuditLogModel.action == ActionType.USER_LOGIN.value,
                AuditLogModel.timestamp >= start_date,
            )
        )
        login_count = login_result.scalar() or 0

        alert_result = await self.session.execute(
            select(func.count(AuditLogModel.id)).where(
                AuditLogModel.action == ActionType.ALERT_CREATED.value,
                AuditLogModel.timestamp >= start_date,
            )
        )
        alert_count = alert_result.scalar() or 0

        panic_result = await self.session.execute(
            select(func.count(AuditLogModel.id)).where(
                AuditLogModel.action == ActionType.PANIC_BUTTON_PRESSED.value,
                AuditLogModel.timestamp >= start_date,
            )
        )
        panic_count = panic_result.scalar() or 0

        return {
            "period_days": days,
            "total_actions": total_actions,
            "login_count": login_count,
            "alert_count": alert_count,
            "panic_button_count": panic_count,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        }

    def _to_entity(self, model: AuditLogModel) -> AuditLog:
        return AuditLog(
            id=model.id,
            user_id=model.user_id,
            action_type=ActionType(model.action),
            resource_type=model.sensor_id if model.sensor_id else "system",
            resource_id=model.sensor_id,
            details=model.details or {},
            ip_address=str(model.ip_origin) if model.ip_origin else None,
            user_agent=None,
            timestamp=model.timestamp,
            created_at=model.created_at,
        )

    def _to_model(self, entity: AuditLog) -> AuditLogModel:
        return AuditLogModel(
            id=entity.id,
            user_id=entity.user_id,
            action=entity.action_type.value,
            sensor_id=entity.resource_id,
            details=entity.details,
            ip_origin=entity.ip_address,
            timestamp=entity.timestamp,
            created_at=entity.created_at,
        )
