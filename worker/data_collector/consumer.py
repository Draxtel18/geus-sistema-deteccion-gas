import asyncio
import json
from datetime import datetime

import aio_pika
import structlog
from pydantic import ValidationError

from worker.data_collector.storage import ReadingStorage
from worker.data_collector.validator import ReadingValidator
from worker.shared.database import worker_db
from worker.shared.messaging import WorkerMQTTClient, WorkerRabbitMQClient
from worker.shared.mqtt_schemas import MQTTReadingPayload, MQTTStatusPayload
from worker.shared.sensor_repository import WorkerSensorRepository

logger = structlog.get_logger()


class DataCollectorConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.mqtt = WorkerMQTTClient()
        self.validator = ReadingValidator()
        self.storage = ReadingStorage()
        self.sensor_repo = WorkerSensorRepository()
        self.running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        logger.info("starting_data_collector_consumer")

        await self.rabbitmq.connect()
        await self.mqtt.connect()
        await worker_db.connect()
        self.running = True

        await self.mqtt.subscribe("sensors/+/data")
        logger.info("subscribed_to_mqtt_topic_sensors_+/data")
        await self.mqtt.subscribe("sensors/+/status")
        logger.info("subscribed_to_mqtt_topic_sensors_+/status")

        self._tasks.append(asyncio.create_task(self.mqtt.listen(self.handle_mqtt_message)))

        logger.info("data_collector_consumer_started")

        while self.running:
            await asyncio.sleep(1)

    async def handle_mqtt_message(self, topic: str, payload: dict) -> None:
        logger.info("received_mqtt_message", topic=topic, sensor_id=payload.get("sensor_id"))

        if topic.endswith("/status"):
            try:
                validated = MQTTStatusPayload(**payload)
            except ValidationError as e:
                logger.warning(
                    "invalid_mqtt_status_payload",
                    topic=topic,
                    errors=e.errors(),
                    payload=payload,
                )
                return
            await self._handle_status_message(validated.model_dump())
            return

        try:
            validated = MQTTReadingPayload(**payload)
        except ValidationError as e:
            logger.warning(
                "invalid_mqtt_reading_payload",
                topic=topic,
                errors=e.errors(),
                payload=payload,
            )
            return

        try:
            transformed = self._transform_mqtt_to_reading(validated.model_dump())
        except Exception as e:
            logger.warning("failed_to_transform_mqtt_message", error=str(e), payload=payload)
            return

        is_valid, reading, error = self.validator.validate(transformed)
        if not is_valid:
            logger.warning("invalid_transformed_reading", error=error, transformed=transformed)
            return

        resolved_device_id = await self._resolve_device_id(reading.device_id)
        if resolved_device_id is None:
            logger.warning(
                "unregistered_sensor_reading_discarded",
                raw_device_id=reading.device_id,
                reason="sensor_not_found_in_postgres",
            )
            return

        success = await self.storage.store_reading(
            device_id=resolved_device_id,
            gas_ppm=reading.gas_ppm,
            temperature_c=reading.temperature_c,
            humidity_percent=reading.humidity_percent,
            wifi_signal=reading.wifi_signal,
            timestamp=reading.timestamp,
        )

        if success:
            logger.info(
                "reading_stored_successfully",
                device_id=resolved_device_id,
                raw_device_id=reading.device_id,
                gas_ppm=reading.gas_ppm,
            )
            try:
                sensor = await self.sensor_repo.find_by_device_id(resolved_device_id)
                timestamp = self._normalize_datetime(reading.timestamp)
                sensor_status = self._determine_sensor_status(
                    sensor.get("status") if sensor else None,
                    mqtt_connected=True,
                )
                await worker_db.execute(
                    """
                    UPDATE sensors
                    SET last_gas_ppm = $1,
                        last_reading_at = $2,
                        mqtt_connected = true,
                        status = $3,
                        wifi_signal = COALESCE($4, wifi_signal),
                        updated_at = $2
                    WHERE device_id = $5
                    """,
                    reading.gas_ppm,
                    timestamp,
                    sensor_status,
                    reading.wifi_signal,
                    resolved_device_id,
                )
                logger.info(
                    "sensor_last_gas_ppm_updated",
                    device_id=resolved_device_id,
                    last_gas_ppm=reading.gas_ppm,
                )
            except Exception as e:
                logger.error(
                    "failed_to_update_sensor_last_gas_ppm",
                    device_id=resolved_device_id,
                    error=str(e),
                )
        else:
            logger.error(
                "reading_storage_failed",
                device_id=resolved_device_id,
                raw_device_id=reading.device_id,
            )
            return

        transformed["device_id"] = resolved_device_id
        await self._publish_to_analysis_queue(transformed)

    async def _handle_status_message(self, payload: dict) -> None:
        device_id = payload.get("sensor_id", "")
        if not device_id:
            logger.warning("status_message_missing_sensor_id", payload=payload)
            return

        sensor = await self.sensor_repo.find_by_device_id(device_id)
        if not sensor:
            logger.warning("status_message_sensor_not_found", device_id=device_id)
            return

        sensor_id = sensor.get("id")
        if not sensor_id:
            logger.warning("status_message_sensor_no_uuid", device_id=device_id)
            return

        now = self._normalize_datetime()

        device_status = payload.get("device_status", {})
        metadata = payload.get("metadata", {})
        mqtt_status = payload.get("status", "offline")

        mqtt_connected = mqtt_status == "online"
        sensor_status = self._determine_sensor_status(sensor.get("status"), mqtt_connected)
        wifi_signal = metadata.get("wifi_rssi")
        uptime_seconds = metadata.get("uptime_seconds", 0)

        try:
            await worker_db.execute(
                """
                UPDATE sensors
                SET mqtt_connected = $1,
                    status = $2,
                    wifi_signal = $3,
                    uptime_seconds = $4,
                    updated_at = $5
                WHERE id = $6
                """,
                mqtt_connected,
                sensor_status,
                wifi_signal,
                uptime_seconds,
                now,
                sensor_id,
            )
        except Exception as e:
            logger.error("failed_to_update_sensor_status", device_id=device_id, error=str(e))
            return

        valve_open = device_status.get("valve_open")
        if valve_open is not None:
            new_valve_state = "open" if valve_open else "closed"
            try:
                await worker_db.execute(
                    """
                    UPDATE valves
                    SET state = $1,
                        last_state_change = $2,
                        updated_at = $2
                    WHERE sensor_id = $3
                    """,
                    new_valve_state,
                    now,
                    sensor_id,
                )
            except Exception as e:
                logger.error("failed_to_update_valve_status", device_id=device_id, error=str(e))

        dissipator_active = device_status.get("dissipator_active")
        if dissipator_active is not None:
            new_dissipator_state = "on" if dissipator_active else "off"
            try:
                await worker_db.execute(
                    """
                    UPDATE dissipators
                    SET state = $1,
                        last_state_change = $2,
                        updated_at = $2
                    WHERE sensor_id = $3
                    """,
                    new_dissipator_state,
                    now,
                    sensor_id,
                )
            except Exception as e:
                logger.error("failed_to_update_dissipator_status", device_id=device_id, error=str(e))

        logger.info(
            "sensor_status_synced",
            device_id=device_id,
            mqtt_connected=mqtt_connected,
            sensor_status=sensor_status,
            valve_open=valve_open,
            dissipator_active=dissipator_active,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None = None) -> datetime:
        timestamp = value or datetime.utcnow()
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        return timestamp

    @staticmethod
    def _determine_sensor_status(current_status: str | None, mqtt_connected: bool) -> str:
        if current_status == "maintenance":
            return current_status
        return "online" if mqtt_connected else "offline"

    def _transform_mqtt_to_reading(self, payload: dict) -> dict:
        sensor_id = payload.get("sensor_id", "")
        readings = payload.get("readings", {})
        metadata = payload.get("metadata", {})
        raw_timestamp = payload.get("timestamp")

        if raw_timestamp:
            try:
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        return {
            "device_id": sensor_id,
            "gas_ppm": float(readings.get("gas_concentration", 0)),
            "temperature_c": float(readings.get("temperature", 0)),
            "humidity_percent": float(readings.get("humidity", 0)),
            "wifi_signal": metadata.get("wifi_rssi"),
            "timestamp": timestamp.isoformat(),
        }

    async def _resolve_device_id(self, sensor_id: str) -> str | None:
        try:
            sensor = await self.sensor_repo.find_by_device_id(sensor_id)
            if sensor:
                return sensor["device_id"]

            candidates = await self.sensor_repo.find_by_suffix(sensor_id)
            if len(candidates) == 1:
                resolved = candidates[0]["device_id"]
                logger.warning(
                    "device_id_resolved_via_suffix",
                    raw_sensor_id=sensor_id,
                    resolved_device_id=resolved,
                )
                return resolved
            elif len(candidates) > 1:
                logger.warning(
                    "ambiguous_device_id_suffix_match",
                    raw_sensor_id=sensor_id,
                    matches=[c["device_id"] for c in candidates],
                )
                return None

            return None
        except Exception as e:
            logger.error("failed_to_resolve_device_id", sensor_id=sensor_id, error=str(e))
            return None

    async def _publish_to_analysis_queue(self, reading_data: dict) -> None:
        if not self.rabbitmq.channel:
            logger.error("rabbitmq_channel_not_available")
            return

        exchange = await self.rabbitmq.channel.declare_exchange(
            "gas.readings", aio_pika.ExchangeType.TOPIC, durable=True
        )

        message = aio_pika.Message(
            body=json.dumps(reading_data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        routing_key = f"sensor.reading.{reading_data['device_id']}"
        await exchange.publish(message, routing_key=routing_key)

        logger.info(
            "reading_published_to_analysis_queue",
            device_id=reading_data["device_id"],
            routing_key=routing_key,
        )

    async def process_reading(self, data: dict) -> None:
        logger.debug("processing_reading", data=data)

        is_valid, reading, error = self.validator.validate(data)

        if not is_valid:
            logger.warning("invalid_reading_skipped", error=error, data=data)
            return

        resolved_device_id = await self._resolve_device_id(reading.device_id)
        if resolved_device_id is None:
            logger.warning(
                "unregistered_sensor_reading_discarded",
                raw_device_id=reading.device_id,
                reason="sensor_not_found_in_postgres",
            )
            return

        success = await self.storage.store_reading(
            device_id=resolved_device_id,
            gas_ppm=reading.gas_ppm,
            temperature_c=reading.temperature_c,
            humidity_percent=reading.humidity_percent,
            wifi_signal=reading.wifi_signal,
            timestamp=reading.timestamp,
        )

        if success:
            logger.info(
                "reading_processed_successfully",
                device_id=resolved_device_id,
                raw_device_id=reading.device_id,
                gas_ppm=reading.gas_ppm,
            )
        else:
            logger.error(
                "reading_processing_failed",
                device_id=resolved_device_id,
                raw_device_id=reading.device_id,
            )

    async def stop(self) -> None:
        logger.info("stopping_data_collector_consumer")
        self.running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self.rabbitmq.close()
        await self.mqtt.close()
        await worker_db.close()
        self.storage.close()
        logger.info("data_collector_consumer_stopped")
