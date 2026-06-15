"""Push notification service using Expo HTTP API."""

import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class ExpoSettings(BaseSettings):
    expo_access_token: str | None = None
    expo_enabled: bool = False

    class Config:
        env_file = ".env"


expo_settings = ExpoSettings()


class ExpoPushService:
    """Send push notifications via Expo Push API.

    Falls back to logging if expo-notifications is not installed or disabled.
    """

    _expo_api_url: str = "https://exp.host/--/api/v2/push/send"

    async def send_to_tokens(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict | None = None,
    ) -> dict[str, int]:
        if not expo_settings.expo_enabled or not tokens:
            logger.info(
                "push_notification_skipped",
                reason="expo_disabled_or_no_tokens",
                tokens_count=len(tokens),
            )
            return {"sent": 0, "failed": 0}

        try:
            import aiohttp
        except ImportError:
            logger.warning(
                "push_notification_skipped",
                reason="aiohttp_not_installed",
            )
            return {"sent": 0, "failed": 0}

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
                "data": data or {},
            }
            for token in tokens
        ]

        sent = 0
        failed = 0

        async with aiohttp.ClientSession() as session:
            for msg in messages:
                try:
                    async with session.post(
                        self._expo_api_url,
                        json=msg,
                        headers=headers,
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if result.get("data", {}).get("status") == "ok":
                                sent += 1
                                logger.info(
                                    "push_notification_sent",
                                    token=msg["to"][:8] + "...",
                                    title=title,
                                )
                            else:
                                failed += 1
                                logger.warning(
                                    "push_notification_rejected",
                                    token=msg["to"][:8] + "...",
                                    response=result,
                                )
                        else:
                            failed += 1
                            text = await resp.text()
                            logger.warning(
                                "push_notification_http_error",
                                status=resp.status,
                                body=text[:200],
                            )
                except Exception as e:
                    failed += 1
                    logger.error(
                        "push_notification_send_failed",
                        token=msg["to"][:8] + "...",
                        error=str(e),
                    )

        return {"sent": sent, "failed": failed}
