from uuid import UUID

import structlog

from app.domain.alert.repository import IAlertRepository
from app.domain.alert.services import AlertManager
from app.domain.shared.exceptions import AlertNotFoundError

logger = structlog.get_logger()


class AcknowledgeAlert:
    def __init__(self, alert_repository: IAlertRepository) -> None:
        self.alert_repository = alert_repository
        self.alert_manager = AlertManager(alert_repository)

    async def execute(self, alert_id: UUID, user_id: UUID) -> dict:
        try:
            alert = await self.alert_manager.acknowledge_alert(alert_id, user_id)

            return {
                "alert_id": str(alert.id),
                "sensor_id": str(alert.sensor_id),
                "status": alert.status.value,
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "acknowledged_by": str(alert.acknowledged_by) if alert.acknowledged_by else None,
            }

        except ValueError as e:
            raise AlertNotFoundError(str(alert_id)) from e
