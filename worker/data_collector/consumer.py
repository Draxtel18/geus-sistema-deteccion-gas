import asyncio
import json
from datetime import UTC, datetime

import aio_pika
import structlog

from worker.data_collector.storage import ReadingStorage
from worker.data_collector.validator import ReadingValidator
from worker.shared.messaging import WorkerMQTTClient, WorkerRabbitMQClient

logger = structlog.get_logger()


class DataCollectorConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.mqtt = WorkerMQTTClient()
        self.validator = ReadingValidator()
        self.storage = ReadingStorage()
        self.running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        logger.info("starting_data_collector_consumer")

        await self.rabbitmq.connect()
        await self.mqtt.connect()
        self.running = True

        # Escuchar directamente desde MQTT (simulador/ESP32 publica aqui)
        await self.mqtt.subscribe("sensors/+/data")
        logger.info("subscribed_to_mqtt_topic_sensors_+/data")

        # Iniciar el bucle de escucha MQTT en background
        self._tasks.append(asyncio.create_task(self.mqtt.listen(self.handle_mqtt_message)))

        # Tambien mantener consumo de RabbitMQ para compatibilidad
        self._tasks.append(asyncio.create_task(
            self.rabbitmq.consume_queue("readings.storage", self.process_reading)
        ))

        logger.info("data_collector_consumer_started")

        while self.running:
            await asyncio.sleep(1)

    async def handle_mqtt_message(self, topic: str, payload: dict) -> None:
        """Procesar mensaje MQTT del simulador/ESP32 y encolar en RabbitMQ."""
        logger.info("received_mqtt_message", topic=topic, sensor_id=payload.get("sensor_id"))

        # Transformar mensaje del simulador al formato SensorReadingSchema
        try:
            transformed = self._transform_mqtt_to_reading(payload)
        except Exception as e:
            logger.warning("failed_to_transform_mqtt_message", error=str(e), payload=payload)
            return

        # Validar
        is_valid, reading, error = self.validator.validate(transformed)
        if not is_valid:
            logger.warning("invalid_transformed_reading", error=error, transformed=transformed)
            return

        # Almacenar en InfluxDB
        success = await self.storage.store_reading(
            device_id=reading.device_id,
            gas_ppm=reading.gas_ppm,
            temperature_c=reading.temperature_c,
            humidity_percent=reading.humidity_percent,
            wifi_signal=reading.wifi_signal,
            timestamp=reading.timestamp,
        )

        if success:
            logger.info(
                "reading_stored_successfully",
                device_id=reading.device_id,
                gas_ppm=reading.gas_ppm,
            )
        else:
            logger.error("reading_storage_failed", device_id=reading.device_id)
            return

        # Publicar a RabbitMQ para que GasDetectionWorker lo procese
        await self._publish_to_analysis_queue(transformed)

    def _transform_mqtt_to_reading(self, payload: dict) -> dict:
        """Transformar mensaje MQTT del simulador a formato SensorReadingSchema."""
        sensor_id = payload.get("sensor_id", "")
        readings = payload.get("readings", {})
        metadata = payload.get("metadata", {})
        raw_timestamp = payload.get("timestamp")

        # Parsear timestamp
        if raw_timestamp:
            try:
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)

        return {
            "device_id": sensor_id,
            "gas_ppm": float(readings.get("gas_concentration", 0)),
            "temperature_c": float(readings.get("temperature", 0)),
            "humidity_percent": float(readings.get("humidity", 0)),
            "wifi_signal": metadata.get("wifi_rssi"),
            "timestamp": timestamp.isoformat(),
        }

    async def _publish_to_analysis_queue(self, reading_data: dict) -> None:
        """Publicar lectura a RabbitMQ para analisis de GasDetectionWorker."""
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

        success = await self.storage.store_reading(
            device_id=reading.device_id,
            gas_ppm=reading.gas_ppm,
            temperature_c=reading.temperature_c,
            humidity_percent=reading.humidity_percent,
            wifi_signal=reading.wifi_signal,
            timestamp=reading.timestamp,
        )

        if success:
            logger.info(
                "reading_processed_successfully",
                device_id=reading.device_id,
                gas_ppm=reading.gas_ppm,
            )
        else:
            logger.error(
                "reading_processing_failed",
                device_id=reading.device_id,
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
        self.storage.close()
        logger.info("data_collector_consumer_stopped")
