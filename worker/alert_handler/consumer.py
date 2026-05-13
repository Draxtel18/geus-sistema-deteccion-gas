import asyncio
from datetime import datetime

import structlog

from worker.alert_handler.notifier import AlertNotifier
from worker.alert_handler.safety_logic import SafetyLogic
from worker.shared.messaging import WorkerMQTTClient, WorkerRabbitMQClient

logger = structlog.get_logger()


class AlertHandlerConsumer:
    def __init__(self) -> None:
        self.rabbitmq = WorkerRabbitMQClient()
        self.mqtt = WorkerMQTTClient()
        self.safety_logic = SafetyLogic()
        self.notifier = AlertNotifier()
        self.running = False

    async def start(self) -> None:
        logger.info("starting_alert_handler_consumer")

        await self.rabbitmq.connect()
        await self.mqtt.connect()
        self.running = True

        await self.rabbitmq.consume_queue("alerts.critical", self.handle_critical_alert)
        await self.rabbitmq.consume_queue("alerts.warning", self.handle_warning_alert)

        logger.info("alert_handler_consumer_started")

        while self.running:
            await asyncio.sleep(1)

    async def handle_critical_alert(self, data: dict) -> None:
        logger.info("handling_critical_alert", data=data)

        device_id = data.get("device_id")
        severity = data.get("severity")
        gas_level_ppm = data.get("gas_level_ppm")

        if not device_id or not severity or gas_level_ppm is None:
            logger.warning("invalid_alert_data", data=data)
            return

        actions = self.safety_logic.determine_actions(device_id, severity, gas_level_ppm)

        if actions["should_close_valve"]:
            await self.send_valve_command(device_id, "close")

        if actions["should_activate_dissipator"]:
            await self.send_dissipator_command(device_id, "on")

        await self.notifier.send_notification(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            recipients=["admin@example.com"],
        )

        logger.info(
            "critical_alert_handled",
            device_id=device_id,
            valve_closed=actions["should_close_valve"],
            dissipator_activated=actions["should_activate_dissipator"],
        )

    async def handle_warning_alert(self, data: dict) -> None:
        logger.info("handling_warning_alert", data=data)

        device_id = data.get("device_id")
        severity = data.get("severity")
        gas_level_ppm = data.get("gas_level_ppm")

        if not device_id or not severity or gas_level_ppm is None:
            logger.warning("invalid_alert_data", data=data)
            return

        await self.notifier.send_notification(
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            recipients=["operator@example.com"],
        )

        logger.info("warning_alert_handled", device_id=device_id)

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
        logger.info("alert_handler_consumer_stopped")
