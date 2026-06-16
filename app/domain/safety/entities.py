from dataclasses import dataclass
from enum import StrEnum

from app.core.constants import GAS_THRESHOLD_CRITICAL, GAS_THRESHOLD_WARNING


class SafetyLevel(StrEnum):
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"


class ActionType(StrEnum):
    NONE = "none"
    ALERT_ONLY = "alert_only"
    CLOSE_VALVE = "close_valve"
    ACTIVATE_DISSIPATOR = "activate_dissipator"
    FULL_LOCKDOWN = "full_lockdown"


@dataclass(frozen=True)
class SafetyThresholds:
    warning_ppm: float = GAS_THRESHOLD_WARNING
    critical_ppm: float = GAS_THRESHOLD_CRITICAL
    auto_valve_close_ppm: float = GAS_THRESHOLD_CRITICAL
    auto_dissipator_activate_ppm: float = GAS_THRESHOLD_WARNING

    def __post_init__(self) -> None:
        if self.warning_ppm >= self.critical_ppm:
            raise ValueError("Warning threshold must be less than critical threshold")
        if self.critical_ppm <= 0 or self.warning_ppm <= 0:
            raise ValueError("Thresholds must be positive values")


@dataclass
class SafetyProtocol:
    thresholds: SafetyThresholds
    auto_valve_close_enabled: bool = True
    auto_dissipator_enabled: bool = True
    require_manual_valve_open: bool = True

    def determine_safety_level(self, gas_ppm: float) -> SafetyLevel:
        if gas_ppm >= self.thresholds.critical_ppm:
            return SafetyLevel.CRITICAL
        elif gas_ppm >= self.thresholds.warning_ppm:
            return SafetyLevel.WARNING
        else:
            return SafetyLevel.SAFE

    def determine_required_action(self, gas_ppm: float, test_mode: bool = False) -> ActionType:
        if test_mode:
            return ActionType.NONE

        safety_level = self.determine_safety_level(gas_ppm)

        if safety_level == SafetyLevel.CRITICAL:
            if self.auto_valve_close_enabled and self.auto_dissipator_enabled:
                return ActionType.FULL_LOCKDOWN
            elif self.auto_valve_close_enabled:
                return ActionType.CLOSE_VALVE
            elif self.auto_dissipator_enabled:
                return ActionType.ACTIVATE_DISSIPATOR
            else:
                return ActionType.ALERT_ONLY
        elif safety_level == SafetyLevel.WARNING:
            return ActionType.ALERT_ONLY
        else:
            return ActionType.NONE

    def should_close_valve(self, gas_ppm: float, test_mode: bool = False) -> bool:
        if test_mode or not self.auto_valve_close_enabled:
            return False
        return gas_ppm >= self.thresholds.auto_valve_close_ppm

    def should_activate_dissipator(self, gas_ppm: float, test_mode: bool = False) -> bool:
        if test_mode or not self.auto_dissipator_enabled:
            return False
        return gas_ppm >= self.thresholds.auto_dissipator_activate_ppm

    def can_open_valve_automatically(self, gas_ppm: float) -> bool:
        if self.require_manual_valve_open:
            return False
        return gas_ppm < self.thresholds.warning_ppm
