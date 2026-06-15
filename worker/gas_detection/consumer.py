import asyncio

import aio_pika
import structlog

from worker.alert_handler.notifier import AlertNotifier
from worker.alert_handler.store import AlertStore
from worker.data_collector.validator import ReadingValidator
from worker.gas_detection.processor import GasDetectionProcessor
from worker.gas_detection.publisher import AlertPublisher
from worker.shared.database import worker_db
from worker.shared.messaging import WorkerRabbitMQClient

logger = structlog.get_logger()


class GasDetectionConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.validator = ReadingValidator()
        self.processor = GasDetectionProcessor()
        self.publisher = AlertPublisher()
        self.notifier = AlertNotifier()
        self.alert_store = AlertStore()
        self.running = False

    async def start(self) -> None:
        logger.info("starting_gas_detection_consumer")

        await worker_db.connect()
        await self.rabbitmq.connect()
        await self.publisher.connect()
        self.running = True

        await self._setup_readings_topology()

        await self.rabbitmq.consume_queue("readings.analysis", self.process_reading)

        while self.running:
            await asyncio.sleep(1)

    async def _setup_readings_topology(self) -> None:
        if not self.rabbitmq.channel:
            raise RuntimeError("RabbitMQ channel not available")

        exchange = await self.rabbitmq.channel.declare_exchange(
            "gas.readings", aio_pika.ExchangeType.TOPIC, durable=True
        )

        dlx_name = "gas.dlx"
        dlx = await self.rabbitmq.channel.declare_exchange(
            dlx_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        dlq = await self.rabbitmq.channel.declare_queue(
            "readings.analysis.dlq", durable=True
        )
        await dlq.bind(dlx, routing_key="readings.analysis")

        analysis_queue = await self.rabbitmq.channel.declare_queue(
            "readings.analysis",
            durable=True,
            arguments={"x-dead-letter-exchange": dlx_name, "x-dead-letter-routing-key": "readings.analysis"},
        )
        await analysis_queue.bind(exchange, routing_key="sensor.reading.#")

        logger.info("readings_topology_configured")

    async def process_reading(self, data: dict) -> None:
        logger.debug("analyzing_gas_reading", data=data)

        is_valid, reading, error = self.validator.validate(data)

        if not is_valid:
            logger.warning("invalid_reading_for_analysis", error=error, data=data)
            return

        analysis = self.processor.analyze_reading(
            device_id=reading.device_id,
            gas_ppm=reading.gas_ppm,
            temperature_c=reading.temperature_c,
            humidity_percent=reading.humidity_percent,
        )

        if analysis["should_alert"]:
            await self.publisher.publish_alert(
                device_id=reading.device_id,
                severity=analysis["alert_severity"],
                gas_level_ppm=reading.gas_ppm,
                timestamp=reading.timestamp.isoformat(),
            )

            logger.info(
                "alert_triggered",
                device_id=reading.device_id,
                severity=analysis["alert_severity"],
                gas_ppm=reading.gas_ppm,
            )
        elif analysis["is_safe"]:
            resolved = await self.alert_store.resolve_active_alerts(reading.device_id)
            if resolved:
                emails, tokens = await self._resolve_notification_targets(reading.device_id)
                snapshot = await self.alert_store.get_sensor_snapshot(reading.device_id) or {}
                sensor_id = snapshot.get("sensor_id")
                await self.notifier.send_notification(
                    device_id=reading.device_id,
                    severity="resolved",
                    gas_level_ppm=reading.gas_ppm,
                    recipients=emails,
                    push_tokens=tokens,
                    data={
                        "event": "resolved",
                        "sensor_id": str(sensor_id) if sensor_id else None,
                        "device_id": reading.device_id,
                        "severity": "resolved",
                        "gas_level_ppm": reading.gas_ppm,
                        "location": snapshot.get("location"),
                        "sensor_status": snapshot.get("sensor_status"),
                        "mqtt_connected": snapshot.get("mqtt_connected"),
                        "valve_state": snapshot.get("valve_state"),
                        "dissipator_state": snapshot.get("dissipator_state"),
                    },
                )
                logger.info(
                    "alerts_auto_resolved_by_safe_reading",
                    device_id=reading.device_id,
                    gas_ppm=reading.gas_ppm,
                )

    async def _resolve_notification_targets(self, device_id: str) -> tuple[list[str], list[str]]:
        try:
            emails, tokens = await self.alert_store.get_notification_targets(device_id)
        except Exception as e:
            logger.error(
                "failed_to_resolve_safe_notification_targets",
                device_id=device_id,
                error=str(e),
            )
            emails, tokens = [], []

        if not emails:
            emails = ["operator@example.com"]

        return list(set(emails)), list(set(tokens))

    async def stop(self) -> None:
        logger.info("stopping_gas_detection_consumer")
        self.running = False
        await self.rabbitmq.close()
        await self.publisher.close()
        await worker_db.close()
        logger.info("gas_detection_consumer_stopped")
