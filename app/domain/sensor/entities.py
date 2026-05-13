from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.shared.exceptions import DissipatorLockedError, ValveOperationError
from app.domain.shared.value_objects import Location


class SensorStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ValveState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class DissipatorState(StrEnum):
    ON = "on"
    OFF = "off"


class ActivationMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class MechanicalStatus(StrEnum):
    OK = "ok"
    STUCK = "stuck"
    UNKNOWN = "unknown"


class CommandSource(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"
    PANIC = "panic"


@dataclass
class Sensor:
    id: UUID
    device_id: str
    location: Location
    status: SensorStatus
    wifi_signal: int | None = None
    mqtt_connected: bool = False
    uptime_seconds: int = 0
    test_mode: bool = False
    test_mode_expires_at: datetime | None = None
    correction_factor: float = 1.0
    last_reading_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.wifi_signal is not None and not (-100 <= self.wifi_signal <= 0):
            raise ValueError("WiFi signal must be between -100 and 0 dBm")
        if not (0.5 <= self.correction_factor <= 2.0):
            raise ValueError("Correction factor must be between 0.5 and 2.0")

    def activate_test_mode(self, timeout_minutes: int = 30) -> None:
        self.test_mode = True
        self.test_mode_expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        self.updated_at = datetime.utcnow()

    def deactivate_test_mode(self) -> None:
        self.test_mode = False
        self.test_mode_expires_at = None
        self.updated_at = datetime.utcnow()

    def check_test_mode_expiration(self) -> None:
        if self.test_mode and self.test_mode_expires_at:
            if datetime.utcnow() >= self.test_mode_expires_at:
                self.deactivate_test_mode()

    def update_connection_status(
        self, mqtt_connected: bool, wifi_signal: int | None = None
    ) -> None:
        self.mqtt_connected = mqtt_connected
        self.status = SensorStatus.ONLINE if mqtt_connected else SensorStatus.OFFLINE
        if wifi_signal is not None:
            self.wifi_signal = wifi_signal
        self.updated_at = datetime.utcnow()

    def record_reading(self) -> None:
        self.last_reading_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


@dataclass
class Valve:
    id: UUID
    sensor_id: UUID
    state: ValveState
    last_state_change: datetime
    mechanical_status: MechanicalStatus = MechanicalStatus.OK
    last_command_source: CommandSource | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def close(self, source: CommandSource) -> None:
        if self.mechanical_status == MechanicalStatus.STUCK:
            raise ValveOperationError("Valve is mechanically stuck")

        self.state = ValveState.CLOSED
        self.last_command_source = source
        self.last_state_change = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def open(self, source: CommandSource) -> None:
        if self.mechanical_status == MechanicalStatus.STUCK:
            raise ValveOperationError("Valve is mechanically stuck")

        self.state = ValveState.OPEN
        self.last_command_source = source
        self.last_state_change = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_stuck(self) -> None:
        self.mechanical_status = MechanicalStatus.STUCK
        self.updated_at = datetime.utcnow()

    def is_closed(self) -> bool:
        return self.state == ValveState.CLOSED


@dataclass
class Dissipator:
    id: UUID
    sensor_id: UUID
    state: DissipatorState
    activation_mode: ActivationMode
    last_state_change: datetime
    mechanical_status: MechanicalStatus = MechanicalStatus.OK
    locked_by_alert: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def activate(self, mode: ActivationMode, locked: bool = False) -> None:
        self.state = DissipatorState.ON
        self.activation_mode = mode
        self.locked_by_alert = locked
        self.last_state_change = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        if self.locked_by_alert:
            raise DissipatorLockedError()

        self.state = DissipatorState.OFF
        self.activation_mode = ActivationMode.MANUAL
        self.last_state_change = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def unlock(self) -> None:
        self.locked_by_alert = False
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        return self.state == DissipatorState.ON
