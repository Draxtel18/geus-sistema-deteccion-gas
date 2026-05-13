from datetime import datetime, timedelta
from uuid import UUID

import structlog

from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.exceptions import SensorNotFoundError
from app.infrastructure.telemetry.reading_repository import reading_repository

logger = structlog.get_logger()


class GetReadingsHistory:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(
        self,
        sensor_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        if not end:
            end = datetime.utcnow()

        if not start:
            start = end - timedelta(hours=24)

        readings = await reading_repository.get_readings_range(
            device_id=sensor.device_id,
            start=start,
            end=end,
            limit=limit,
        )

        formatted_readings = [
            {
                "gas_ppm": reading.get("gas_ppm"),
                "temperature_c": reading.get("temperature_c"),
                "humidity_percent": reading.get("humidity_percent"),
                "wifi_signal": reading.get("wifi_signal"),
                "timestamp": reading.get("timestamp").isoformat() if reading.get("timestamp") else None,
            }
            for reading in readings
        ]

        logger.info(
            "readings_history_retrieved",
            sensor_id=str(sensor_id),
            device_id=sensor.device_id,
            count=len(formatted_readings),
            start=start.isoformat(),
            end=end.isoformat(),
        )

        return {
            "sensor_id": str(sensor_id),
            "device_id": sensor.device_id,
            "readings": formatted_readings,
            "count": len(formatted_readings),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": limit,
        }
