import asyncio
import json
from collections.abc import Callable
from typing import Any

import aio_pika
from aio_pika import ExchangeType
from pydantic_settings import BaseSettings
import structlog

logger = structlog.get_logger()

class RabbitMQSettings(BaseSettings):
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"

    class Config:
        env_file = ".env"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"


settings = RabbitMQSettings()


class RabbitMQClient:
    def __init__(self) -> None:
        self.connection: aio_pika.Connection | None = None
        self.channel: aio_pika.Channel | None = None
        self.exchanges: dict[str, aio_pika.Exchange] = {}
        self.queues: dict[str, aio_pika.Queue] = {}

    async def connect(self, retries: int = 30, delay: int = 2) -> None:
        for attempt in range(retries):
            try:
                logger.info(f"Conectando a RabbitMQ (Intento {attempt + 1}/{retries})...")
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)

                await self._setup_exchanges()
                await self._setup_queues()
                logger.info("¡Conexión a RabbitMQ establecida y topología configurada!")
                return
            except Exception as e:
                logger.warning(f"RabbitMQ no está disponible ({e}). Reintentando en {delay}s...")
                if attempt == retries - 1:
                    logger.error("Se agotaron los reintentos para conectar a RabbitMQ.")
                    raise
                await asyncio.sleep(delay)

    async def _setup_exchanges(self) -> None:
        self.exchanges["readings"] = await self.channel.declare_exchange(
            "gas.readings", ExchangeType.TOPIC, durable=True
        )
        self.exchanges["alerts"] = await self.channel.declare_exchange(
            "gas.alerts", ExchangeType.TOPIC, durable=True
        )
        self.exchanges["commands"] = await self.channel.declare_exchange(
            "gas.commands", ExchangeType.TOPIC, durable=True
        )

    async def _setup_queues(self) -> None:
        dlx_name = "gas.dlx"
        dlx = await self.channel.declare_exchange(dlx_name, ExchangeType.DIRECT, durable=True)

        queues_config = [
            ("readings.storage", "readings_storage", self.exchanges["readings"], "sensor.reading.#"),
            ("readings.analysis", "readings_analysis", self.exchanges["readings"], "sensor.reading.#"),
            ("alerts.critical", "alerts_critical", self.exchanges["alerts"], "alert.critical.#"),
            ("alerts.warning", "alerts_warning", self.exchanges["alerts"], "alert.warning.#"),
        ]

        for queue_name, key, exchange, routing_key in queues_config:
            dlq_name = f"{queue_name}.dlq"
            dlq = await self.channel.declare_queue(dlq_name, durable=True)
            await dlq.bind(dlx, routing_key=queue_name)

            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-dead-letter-exchange": dlx_name, "x-dead-letter-routing-key": queue_name},
            )
            await queue.bind(exchange, routing_key=routing_key)
            self.queues[key] = queue

    async def publish_reading(self, sensor_id: str, reading_data: dict[str, Any]) -> None:
        if not self.channel:
            raise RuntimeError("RabbitMQ not connected")

        message = aio_pika.Message(
            body=json.dumps(reading_data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.exchanges["readings"].publish(
            message, routing_key=f"sensor.reading.{sensor_id}"
        )

    async def publish_alert(
        self, sensor_id: str, severity: str, alert_data: dict[str, Any]
    ) -> None:
        if not self.channel:
            raise RuntimeError("RabbitMQ not connected")

        message = aio_pika.Message(
            body=json.dumps(alert_data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.exchanges["alerts"].publish(
            message, routing_key=f"alert.{severity}.{sensor_id}"
        )

    async def publish_command(
        self, sensor_id: str, command_type: str, command_data: dict[str, Any]
    ) -> None:
        if not self.channel:
            raise RuntimeError("RabbitMQ not connected")

        message = aio_pika.Message(
            body=json.dumps(command_data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await self.exchanges["commands"].publish(
            message, routing_key=f"command.{command_type}.{sensor_id}"
        )

    async def consume_queue(
        self, queue_name: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        if not self.channel:
            raise RuntimeError("RabbitMQ no esta conectado")

        queue = self.queues.get(queue_name)
        if not queue:
            raise ValueError(f"Cola {queue_name} no encontrada")

        async def message_handler(message: aio_pika.IncomingMessage) -> None:
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    await callback(data)
                except json.JSONDecodeError:
                    logger.error(f"Mensaje mal formado en la cola {queue_name}. Se descartará.")
                except Exception as e:
                    logger.error(f"Error procesando el mensaje en {queue_name: {e}}")
                    raise

        await queue.consume(message_handler)

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()


rabbitmq_client = RabbitMQClient()
