from datetime import datetime, timedelta
from typing import Any

from app.domain.safety.entities import SafetyLevel, SafetyProtocol, SafetyThresholds
from app.domain.shared.value_objects import GasLevel


class GasLevelAnalyzer:
    def __init__(self, protocol: SafetyProtocol) -> None:
        self.protocol = protocol

    def analyze_reading(
        self,
        gas_ppm: float,
        temperature_c: float,
        humidity_percent: float,
        test_mode: bool = False,
    ) -> dict[str, Any]:
        gas_level = GasLevel(gas_ppm)
        safety_level = self.protocol.determine_safety_level(gas_ppm)
        required_action = self.protocol.determine_required_action(gas_ppm, test_mode)

        return {
            "gas_ppm": gas_ppm,
            "temperature_c": temperature_c,
            "humidity_percent": humidity_percent,
            "safety_level": safety_level.value,
            "required_action": required_action.value,
            "is_safe": gas_level.is_safe(),
            "is_warning": gas_level.is_warning(),
            "is_critical": gas_level.is_critical(),
            "should_close_valve": self.protocol.should_close_valve(gas_ppm, test_mode),
            "should_activate_dissipator": self.protocol.should_activate_dissipator(
                gas_ppm, test_mode
            ),
            "test_mode": test_mode,
            "analyzed_at": datetime.utcnow(),
        }

    def should_create_alert(
        self, gas_ppm: float, test_mode: bool = False
    ) -> tuple[bool, str | None]:
        if test_mode:
            return False, None

        safety_level = self.protocol.determine_safety_level(gas_ppm)

        if safety_level == SafetyLevel.CRITICAL:
            return True, "critical"
        elif safety_level == SafetyLevel.WARNING:
            return True, "warning"
        else:
            return False, None

    def should_resolve_alert(
        self, current_gas_ppm: float, alert_severity: str, alert_age_minutes: int
    ) -> bool:
        if alert_severity == "critical":
            return False

        if alert_severity == "warning":
            if current_gas_ppm < self.protocol.thresholds.warning_ppm:
                if alert_age_minutes >= 5:
                    return True

        return False

    def calculate_trend(
        self, readings: list[tuple[datetime, float]], window_minutes: int = 5
    ) -> str:
        if len(readings) < 2:
            return "stable"

        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_readings = [(ts, ppm) for ts, ppm in readings if ts >= cutoff_time]

        if len(recent_readings) < 2:
            return "stable"

        recent_readings.sort(key=lambda x: x[0])

        first_ppm = recent_readings[0][1]
        last_ppm = recent_readings[-1][1]

        change = last_ppm - first_ppm
        change_percent = (change / first_ppm * 100) if first_ppm > 0 else 0

        if change_percent > 10:
            return "rising"
        elif change_percent < -10:
            return "falling"
        else:
            return "stable"


def create_default_safety_protocol() -> SafetyProtocol:
    thresholds = SafetyThresholds(
        warning_ppm=200.0,
        critical_ppm=500.0,
        auto_valve_close_ppm=500.0,
        auto_dissipator_activate_ppm=500.0,
    )
    return SafetyProtocol(
        thresholds=thresholds,
        auto_valve_close_enabled=True,
        auto_dissipator_enabled=True,
        require_manual_valve_open=True,
    )
