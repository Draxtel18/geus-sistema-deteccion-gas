from datetime import datetime
from uuid import UUID

import structlog

from app.domain.alert.entities import AlertSeverity, AlertStatus
from app.domain.alert.repository import IAlertRepository

logger = structlog.get_logger()


class ListAlerts:
    def __init__(self, alert_repository: IAlertRepository) -> None:
        self.alert_repository = alert_repository

    async def execute(
        self,
        sensor_id: UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        if start_date and end_date:
            alerts = await self.alert_repository.list_by_date_range(
                start_date=start_date,
                end_date=end_date,
                sensor_id=sensor_id,
                skip=skip,
                limit=limit,
            )
        elif sensor_id:
            alerts = await self.alert_repository.list_by_sensor(
                sensor_id=sensor_id,
                skip=skip,
                limit=limit,
            )
        elif status:
            alert_status = AlertStatus(status)
            alerts = await self.alert_repository.list_by_status(
                status=alert_status,
                skip=skip,
                limit=limit,
            )
        elif severity:
            alert_severity = AlertSeverity(severity)
            alerts = await self.alert_repository.list_by_severity(
                severity=alert_severity,
                skip=skip,
                limit=limit,
            )
        else:
            alerts = await self.alert_repository.list_active_alerts(skip=skip, limit=limit)

        alert_list = [
            {
                "id": str(alert.id),
                "sensor_id": str(alert.sensor_id),
                "gas_level_ppm": alert.gas_level_ppm,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "triggered_at": alert.triggered_at.isoformat(),
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "auto_resolved": alert.auto_resolved,
            }
            for alert in alerts
        ]

        logger.info(
            "alerts_listed",
            count=len(alert_list),
            sensor_id=str(sensor_id) if sensor_id else None,
            status=status,
            severity=severity,
        )

        return {
            "alerts": alert_list,
            "count": len(alert_list),
            "skip": skip,
            "limit": limit,
            "filters": {
                "sensor_id": str(sensor_id) if sensor_id else None,
                "status": status,
                "severity": severity,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        }
