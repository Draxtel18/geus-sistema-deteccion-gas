import asyncio
import json
import ssl
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID

import aio_pika
import aiomqtt
import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class MessagingSettings(BaseSettings):
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_use_tls: bool = False
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_ca_cert_path: str | None = None
    mqtt_client_cert_path: str | None = None
    mqtt_client_key_path: str | None = None

    class Config:
        env_file = ".env"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"


settings = MessagingSettings()


class WorkerRabbitMQClient:
    def __init__(self) -> None:
        self.connection: aio_pika.Connection | None = None
        self.channel: aio_pika.Channel | None = None

    async def connect(self, retries: int = 30, delay: int = 5) -> None:
        for attempt in range(retries):
            try:
                logger.info(f"Worker conectando a RabbitMQ (Intento {attempt + 1}/{retries})...")
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)
                logger.info("¡Worker conectado a RabbitMQ con éxito!")
                return
            except Exception as e:
                logger.warning(f"RabbitMQ no está listo ({e}). Reintentando en {delay}s...")
                if attempt == retries - 1:
                    logger.error("El Worker no pudo conectar a RabbitMQ.")
                    raise
                await asyncio.sleep(delay)

    async def consume_queue(
        self, queue_name: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        if not self.channel:
            raise RuntimeError("RabbitMQ no está conectado")

        dlx_name = "gas.dlx"
        dlq_name = f"{queue_name}.dlq"
        dlx = await self.channel.declare_exchange(
            dlx_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        dlq = await self.channel.declare_queue(dlq_name, durable=True)
        await dlq.bind(dlx, routing_key=queue_name)

        queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": dlx_name, "x-dead-letter-routing-key": queue_name},
        )
        logger.info(f"Worker escuchando la cola RabbitMQ: {queue_name} (DLQ: {dlq_name})")

        async def message_handler(message: aio_pika.IncomingMessage) -> None:
            async with message.process(reject_on_redelivered=True):
                try:
                    data = json.loads(message.body.decode())
                    await callback(data)
                except json.JSONDecodeError:
                    logger.error(f"Mensaje mal formado en la cola {queue_name}. Se descartará.")
                except Exception as e:
                    logger.error(
                        f"Error en el worker procesando mensaje de {queue_name}: {e}", exc_info=True
                    )
                    raise  

        await queue.consume(message_handler)

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()


class WorkerMQTTClient:
    def __init__(self) -> None:
        self.client: aiomqtt.Client | None = None
        self.subscribed_topics: set[str] = set()

    async def connect(self, retries: int = 30, delay: int = 5) -> None:
        tls_context = None
        if settings.mqtt_use_tls:
            tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

            if settings.mqtt_ca_cert_path:
                tls_context.load_verify_locations(cafile=settings.mqtt_ca_cert_path)

            if settings.mqtt_client_cert_path and settings.mqtt_client_key_path:
                tls_context.load_cert_chain(
                    certfile=settings.mqtt_client_cert_path, keyfile=settings.mqtt_client_key_path
                )

            tls_context.verify_mode = ssl.CERT_REQUIRED
            tls_context.check_hostname = False

        client_kwargs: dict[str, Any] = {
            "hostname": settings.mqtt_broker_host,
            "port": settings.mqtt_broker_port,
            "tls_context": tls_context,
        }
        if settings.mqtt_username:
            client_kwargs["username"] = settings.mqtt_username
        if settings.mqtt_password:
            client_kwargs["password"] = settings.mqtt_password

        self.client = aiomqtt.Client(**client_kwargs)
        for attempt in range(retries):
            try:
                logger.info(
                    f"Worker conectando a Mosquitto MQTT (Intento {attempt + 1}/{retries})..."
                )
                await self.client.__aenter__()
                logger.info("¡Worker conectado a MQTT con éxito!")
                return
            except Exception as e:
                logger.warning(f"Mosquitto no está listo ({e}). Reintentando en {delay}s...")
                if attempt == retries - 1:
                    logger.error("El Worker no pudo conectar a Mosquitto.")
                    raise
                await asyncio.sleep(delay)

    async def subscribe(self, topic: str) -> None:
        if not self.client:
            raise RuntimeError("MQTT no está conectado")
        await self.client.subscribe(topic)
        self.subscribed_topics.add(topic)
        logger.info(f"Worker suscrito al tópico MQTT: {topic}")

    @staticmethod
    def _serialize_payload(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {k: WorkerMQTTClient._serialize_payload(v) for k, v in value.items()}
        if isinstance(value, list):
            return [WorkerMQTTClient._serialize_payload(item) for item in value]
        return value

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if not self.client:
            raise RuntimeError("MQTT no está conectado")
        serialized = self._serialize_payload(payload)
        await self.client.publish(topic, payload=json.dumps(serialized).encode(), qos=1)

    async def listen(self, callback: Callable[[str, dict[str, Any]], Awaitable[None]]) -> None:
        if not self.client:
            raise RuntimeError("MQTT no está conectado")

        while True:
            logger.info("Worker iniciando bucle de escucha MQTT...")
            try:
                async for message in self.client.messages:
                    topic = str(message.topic)
                    try:
                        payload = json.loads(message.payload.decode())
                        await callback(topic, payload)
                    except json.JSONDecodeError:
                        logger.error(f"Payload MQTT malformado recibido en {topic}. Ignorando.")
                    except Exception as e:
                        logger.error(
                            f"Error en el worker ejecutando el callback para {topic}: {e}",
                            exc_info=True,
                        )

            except aiomqtt.MqttError as e:
                logger.error(f"Worker desconectado de MQTT inesperadamente: {e}")
                logger.info("Worker iniciando protocolo de reconexión en 5 segundos...")
                await asyncio.sleep(5)

                try:
                    await self.client.__aexit__(None, None, None)
                except Exception:
                    pass

                try:
                    await self.connect(retries=5, delay=5)
                    for topic in self.subscribed_topics:
                        await self.client.subscribe(topic)
                        logger.info(f"Worker restauró la suscripción para: {topic}")
                except Exception as reconn_error:
                    logger.error(f"Worker falló en reconexión automática: {reconn_error}")

            except asyncio.CancelledError:
                logger.info("Bucle de escucha del Worker detenido de forma segura.")
                break
            except Exception as e:
                logger.critical(f"Error fatal no contemplado en el worker MQTT: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def close(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)
