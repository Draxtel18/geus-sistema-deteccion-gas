import asyncio

import structlog

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
        self.running = False

    async def start(self) -> None:
        logger.info("starting_gas_detection_consumer")

        await self.rabbitmq.connect()
        await self.publisher.connect()
        self.running = True

        await self.rabbitmq.consume_queue("readings.analysis", self.process_reading)

        logger.info("gas_detection_consumer_started")

        while self.running:
            await asyncio.sleep(1)

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

    async def stop(self) -> None:
        logger.info("stopping_gas_detection_consumer")
        self.running = False
        await self.rabbitmq.close()
        await self.publisher.close()
        logger.info("gas_detection_consumer_stopped")
