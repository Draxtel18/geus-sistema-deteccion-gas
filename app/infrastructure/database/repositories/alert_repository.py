from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alert.entities import Alert, AlertSeverity, AlertStatus
from app.domain.alert.repository import IAlertRepository
from app.infrastructure.database.models.alert import AlertModel


class AlertRepository(IAlertRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        result = await self.session.execute(
            select(AlertModel).where(AlertModel.id == alert_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_sensor(
        self, 
        sensor_id: UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Alert]:
        result = await self.session.execute(
            select(AlertModel)
            .where(AlertModel.sensor_id == sensor_id)
            .order_by(AlertModel.triggered_at.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_status(
        self, 
        status: AlertStatus, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Alert]:
        result = await self.session.execute(
            select(AlertModel)
            .where(AlertModel.status == status.value)
            .order_by(AlertModel.triggered_at.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_active_alerts(self, skip: int = 0, limit: int = 100) -> list[Alert]:
        result = await self.session.execute(
            select(AlertModel)
            .where(AlertModel.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]))
            .order_by(AlertModel.triggered_at.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_severity(
        self, 
        severity: AlertSeverity, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Alert]:
        result = await self.session.execute(
            select(AlertModel)
            .where(AlertModel.severity == severity.value)
            .order_by(AlertModel.triggered_at.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        sensor_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[Alert]:
        query = select(AlertModel).where(
            AlertModel.triggered_at >= start_date,
            AlertModel.triggered_at <= end_date
        )
        
        if sensor_id:
            query = query.where(AlertModel.sensor_id == sensor_id)
        
        query = query.order_by(AlertModel.triggered_at.desc()).offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def save(self, alert: Alert) -> Alert:
        model = self._to_model(alert)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, alert: Alert) -> Alert:
        result = await self.session.execute(
            select(AlertModel).where(AlertModel.id == alert.id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            model.gas_level_ppm = alert.gas_level_ppm
            model.severity = alert.severity.value
            model.status = alert.status.value
            model.acknowledged_at = alert.acknowledged_at
            model.acknowledged_by = alert.acknowledged_by
            model.resolved_at = alert.resolved_at
            model.resolved_by = alert.resolved_by
            model.auto_resolved = alert.auto_resolved
            model.notifications_sent = alert.notifications_sent
            
            await self.session.flush()
            await self.session.refresh(model)
            return self._to_entity(model)
        
        return alert

    async def get_active_alert_for_sensor(self, sensor_id: UUID) -> Alert | None:
        result = await self.session.execute(
            select(AlertModel)
            .where(
                AlertModel.sensor_id == sensor_id,
                AlertModel.status.in_([AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value])
            )
            .order_by(AlertModel.triggered_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _to_entity(self, model: AlertModel) -> Alert:
        return Alert(
            id=model.id,
            sensor_id=model.sensor_id,
            gas_level_ppm=model.gas_level_ppm,
            severity=AlertSeverity(model.severity),
            status=AlertStatus(model.status),
            triggered_at=model.triggered_at,
            acknowledged_at=model.acknowledged_at,
            acknowledged_by=model.acknowledged_by,
            resolved_at=model.resolved_at,
            resolved_by=model.resolved_by,
            auto_resolved=model.auto_resolved,
            notifications_sent=model.notifications_sent or [],
            created_at=model.created_at,
        )

    def _to_model(self, entity: Alert) -> AlertModel:
        return AlertModel(
            id=entity.id,
            sensor_id=entity.sensor_id,
            gas_level_ppm=entity.gas_level_ppm,
            severity=entity.severity.value,
            status=entity.status.value,
            triggered_at=entity.triggered_at,
            acknowledged_at=entity.acknowledged_at,
            acknowledged_by=entity.acknowledged_by,
            resolved_at=entity.resolved_at,
            resolved_by=entity.resolved_by,
            auto_resolved=entity.auto_resolved,
            notifications_sent=entity.notifications_sent,
            created_at=entity.created_at,
        )
