import structlog

from app.domain.sensor.repository import ISensorRepository

logger = structlog.get_logger()


class ListSensors:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(self, skip: int = 0, limit: int = 100, status_filter: str | None = None) -> dict:
        if status_filter:
            sensors = await self.sensor_repository.list_by_status(status_filter, skip, limit)
        else:
            sensors = await self.sensor_repository.list_all(skip, limit)

        sensor_list = [
            {
                "id": str(sensor.id),
                "device_id": sensor.device_id,
                "location": sensor.location.description,
                "status": sensor.status.value,
                "mqtt_connected": sensor.mqtt_connected,
                "wifi_signal": sensor.wifi_signal,
                "test_mode": sensor.test_mode,
                "last_reading_at": sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
            }
            for sensor in sensors
        ]

        logger.info(
            "sensors_listed",
            count=len(sensor_list),
            skip=skip,
            limit=limit,
            status_filter=status_filter,
        )

        return {
            "sensors": sensor_list,
            "count": len(sensor_list),
            "skip": skip,
            "limit": limit,
        }
