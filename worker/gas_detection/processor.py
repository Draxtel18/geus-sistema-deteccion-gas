from datetime import datetime

import structlog

logger = structlog.get_logger()


class GasDetectionProcessor:
    def __init__(
        self,
        warning_threshold: float = 200.0,
        critical_threshold: float = 500.0,
    ) -> None:
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def analyze_reading(
        self, device_id: str, gas_ppm: float, temperature_c: float, humidity_percent: float
    ) -> dict:
        safety_level = self._determine_safety_level(gas_ppm)
        should_alert = safety_level in ["warning", "critical"]
        should_close_valve = gas_ppm >= self.critical_threshold
        is_safe = safety_level == "safe"

        analysis = {
            "device_id": device_id,
            "gas_ppm": gas_ppm,
            "temperature_c": temperature_c,
            "humidity_percent": humidity_percent,
            "safety_level": safety_level,
            "should_alert": should_alert,
            "should_close_valve": should_close_valve,
            "is_safe": is_safe,
            "alert_severity": self._get_alert_severity(gas_ppm) if should_alert else None,
            "analyzed_at": datetime.utcnow(),
        }

        logger.info(
            "gas_reading_analyzed",
            device_id=device_id,
            gas_ppm=gas_ppm,
            safety_level=safety_level,
            should_alert=should_alert,
            should_close_valve=should_close_valve,
        )

        return analysis

    def _determine_safety_level(self, gas_ppm: float) -> str:
        if gas_ppm >= self.critical_threshold:
            return "critical"
        elif gas_ppm >= self.warning_threshold:
            return "warning"
        else:
            return "safe"

    def _get_alert_severity(self, gas_ppm: float) -> str:
        if gas_ppm >= self.critical_threshold:
            return "critical"
        elif gas_ppm >= self.warning_threshold:
            return "warning"
        else:
            return "safe"
