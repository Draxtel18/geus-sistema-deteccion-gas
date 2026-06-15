from uuid import UUID

import structlog

from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.exceptions import SensorNotFoundError

logger = structlog.get_logger()


class GetLatestGasReading:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(self, sensor_id: UUID) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        if sensor.last_gas_ppm is None:
            return {
                "sensor_id": str(sensor_id),
                "device_id": sensor.device_id,
                "gas_ppm": 0,
                "timestamp": None,
                "status": "ESPERANDO DATOS...",
            }

        logger.info(
            "latest_gas_reading_retrieved",
            sensor_id=str(sensor_id),
            device_id=sensor.device_id,
            gas_ppm=sensor.last_gas_ppm,
        )

        return {
            "sensor_id": str(sensor_id),
            "device_id": sensor.device_id,
            "gas_ppm": sensor.last_gas_ppm,
            "timestamp": sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
            "status": "CONECTADO" if sensor.mqtt_connected else "SISTEMA DESCONECTADO",
        }
