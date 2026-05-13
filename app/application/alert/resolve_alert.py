from uuid import UUID

import structlog

from app.domain.alert.repository import IAlertRepository
from app.domain.alert.services import AlertManager
from app.domain.shared.exceptions import AlertNotFoundError

logger = structlog.get_logger()


class ResolveAlert:
    def __init__(self, alert_repository: IAlertRepository) -> None:
        self.alert_repository = alert_repository
        self.alert_manager = AlertManager(alert_repository)

    async def execute(self, alert_id: UUID, user_id: UUID | None = None) -> dict:
        try:
            alert = await self.alert_manager.resolve_alert(alert_id, user_id, auto=False)

            return {
                "alert_id": str(alert.id),
                "sensor_id": str(alert.sensor_id),
                "status": alert.status.value,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "resolved_by": str(alert.resolved_by) if alert.resolved_by else None,
                "auto_resolved": alert.auto_resolved,
            }

        except ValueError as e:
            raise AlertNotFoundError(str(alert_id)) from e
