from datetime import datetime

import structlog
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class InfluxDBSettings(BaseSettings):
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "influxdb_token"
    influxdb_org: str = "geus"
    influxdb_bucket: str = "sensor_readings"

    class Config:
        env_file = ".env"


settings = InfluxDBSettings()


class ReadingStorage:
    def __init__(self) -> None:
        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        self.bucket = settings.influxdb_bucket
        self.org = settings.influxdb_org

    async def store_reading(
        self,
        device_id: str,
        gas_ppm: float,
        temperature_c: float,
        humidity_percent: float,
        wifi_signal: int | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        try:
            point = (
                Point("sensor_readings")
                .tag("device_id", device_id)
                .field("gas_ppm", gas_ppm)
                .field("temperature_c", temperature_c)
                .field("humidity_percent", humidity_percent)
            )

            if wifi_signal is not None:
                point = point.field("wifi_signal", wifi_signal)

            if timestamp:
                point = point.time(timestamp)

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)

            logger.info(
                "reading_stored_influxdb",
                device_id=device_id,
                gas_ppm=gas_ppm,
                temperature_c=temperature_c,
            )

            return True

        except Exception as e:
            logger.error(
                "failed_to_store_reading",
                device_id=device_id,
                error=str(e),
            )
            return False

    def close(self) -> None:
        self.client.close()
