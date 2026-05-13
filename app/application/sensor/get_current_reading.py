from datetime import datetime
from uuid import UUID

import structlog

from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.exceptions import SensorNotFoundError
from app.infrastructure.telemetry.influx_client import influx_client

logger = structlog.get_logger()


class GetCurrentReading:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(self, sensor_id: UUID) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        latest_reading = await influx_client.query_latest_reading(sensor.device_id)

        if not latest_reading:
            return {
                "sensor_id": str(sensor_id),
                "device_id": sensor.device_id,
                "reading": None,
                "message": "No readings available",
                "timestamp": datetime.utcnow().isoformat(),
            }

        return {
            "sensor_id": str(sensor_id),
            "device_id": sensor.device_id,
            "reading": {
                "gas_ppm": latest_reading.get("gas_ppm"),
                "temperature_c": latest_reading.get("temperature_c"),
                "humidity_percent": latest_reading.get("humidity_percent"),
                "wifi_signal": latest_reading.get("wifi_signal"),
                "timestamp": latest_reading.get("timestamp").isoformat() if latest_reading.get("timestamp") else None,
            },
            "sensor_status": {
                "status": sensor.status.value,
                "mqtt_connected": sensor.mqtt_connected,
                "test_mode": sensor.test_mode,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
