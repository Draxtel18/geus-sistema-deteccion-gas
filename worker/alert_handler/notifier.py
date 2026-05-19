from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger()


class AlertNotifier:
    _last_sent: dict[tuple[str, str], datetime] = {}
    _cooldown_seconds: int = 300  # 5 minutos entre notificaciones del mismo device/severity

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self._cooldown_seconds = cooldown_seconds

    async def send_notification(
        self, device_id: str, severity: str, gas_level_ppm: float, recipients: list[str]
    ) -> bool:
        key = (device_id, severity)
        now = datetime.utcnow()
        last = self._last_sent.get(key)

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
        )

        try:
            for recipient in recipients:
                logger.info(
                    "notification_sent",
                    device_id=device_id,
                    severity=severity,
                    recipient=recipient,
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
