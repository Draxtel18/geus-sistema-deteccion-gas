from uuid import UUID

import structlog

from app.domain.alert.entities import Alert, AlertStatus
from app.domain.alert.repository import IAlertRepository

logger = structlog.get_logger()


class AlertManager:
    def __init__(self, alert_repository: IAlertRepository) -> None:
        self.alert_repository = alert_repository

    async def acknowledge_alert(self, alert_id: UUID, user_id: UUID) -> Alert:
        alert = await self.alert_repository.get_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.acknowledge(user_id)
        updated_alert = await self.alert_repository.update(alert)

        logger.info(
            "alert_acknowledged",
            alert_id=str(alert_id),
            user_id=str(user_id),
            severity=alert.severity.value,
        )

        return updated_alert

    async def resolve_alert(
        self, alert_id: UUID, user_id: UUID | None = None, auto: bool = False
    ) -> Alert:
        alert = await self.alert_repository.get_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.resolve(user_id, auto)
        updated_alert = await self.alert_repository.update(alert)

        logger.info(
            "alert_resolved",
            alert_id=str(alert_id),
            user_id=str(user_id) if user_id else None,
            auto_resolved=auto,
            severity=alert.severity.value,
        )

        return updated_alert

    async def get_active_alerts_for_sensor(self, sensor_id: UUID) -> list[Alert]:
        return await self.alert_repository.list_by_sensor(sensor_id, skip=0, limit=100)

    async def should_auto_resolve(
        self, alert: Alert, current_gas_ppm: float
    ) -> bool:
        if alert.status not in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED):
            return False

        return current_gas_ppm < 200
