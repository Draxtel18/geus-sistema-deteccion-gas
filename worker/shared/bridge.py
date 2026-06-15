"""MQTT → RabbitMQ Bridge.

Subscribes to MQTT topics, validates payloads strictly with Pydantic,
and forwards them to RabbitMQ exchanges for downstream consumers.
"""

import asyncio
import json

import aio_pika
import structlog
from pydantic import ValidationError

from worker.shared.messaging import WorkerMQTTClient, WorkerRabbitMQClient
from worker.shared.mqtt_schemas import MQTTBridgeMessage, MQTTReadingPayload, MQTTStatusPayload

logger = structlog.get_logger()


class MQTTToRabbitMQBridge:
    """Bridge that fans-out validated MQTT messages into RabbitMQ exchanges."""

    def __init__(
        self,
        mqtt_client: WorkerMQTTClient | None = None,
        rabbitmq_client: WorkerRabbitMQClient | None = None,
    ) -> None:
        self.mqtt = mqtt_client or WorkerMQTTClient()
        self.rabbitmq = rabbitmq_client or WorkerRabbitMQClient()
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        logger.info("starting_mqtt_rabbitmq_bridge")
        await self.rabbitmq.connect()
        await self.mqtt.connect()
        self._running = True

        await self.mqtt.subscribe("sensors/+/data")
        await self.mqtt.subscribe("sensors/+/status")
        logger.info("bridge_subscribed_to_mqtt_topics")

        self._tasks.append(asyncio.create_task(self._mqtt_listen_loop()))
        logger.info("mqtt_rabbitmq_bridge_started")

        while self._running:
            await asyncio.sleep(1)

    async def _mqtt_listen_loop(self) -> None:
        async def _callback(topic: str, payload: dict) -> None:
            envelope = await self._validate_and_wrap(topic, payload)
            if envelope is None:
                return
            await self._publish_to_rabbitmq(envelope)

        await self.mqtt.listen(_callback)

    async def _validate_and_wrap(self, topic: str, payload: dict) -> MQTTBridgeMessage | None:
        if topic.endswith("/status"):
            try:
                MQTTStatusPayload(**payload)
            except ValidationError as e:
                logger.warning(
                    "bridge_invalid_status_payload",
                    topic=topic,
                    errors=e.errors(),
                    payload=payload,
                )
                return None
        elif topic.endswith("/data"):
            try:
                MQTTReadingPayload(**payload)
            except ValidationError as e:
                logger.warning(
                    "bridge_invalid_reading_payload",
                    topic=topic,
                    errors=e.errors(),
                    payload=payload,
                )
                return None
        else:
            logger.debug("bridge_unknown_topic", topic=topic)
            return None

        return MQTTBridgeMessage(topic=topic, payload=payload)

    async def _publish_to_rabbitmq(self, envelope: MQTTBridgeMessage) -> None:
        if not self.rabbitmq.channel:
            logger.error("bridge_rabbitmq_channel_not_available")
            return

        exchange_name = "gas.bridge"
        exchange = await self.rabbitmq.channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

        routing_key = envelope.topic.replace("/", ".")
        message = aio_pika.Message(
            body=json.dumps({
                "topic": envelope.topic,
                "payload": envelope.payload,
                "received_at": envelope.received_at.isoformat(),
            }).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await exchange.publish(message, routing_key=routing_key)
        logger.info(
            "bridge_published_to_rabbitmq",
            topic=envelope.topic,
            exchange=exchange_name,
            routing_key=routing_key,
        )

    async def stop(self) -> None:
        logger.info("stopping_mqtt_rabbitmq_bridge")
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self.mqtt.close()
        await self.rabbitmq.close()
        logger.info("mqtt_rabbitmq_bridge_stopped")
