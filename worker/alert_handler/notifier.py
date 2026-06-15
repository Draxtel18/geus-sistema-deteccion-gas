import asyncio
from datetime import datetime, timedelta

import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class SMTPSettings(BaseSettings):
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@geus.example.com"
    smtp_enabled: bool = False

    class Config:
        env_file = ".env"


smtp_settings = SMTPSettings()


class ExpoSettings(BaseSettings):
    expo_access_token: str | None = None
    expo_enabled: bool = False

    class Config:
        env_file = ".env"


expo_settings = ExpoSettings()


class AlertNotifier:
    _last_sent: dict[tuple[str, str], datetime] = {}
    _cooldown_seconds: int = 300

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self._cooldown_seconds = cooldown_seconds

    async def send_notification(
        self,
        device_id: str,
        severity: str,
        gas_level_ppm: float,
        recipients: list[str],
        push_tokens: list[str] | None = None,
        title: str | None = None,
        body: str | None = None,
        data: dict | None = None,
    ) -> bool:
        key = (device_id, severity)
        now = datetime.utcnow()
        last = self._last_sent.get(key)

        payload = dict(data or {})
        payload.setdefault("device_id", device_id)
        payload.setdefault("severity", severity)
        payload.setdefault("gas_level_ppm", gas_level_ppm)

        notification_title = title or self._build_title(device_id, severity)
        notification_body = body or self._build_body(severity, gas_level_ppm)

        if last and (now - last) < timedelta(seconds=self._cooldown_seconds):
            logger.info(
                "notification_rate_limited",
                device_id=device_id,
                severity=severity,
                last_sent=last.isoformat(),
                cooldown_seconds=self._cooldown_seconds,
            )
            return True

        logger.info(
            "sending_alert_notification",
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            recipients=recipients,
            push_tokens_count=len(push_tokens or []),
            title=notification_title,
        )

        try:
            email_tasks = [
                self._send_email(
                    to=recipient,
                    subject=notification_title,
                    body=self._build_email_body(
                        device_id=device_id,
                        severity=severity,
                        gas_level_ppm=gas_level_ppm,
                        timestamp=now,
                        body=notification_body,
                        data=payload,
                    ),
                )
                for recipient in recipients
            ]
            await asyncio.gather(*email_tasks, return_exceptions=True)

            if push_tokens:
                await self._send_push(
                    tokens=push_tokens,
                    title=notification_title,
                    body=notification_body,
                    data=payload,
                )

            self._last_sent[key] = now
            return True

        except Exception as e:
            logger.error(
                "notification_failed",
                device_id=device_id,
                error=str(e),
            )
            return False

    @staticmethod
    def _build_title(device_id: str, severity: str) -> str:
        if severity == "resolved":
            return f"Sensor {device_id} en estado seguro"
        return f"Alerta {severity.upper()} - Sensor {device_id}"

    @staticmethod
    def _build_body(severity: str, gas_level_ppm: float) -> str:
        if severity == "resolved":
            return f"Nivel actual: {gas_level_ppm} ppm. El sistema volvió a un umbral seguro."
        return f"Nivel de gas: {gas_level_ppm} ppm"

    @staticmethod
    def _build_email_body(
        device_id: str,
        severity: str,
        gas_level_ppm: float,
        timestamp: datetime,
        body: str,
        data: dict,
    ) -> str:
        lines = [
            body,
            "",
            f"Sensor: {device_id}",
            f"Severidad: {severity.upper()}",
            f"Nivel de gas: {gas_level_ppm} ppm",
        ]

        if data.get("event"):
            lines.append(f"Evento: {data['event']}")
        if data.get("sensor_status"):
            lines.append(f"Estado del sensor: {data['sensor_status']}")
        if data.get("mqtt_connected") is not None:
            lines.append(f"MQTT conectado: {data['mqtt_connected']}")
        if data.get("valve_state"):
            lines.append(f"Válvula: {data['valve_state']}")
        if data.get("dissipator_state"):
            lines.append(f"Disipador: {data['dissipator_state']}")

        lines.append(f"Hora: {timestamp.isoformat()}")
        return "\n".join(lines)

    async def _send_email(self, to: str, subject: str, body: str) -> None:
        if not smtp_settings.smtp_enabled:
            logger.info(
                "notification_email_simulated",
                to=to,
                subject=subject,
                reason="smtp_not_enabled",
            )
            return

        try:
            import aiosmtplib
        except ImportError:
            logger.warning(
                "notification_email_skipped",
                to=to,
                reason="aiosmtplib_not_installed",
            )
            return

        try:
            await aiosmtplib.send(
                message=f"Subject: {subject}\n\n{body}",
                sender=smtp_settings.smtp_from_email,
                recipients=[to],
                hostname=smtp_settings.smtp_host,
                port=smtp_settings.smtp_port,
                username=smtp_settings.smtp_user if smtp_settings.smtp_user else None,
                password=smtp_settings.smtp_password if smtp_settings.smtp_password else None,
                start_tls=True,
            )
            logger.info(
                "notification_email_sent",
                to=to,
                subject=subject,
            )
        except Exception as e:
            logger.error(
                "notification_email_failed",
                to=to,
                error=str(e),
            )
            raise

    async def _send_push(
        self, tokens: list[str], title: str, body: str, data: dict
    ) -> None:
        if not expo_settings.expo_enabled or not tokens:
            logger.info(
                "push_notification_skipped",
                reason="expo_disabled_or_no_tokens",
            )
            return

        try:
            import aiohttp
        except ImportError:
            logger.warning(
                "push_notification_skipped",
                reason="aiohttp_not_installed",
            )
            return

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        if expo_settings.expo_access_token:
            headers["Authorization"] = f"Bearer {expo_settings.expo_access_token}"

        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "sound": "default",
                "priority": "high",
                "data": data,
            }
            for token in tokens
        ]

        async with aiohttp.ClientSession() as session:
            for msg in messages:
                try:
                    async with session.post(
                        "https://exp.host/--/api/v2/push/send",
                        json=msg,
                        headers=headers,
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if result.get("data", {}).get("status") == "ok":
                                logger.info(
                                    "push_notification_sent",
                                    token=msg["to"][:8] + "...",
                                    title=title,
                                )
                            else:
                                logger.warning(
                                    "push_notification_rejected",
                                    token=msg["to"][:8] + "...",
                                    response=result,
                                )
                        else:
                            text = await resp.text()
                            logger.warning(
                                "push_notification_http_error",
                                status=resp.status,
                                body=text[:200],
                            )
                except Exception as e:
                    logger.error(
                        "push_notification_send_failed",
                        token=msg["to"][:8] + "...",
                        error=str(e),
                    )
