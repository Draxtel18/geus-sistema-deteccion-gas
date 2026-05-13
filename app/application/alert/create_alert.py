from datetime import datetime
from uuid import UUID, uuid4

import structlog

from app.domain.alert.entities import Alert, AlertSeverity, AlertStatus
from app.domain.alert.repository import IAlertRepository
from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.events import AlertCreatedEvent
from app.domain.shared.exceptions import SensorNotFoundError

logger = structlog.get_logger()


class CreateAlert:
    def __init__(
        self,
        alert_repository: IAlertRepository,
        sensor_repository: ISensorRepository,
    ) -> None:
        self.alert_repository = alert_repository
        self.sensor_repository = sensor_repository

    async def execute(
        self,
        sensor_id: UUID,
        gas_level_ppm: float,
        severity: str,
        timestamp: datetime | None = None,
    ) -> Alert:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        existing_alert = await self.alert_repository.get_active_alert_for_sensor(sensor_id)
        if existing_alert:
            logger.info(
                "active_alert_already_exists",
                sensor_id=str(sensor_id),
                existing_alert_id=str(existing_alert.id),
                severity=severity,
            )
            return existing_alert

        alert_severity = AlertSeverity.CRITICAL if severity == "critical" else AlertSeverity.WARNING
        triggered_at = timestamp or datetime.utcnow()

        alert = Alert(
            id=uuid4(),
            sensor_id=sensor_id,
            gas_level_ppm=gas_level_ppm,
            severity=alert_severity,
            status=AlertStatus.ACTIVE,
            triggered_at=triggered_at,
        )

        saved_alert = await self.alert_repository.save(alert)

        event = AlertCreatedEvent(
            alert_id=saved_alert.id,
            sensor_id=sensor_id,
            gas_level_ppm=gas_level_ppm,
            severity=severity,
        )
        event.aggregate_id = sensor_id

        logger.info(
            "alert_created",
            alert_id=str(saved_alert.id),
            sensor_id=str(sensor_id),
            severity=severity,
            gas_level_ppm=gas_level_ppm,
        )

        return saved_alert

    async def should_create_alert(
        self, sensor_id: UUID, gas_ppm: float, test_mode: bool = False
    ) -> tuple[bool, str | None]:
        if test_mode:
            return False, None

        existing_alert = await self.alert_repository.get_active_alert_for_sensor(sensor_id)
        if existing_alert:
            return False, None

        if gas_ppm >= 500:
            return True, "critical"
        elif gas_ppm >= 200:
            return True, "warning"
        else:
            return False, None
