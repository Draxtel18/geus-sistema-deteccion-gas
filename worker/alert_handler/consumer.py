import asyncio
from datetime import datetime

import structlog

from worker.alert_handler.notifier import AlertNotifier
from worker.alert_handler.safety_logic import SafetyLogic
from worker.alert_handler.store import AlertStore
from worker.shared.database import worker_db
from worker.shared.messaging import WorkerMQTTClient, WorkerRabbitMQClient

logger = structlog.get_logger()


class AlertHandlerConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.mqtt = WorkerMQTTClient()
        self.safety_logic = SafetyLogic()
        self.notifier = AlertNotifier()
        self.alert_store = AlertStore()
        self.running = False

    async def start(self) -> None:
        logger.info("starting_alert_handler_consumer")

        await worker_db.connect()
        await self.rabbitmq.connect()
        await self.mqtt.connect()
        self.running = True

        await self._setup_alert_topology()

        await self.rabbitmq.consume_queue("alerts.critical", self.handle_critical_alert)
        await self.rabbitmq.consume_queue("alerts.warning", self.handle_warning_alert)

        logger.info("alert_handler_consumer_started")

        while self.running:
            await asyncio.sleep(1)

    async def _setup_alert_topology(self) -> None:
        import aio_pika

        if not self.rabbitmq.channel:
            raise RuntimeError("RabbitMQ channel not available")

        exchange = await self.rabbitmq.channel.declare_exchange(
            "gas.alerts", aio_pika.ExchangeType.TOPIC, durable=True
        )

        dlx_name = "gas.dlx"
        dlx = await self.rabbitmq.channel.declare_exchange(
            dlx_name, aio_pika.ExchangeType.DIRECT, durable=True
        )

        for queue_name, routing_key in [
            ("alerts.critical", "alert.critical.#"),
            ("alerts.warning", "alert.warning.#"),
        ]:
            dlq_name = f"{queue_name}.dlq"
            dlq = await self.rabbitmq.channel.declare_queue(dlq_name, durable=True)
            await dlq.bind(dlx, routing_key=queue_name)

            queue = await self.rabbitmq.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-dead-letter-exchange": dlx_name, "x-dead-letter-routing-key": queue_name},
            )
            await queue.bind(exchange, routing_key=routing_key)

        logger.info("alert_topology_configured")

    async def handle_critical_alert(self, data: dict) -> None:
        logger.info("handling_critical_alert", data=data)

        device_id = data.get("device_id")
        severity = data.get("severity")
        gas_level_ppm = data.get("gas_level_ppm")
        timestamp = data.get("timestamp")

        if not device_id or not severity or gas_level_ppm is None:
            logger.warning("invalid_alert_data", data=data)
            return

        saved = False
        try:
            await self.alert_store.ensure_sensor_exists(device_id)

            triggered_at = None
            if timestamp:
                try:
                    triggered_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    triggered_at = datetime.utcnow()
            else:
                triggered_at = datetime.utcnow()

            saved = await self.alert_store.save_alert(
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                triggered_at=triggered_at,
            )

            if not saved:
                logger.error("failed_to_save_critical_alert", device_id=device_id)
        except Exception as e:
            logger.critical(
                "db_down_alert_actions_executed_without_persistence",
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                error=str(e),
            )

        if not saved:
            logger.critical(
                "alert_not_saved_skipping_is_disabled",
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                reason="safety_actions_always_execute",
            )

        actions = self.safety_logic.determine_actions(device_id, severity, gas_level_ppm)

        if actions["should_close_valve"]:
            await self.send_valve_command(device_id, "close")
            await self.alert_store.update_valve_snapshot(device_id, "closed", "remote")

        if actions["should_activate_dissipator"]:
            await self.send_dissipator_command(device_id, "on")
            await self.alert_store.update_dissipator_snapshot(
                device_id=device_id,
                state="on",
                activation_mode="automatic",
                locked_by_alert=True,
            )

        emails, tokens = await self._resolve_notification_targets(device_id, severity)
        notification_data = await self._build_notification_data(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            event="alert",
        )
        await self.notifier.send_notification(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            recipients=emails,
            push_tokens=tokens,
            data=notification_data,
        )

        logger.info(
            "critical_alert_handled",
            device_id=device_id,
            saved_to_db=saved,
            valve_closed=actions["should_close_valve"],
            dissipator_activated=actions["should_activate_dissipator"],
        )

    async def handle_warning_alert(self, data: dict) -> None:
        logger.info("handling_warning_alert", data=data)

        device_id = data.get("device_id")
        severity = data.get("severity")
        gas_level_ppm = data.get("gas_level_ppm")
        timestamp = data.get("timestamp")

        if not device_id or not severity or gas_level_ppm is None:
            logger.warning("invalid_alert_data", data=data)
            return

        saved = False
        try:
            await self.alert_store.ensure_sensor_exists(device_id)

            triggered_at = None
            if timestamp:
                try:
                    triggered_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    triggered_at = datetime.utcnow()
            else:
                triggered_at = datetime.utcnow()

            saved = await self.alert_store.save_alert(
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                triggered_at=triggered_at,
            )

            if not saved:
                logger.error("failed_to_save_warning_alert", device_id=device_id)
        except Exception as e:
            logger.critical(
                "db_down_alert_actions_executed_without_persistence",
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                error=str(e),
            )

        if not saved:
            logger.critical(
                "alert_not_saved_skipping_is_disabled",
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
                reason="safety_actions_always_execute",
            )

        emails, tokens = await self._resolve_notification_targets(device_id, severity)
        notification_data = await self._build_notification_data(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            event="alert",
        )
        await self.notifier.send_notification(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            recipients=emails,
            push_tokens=tokens,
            data=notification_data,
        )

        logger.info("warning_alert_handled", device_id=device_id, saved_to_db=saved)

    async def _resolve_notification_targets(
        self, device_id: str, severity: str
    ) -> tuple[list[str], list[str]]:
        emails: list[str] = []
        tokens: list[str] = []

        try:
            emails, tokens = await self.alert_store.get_notification_targets(device_id)
        except Exception as e:
            logger.error(
                "failed_to_resolve_notification_targets",
                device_id=device_id,
                error=str(e),
            )

        if not emails:
            if severity == "critical":
                emails = ["admin@example.com"]
            else:
                emails = ["operator@example.com"]

        return list(set(emails)), list(set(tokens))

    async def _build_notification_data(
        self,
        device_id: str,
        severity: str,
        gas_level_ppm: float,
        event: str,
    ) -> dict:
        snapshot = await self.alert_store.get_sensor_snapshot(device_id) or {}
        sensor_id = snapshot.get("sensor_id")

        return {
            "event": event,
            "sensor_id": str(sensor_id) if sensor_id else None,
            "device_id": device_id,
            "severity": severity,
            "gas_level_ppm": gas_level_ppm,
            "location": snapshot.get("location"),
            "sensor_status": snapshot.get("sensor_status"),
            "mqtt_connected": snapshot.get("mqtt_connected"),
            "valve_state": snapshot.get("valve_state"),
            "dissipator_state": snapshot.get("dissipator_state"),
        }

    async def send_valve_command(self, device_id: str, command: str) -> None:
        topic = f"gas/command/{device_id}/valve"
        payload = {
            "command": command,
            "source": "remote",
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.mqtt.publish(topic, payload)

        logger.info(
            "valve_command_sent",
            device_id=device_id,
            command=command,
            topic=topic,
        )

    async def send_dissipator_command(self, device_id: str, state: str) -> None:
        topic = f"gas/command/{device_id}/dissipator"
        payload = {
            "state": state,
            "mode": "automatic",
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.mqtt.publish(topic, payload)

        logger.info(
            "dissipator_command_sent",
            device_id=device_id,
            state=state,
            topic=topic,
        )

    async def stop(self) -> None:
        logger.info("stopping_alert_handler_consumer")
        self.running = False
        await self.rabbitmq.close()
        await self.mqtt.close()
        await worker_db.close()
        logger.info("alert_handler_consumer_stopped")
