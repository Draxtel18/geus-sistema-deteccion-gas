from datetime import datetime
from typing import Any

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from pydantic_settings import BaseSettings


class InfluxDBSettings(BaseSettings):
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "influxdb_token"
    influxdb_org: str = "geus"
    influxdb_bucket: str = "sensor_readings"

    class Config:
        env_file = ".env"


settings = InfluxDBSettings()


class InfluxDBClientWrapper:
    def __init__(self) -> None:
        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        self.query_api = self.client.query_api()
        self.bucket = settings.influxdb_bucket
        self.org = settings.influxdb_org

    async def write_reading(
        self,
        sensor_id: str,
        gas_ppm: float,
        temperature_c: float,
        humidity_percent: float,
        wifi_signal: int | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        point = (
            Point("sensor_readings")
            .tag("sensor_id", sensor_id)
            .field("gas_ppm", gas_ppm)
            .field("temperature_c", temperature_c)
            .field("humidity_percent", humidity_percent)
        )

        if wifi_signal is not None:
            point = point.field("wifi_signal", wifi_signal)

        if timestamp:
            point = point.time(timestamp)

        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    async def query_latest_reading(self, sensor_id: str) -> dict[str, Any] | None:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "sensor_readings")
            |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
            |> last()
        '''

        result = self.query_api.query(org=self.org, query=query)

        if not result:
            return None

        reading: dict[str, Any] = {"sensor_id": sensor_id, "timestamp": None}

        for table in result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                reading[field] = value
                if reading["timestamp"] is None:
                    reading["timestamp"] = record.get_time()

        return reading

    async def query_readings_range(
        self,
        sensor_id: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start.isoformat()}Z, stop: {end.isoformat()}Z)
            |> filter(fn: (r) => r["_measurement"] == "sensor_readings")
            |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
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
                        "sensor_id": sensor_id,
                        "timestamp": record.get_time(),
                    }

                field = record.get_field()
                value = record.get_value()
                readings_map[timestamp][field] = value

        return list(readings_map.values())

    async def query_stats(
        self, sensor_id: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start.isoformat()}Z, stop: {end.isoformat()}Z)
            |> filter(fn: (r) => r["_measurement"] == "sensor_readings")
            |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
        '''

        stats: dict[str, Any] = {}

        for field in ["gas_ppm", "temperature_c", "humidity_percent"]:
            mean_query = query + f'''
                |> filter(fn: (r) => r["_field"] == "{field}")
                |> mean()
            '''
            mean_result = self.query_api.query(org=self.org, query=mean_query)
            if mean_result and mean_result[0].records:
                stats[f"{field}_mean"] = mean_result[0].records[0].get_value()

            max_query = query + f'''
                |> filter(fn: (r) => r["_field"] == "{field}")
                |> max()
            '''
            max_result = self.query_api.query(org=self.org, query=max_query)
            if max_result and max_result[0].records:
                stats[f"{field}_max"] = max_result[0].records[0].get_value()

            min_query = query + f'''
                |> filter(fn: (r) => r["_field"] == "{field}")
                |> min()
            '''
            min_result = self.query_api.query(org=self.org, query=min_query)
            if min_result and min_result[0].records:
                stats[f"{field}_min"] = min_result[0].records[0].get_value()

        return stats

    def close(self) -> None:
        self.client.close()


influx_client = InfluxDBClientWrapper()
