import json

import structlog
from aio_pika import DeliveryMode, ExchangeType, Message

from worker.shared.messaging import WorkerRabbitMQClient

logger = structlog.get_logger()


class AlertPublisher:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()

    async def connect(self) -> None:
        await self.rabbitmq.connect()

        if self.rabbitmq.channel:
            self.alerts_exchange = await self.rabbitmq.channel.declare_exchange(
                "gas.alerts", ExchangeType.TOPIC, durable=True
            )

    async def publish_alert(
        self, device_id: str, severity: str, gas_level_ppm: float, timestamp: str
    ) -> None:
        alert_data = {
            "device_id": device_id,
            "gas_level_ppm": gas_level_ppm,
            "severity": severity,
            "timestamp": timestamp,
        }

        message = Message(
            body=json.dumps(alert_data).encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        )

        routing_key = f"alert.{severity}.{device_id}"
        await self.alerts_exchange.publish(message, routing_key=routing_key)

        logger.info(
            "alert_published",
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            routing_key=routing_key,
        )

    async def close(self) -> None:
        await self.rabbitmq.close()
