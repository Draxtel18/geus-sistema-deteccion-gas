import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone, UTC
from typing import Any

import aiomqtt
import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class MQTTSettings(BaseSettings):
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_use_tls: bool = False
    mqtt_ca_cert_path: str | None = None
    mqtt_client_cert_path: str | None = None
    mqtt_client_key_path: str | None = None

    class Config:
        env_file = ".env"


settings = MQTTSettings()


class MQTTClientWrapper:
    def __init__(self) -> None:
        self.client: aiomqtt.Client | None = None
        self.subscriptions: dict[str, Callable[[str, dict[str, Any]], Awaitable[None]]] = {}

    async def connect(self, retries: int = 30, delay: int = 2) -> None:
        tls_params = None
        if settings.mqtt_use_tls and settings.mqtt_ca_cert_path:
            tls_params = aiomqtt.TLSParameters(
                ca_certs=settings.mqtt_ca_cert_path,
                certfile=settings.mqtt_client_cert_path,
                keyfile=settings.mqtt_client_key_path,
            )

        self.client = aiomqtt.Client(
            hostname=settings.mqtt_broker_host,
            port=settings.mqtt_broker_port,
            tls_params=tls_params,
        )

        for attempt in range(retries):
            try:
                logger.info(f"Conectando a Mosquitto MQTT en {settings.mqtt_broker_host}:{settings.mqtt_broker_port} (Intento {attempt + 1}/{retries})...")
                await self.client.__aenter__()
                logger.info("¡Conexión MQTT establecida con éxito!")
                return
            except Exception as e:
                logger.warning(f"Mosquitto no está listo ({e}). Reintentando en {delay}s...")
                if attempt == retries - 1:
                    logger.error("Se agotaron los reintentos para conectar a MQTT.")
                    raise
                await asyncio.sleep(delay)

    async def publish(self, topic: str, payload: dict[str, Any], qos: int = 1) -> None:
        if not self.client:
            raise RuntimeError("El cliente MQTT no esta conectado")

        await self.client.publish(
            topic, payload=json.dumps(payload).encode(), qos=qos, retain=False
        )

    async def subscribe(self, topic: str, callback: Callable[[str, dict[str, Any]], None]) -> None:
        if not self.client:
            raise RuntimeError("El cliente MQTT no esta conectado")

        await self.client.subscribe(topic)
        self.subscriptions[topic] = callback

    async def listen(self) -> None:
        if not self.client:
            raise RuntimeError("El cliente MQTT no está conectado")

        while True:  # El bucle de supervivencia
            logger.info("Iniciando bucle de escucha de mensajes MQTT...")
            try:
                async for message in self.client.messages:
                    topic = str(message.topic)
                    try:
                        payload = json.loads(message.payload.decode())
                    except json.JSONDecodeError:
                        logger.error(f"Payload MQTT malformado recibido en {topic}. Ignorando.")
                        continue

                    for subscribed_topic, callback in self.subscriptions.items():
                        if self._topic_matches(topic, subscribed_topic):
                            try:
                                await callback(topic, payload)
                            except Exception as e:
                                logger.error(
                                    f"Error ejecutando el callback para {topic}: {e}", exc_info=True
                                )

            except aiomqtt.MqttError as e:
                logger.error(f"El cliente MQTT se desconectó inesperadamente: {e}")
                logger.info("Iniciando protocolo de reconexión en 5 segundos...")
                await asyncio.sleep(5)
                # 1. Matamos limpiamente el contexto de la conexión caída
                try:
                    await self.client.__aexit__(None, None, None)
                except Exception:
                    pass

                # 2. Re-conectamos usando tu método connect() (que ya tiene sus propios reintentos)
                try:
                    await self.connect(retries=5, delay=5)

                    # 3. ¡Restauramos la memoria! Volvemos a suscribirnos a todos los tópicos
                    for topic in self.subscriptions.keys():
                        await self.client.subscribe(topic)
                        logger.info(f"Suscripción restaurada exitosamente para: {topic}")

                except Exception as reconn_error:
                    logger.error(f"Falló la reconexión automática: {reconn_error}")
                    # Si la reconexión falla, el 'while True' vuelve a atraparlo,
                    # espera otros 5 segundos y vuelve a intentar.

            except asyncio.CancelledError:
                # Esto permite que tu aplicación (o FastAPI/Uvicorn) se apague sin lanzar errores feos
                logger.info("Bucle de escucha MQTT detenido por el sistema de forma segura.")
                break
            except Exception as e:
                logger.critical(f"Error fatal no contemplado en el bucle MQTT: {e}", exc_info=True)
                await asyncio.sleep(5)  # Previene que un error desconocido sature el procesador

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        topic_parts = topic.split("/")
        pattern_parts = pattern.split("/")

        if len(topic_parts) != len(pattern_parts):
            if "#" not in pattern:
                return False

        for i, (t, p) in enumerate(zip(topic_parts, pattern_parts, strict=False)):
            if p == "#":
                return True
            if p == "+":
                continue
            if t != p:
                return False

        return True

    async def publish_valve_command(
        self, device_id: str, command: str, source: str = "remote"
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        await self.publish(
            f"gas/command/{device_id}/valve",
            {"command": command, "source": source, "timestamp": timestamp},
        )

    async def publish_dissipator_command(
        self, device_id: str, state: str, mode: str = "manual"
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        await self.publish(
            f"gas/command/{device_id}/dissipator",
            {"state": state, "mode": mode, "timestamp": timestamp},
        )

    async def close(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)


mqtt_client = MQTTClientWrapper()
