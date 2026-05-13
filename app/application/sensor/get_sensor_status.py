from datetime import datetime
from uuid import UUID

import structlog

from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.exceptions import SensorNotFoundError
from app.infrastructure.telemetry.influx_client import influx_client

logger = structlog.get_logger()


class GetSensorStatus:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(self, sensor_id: UUID) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        valve = await self.sensor_repository.get_valve_by_sensor_id(sensor_id)
        dissipator = await self.sensor_repository.get_dissipator_by_sensor_id(sensor_id)

        latest_reading = await influx_client.query_latest_reading(sensor.device_id)

        status = {
            "sensor": {
                "id": str(sensor.id),
                "device_id": sensor.device_id,
                "location": sensor.location.description,
                "status": sensor.status.value,
                "mqtt_connected": sensor.mqtt_connected,
                "wifi_signal": sensor.wifi_signal,
                "test_mode": sensor.test_mode,
                "last_reading_at": sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
            },
            "valve": None,
            "dissipator": None,
            "latest_reading": latest_reading,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if valve:
            status["valve"] = {
                "id": str(valve.id),
                "state": valve.state.value,
                "last_state_change": valve.last_state_change.isoformat(),
                "mechanical_status": valve.mechanical_status.value,
            }

        if dissipator:
            status["dissipator"] = {
                "id": str(dissipator.id),
                "state": dissipator.state.value,
                "activation_mode": dissipator.activation_mode.value,
                "locked_by_alert": dissipator.locked_by_alert,
                "last_state_change": dissipator.last_state_change.isoformat(),
            }

        logger.info(
            "sensor_status_retrieved",
            sensor_id=str(sensor_id),
            device_id=sensor.device_id,
        )

        return status
