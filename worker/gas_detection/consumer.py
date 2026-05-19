import asyncio

import aio_pika
import structlog

from worker.alert_handler.store import AlertStore
from worker.data_collector.validator import ReadingValidator
from worker.gas_detection.processor import GasDetectionProcessor
from worker.gas_detection.publisher import AlertPublisher
from worker.shared.messaging import WorkerRabbitMQClient

logger = structlog.get_logger()


class GasDetectionConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.validator = ReadingValidator()
        self.processor = GasDetectionProcessor()
        self.publisher = AlertPublisher()
        self.alert_store = AlertStore()
        self.running = False

    async def start(self) -> None:
        logger.info("starting_gas_detection_consumer")

        await self.rabbitmq.connect()
        await self.publisher.connect()
        self.running = True

        # Configurar topologia: declarar exchange y ligar cola de analisis
        await self._setup_readings_topology()

        await self.rabbitmq.consume_queue("readings.analysis", self.process_reading)

        logger.info("gas_detection_consumer_started")

        while self.running:
            await asyncio.sleep(1)

    async def _setup_readings_topology(self) -> None:
        """Declarar exchange gas.readings y ligar cola readings.analysis."""
        if not self.rabbitmq.channel:
            raise RuntimeError("RabbitMQ channel not available")

        exchange = await self.rabbitmq.channel.declare_exchange(
            "gas.readings", aio_pika.ExchangeType.TOPIC, durable=True
        )

        analysis_queue = await self.rabbitmq.channel.declare_queue(
            "readings.analysis", durable=True
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
            # Gas volvió a niveles seguros: intentar auto-resolver alertas activas
            resolved = await self.alert_store.resolve_active_alerts(reading.device_id)
            if resolved:
                logger.info(
                    "alerts_auto_resolved_by_safe_reading",
                    device_id=reading.device_id,
                    gas_ppm=reading.gas_ppm,
                )

    async def stop(self) -> None:
        logger.info("stopping_gas_detection_consumer")
        self.running = False
        await self.rabbitmq.close()
        await self.publisher.close()
        logger.info("gas_detection_consumer_stopped")
