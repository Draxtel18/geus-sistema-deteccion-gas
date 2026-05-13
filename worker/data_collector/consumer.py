import asyncio

import structlog

from worker.data_collector.storage import ReadingStorage
from worker.data_collector.validator import ReadingValidator
from worker.shared.messaging import WorkerRabbitMQClient

logger = structlog.get_logger()


class DataCollectorConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.validator = ReadingValidator()
        self.storage = ReadingStorage()
        self.running = False

    async def start(self) -> None:
        logger.info("starting_data_collector_consumer")

        await self.rabbitmq.connect()
        self.running = True

        await self.rabbitmq.consume_queue("readings.storage", self.process_reading)

        logger.info("data_collector_consumer_started")

        while self.running:
            await asyncio.sleep(1)

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
        await self.rabbitmq.close()
        self.storage.close()
        logger.info("data_collector_consumer_stopped")
