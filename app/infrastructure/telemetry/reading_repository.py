from datetime import datetime
from typing import Any

from influxdb_client import InfluxDBClient
from pydantic_settings import BaseSettings


class InfluxDBSettings(BaseSettings):
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "influxdb_token"
    influxdb_org: str = "geus"
    influxdb_bucket: str = "sensor_readings"

    class Config:
        env_file = ".env"


settings = InfluxDBSettings()


class ReadingRepository:
    def __init__(self) -> None:
        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.query_api = self.client.query_api()
        self.bucket = settings.influxdb_bucket
        self.org = settings.influxdb_org

    async def get_latest_reading(self, device_id: str) -> dict[str, Any] | None:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "sensor_readings")
            |> filter(fn: (r) => r["device_id"] == "{device_id}")
            |> last()
        '''

        result = self.query_api.query(org=self.org, query=query)

        if not result or not result[0].records:
            return None

        records = result[0].records
        reading: dict[str, Any] = {"device_id": device_id, "timestamp": None}

        for record in records:
            field = record.get_field()
            value = record.get_value()
            reading[field] = value
            if reading["timestamp"] is None:
                reading["timestamp"] = record.get_time()

        return reading

    async def get_readings_range(
        self,
        device_id: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start.isoformat()}Z, stop: {end.isoformat()}Z)
            |> filter(fn: (r) => r["_measurement"] == "sensor_readings")
            |> filter(fn: (r) => r["device_id"] == "{device_id}")
            |> limit(n: {limit})
        '''

        result = self.query_api.query(org=self.org, query=query)

        if not result:
            return []

        readings_map: dict[str, dict[str, Any]] = {}

        for table in result:
            for record in table.records:
                timestamp = record.get_time().isoformat()
                if timestamp not in readings_map:
                    readings_map[timestamp] = {
                        "device_id": device_id,
                        "timestamp": record.get_time(),
                    }

                field = record.get_field()
                value = record.get_value()
                readings_map[timestamp][field] = value

        return list(readings_map.values())

    def close(self) -> None:
        self.client.close()


reading_repository = ReadingRepository()
