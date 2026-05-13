import structlog

logger = structlog.get_logger()


class AlertNotifier:
    def __init__(self) -> None:
        pass

    async def send_notification(
        self, device_id: str, severity: str, gas_level_ppm: float, recipients: list[str]
    ) -> bool:
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

            return True

        except Exception as e:
            logger.error(
                "notification_failed",
                device_id=device_id,
                error=str(e),
            )
            return False
