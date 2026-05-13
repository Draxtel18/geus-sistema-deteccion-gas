import structlog

logger = structlog.get_logger()


class SafetyLogic:
    def __init__(
        self,
        auto_valve_close_threshold: float = 500.0,
        auto_dissipator_threshold: float = 500.0,
    ) -> None:
        self.auto_valve_close_threshold = auto_valve_close_threshold
        self.auto_dissipator_threshold = auto_dissipator_threshold

    def determine_actions(
        self, device_id: str, severity: str, gas_level_ppm: float
    ) -> dict:
        should_close_valve = severity == "critical" and gas_level_ppm >= self.auto_valve_close_threshold
        should_activate_dissipator = severity == "critical" and gas_level_ppm >= self.auto_dissipator_threshold

        actions = {
            "device_id": device_id,
            "severity": severity,
            "gas_level_ppm": gas_level_ppm,
            "should_close_valve": should_close_valve,
            "should_activate_dissipator": should_activate_dissipator,
            "valve_command": "close" if should_close_valve else None,
            "dissipator_command": "on" if should_activate_dissipator else None,
            "dissipator_mode": "automatic" if should_activate_dissipator else None,
        }

        logger.info(
            "safety_actions_determined",
            device_id=device_id,
            severity=severity,
            gas_level_ppm=gas_level_ppm,
            should_close_valve=should_close_valve,
            should_activate_dissipator=should_activate_dissipator,
        )

        return actions
