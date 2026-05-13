from datetime import datetime, timedelta
from uuid import UUID

import structlog

from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.exceptions import SensorNotFoundError
from app.infrastructure.telemetry.influx_client import influx_client

logger = structlog.get_logger()


class GetSensorStats:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(self, sensor_id: UUID, period: str = "24h") -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        end = datetime.utcnow()
        start = self._calculate_start_time(end, period)

        stats = await influx_client.query_stats(
            sensor_id=sensor.device_id,
            start=start,
            end=end,
        )

        logger.info(
            "sensor_stats_retrieved",
            sensor_id=str(sensor_id),
            device_id=sensor.device_id,
            period=period,
        )

        return {
            "sensor_id": str(sensor_id),
            "device_id": sensor.device_id,
            "period": period,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "statistics": {
                "gas_ppm": {
                    "mean": stats.get("gas_ppm_mean"),
                    "max": stats.get("gas_ppm_max"),
                    "min": stats.get("gas_ppm_min"),
                },
                "temperature_c": {
                    "mean": stats.get("temperature_c_mean"),
                    "max": stats.get("temperature_c_max"),
                    "min": stats.get("temperature_c_min"),
                },
                "humidity_percent": {
                    "mean": stats.get("humidity_percent_mean"),
                    "max": stats.get("humidity_percent_max"),
                    "min": stats.get("humidity_percent_min"),
                },
            },
        }

    def _calculate_start_time(self, end: datetime, period: str) -> datetime:
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "1y": timedelta(days=365),
        }

        delta = period_map.get(period, timedelta(hours=24))
        return end - delta
