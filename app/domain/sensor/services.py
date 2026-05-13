from datetime import datetime, timedelta
from uuid import UUID

from app.domain.sensor.entities import (
    ActivationMode,
    CommandSource,
    Dissipator,
    DissipatorState,
    Sensor,
    SensorStatus,
    Valve,
    ValveState,
)
from app.domain.shared.events import (
    DissipatorActivatedEvent,
    DissipatorDeactivatedEvent,
    ValveClosedEvent,
    ValveOpenedEvent,
)
from app.domain.shared.exceptions import (
    SensorOfflineError,
    TestModeActiveError,
    ValveOperationError,
)


class SensorStateManager:
    def __init__(
        self, sensor: Sensor, valve: Valve | None = None, dissipator: Dissipator | None = None
    ) -> None:
        self.sensor = sensor
        self.valve = valve
        self.dissipator = dissipator
        self.events: list = []

    def validate_sensor_operational(self) -> None:
        if self.sensor.status == SensorStatus.OFFLINE:
            raise SensorOfflineError(str(self.sensor.id))

        self.sensor.check_test_mode_expiration()

        if self.sensor.test_mode:
            raise TestModeActiveError(str(self.sensor.id))

    def close_valve(self, source: CommandSource, gas_level_ppm: float) -> None:
        if not self.valve:
            raise ValveOperationError("No valve associated with this sensor")

        self.valve.close(source)

        event = ValveClosedEvent(
            sensor_id=self.sensor.id,
            valve_id=self.valve.id,
            source=source.value,
            gas_level_ppm=gas_level_ppm,
        )
        event.aggregate_id = self.sensor.id
        self.events.append(event)

    def open_valve(self, source: CommandSource, user_id: UUID | None = None) -> None:
        if not self.valve:
            raise ValveOperationError("No valve associated with this sensor")

        self.valve.open(source)

        event = ValveOpenedEvent(
            sensor_id=self.sensor.id,
            valve_id=self.valve.id,
            opened_by=user_id,
        )
        event.aggregate_id = self.sensor.id
        self.events.append(event)

    def activate_dissipator(self, mode: ActivationMode, triggered_by_alert: bool = False) -> None:
        if not self.dissipator:
            return

        self.dissipator.activate(mode, locked=triggered_by_alert)

        event = DissipatorActivatedEvent(
            sensor_id=self.sensor.id,
            dissipator_id=self.dissipator.id,
            activation_mode=mode.value,
            triggered_by_alert=triggered_by_alert,
        )
        event.aggregate_id = self.sensor.id
        self.events.append(event)

    def deactivate_dissipator(self, user_id: UUID | None = None) -> None:
        if not self.dissipator:
            return

        self.dissipator.deactivate()

        event = DissipatorDeactivatedEvent(
            sensor_id=self.sensor.id,
            dissipator_id=self.dissipator.id,
            deactivated_by=user_id,
        )
        event.aggregate_id = self.sensor.id
        self.events.append(event)

    def execute_safety_protocol(
        self, gas_ppm: float, should_close_valve: bool, should_activate_dissipator: bool
    ) -> None:
        if should_close_valve and self.valve and self.valve.state == ValveState.OPEN:
            self.close_valve(CommandSource.REMOTE, gas_ppm)

        if (
            should_activate_dissipator
            and self.dissipator
            and self.dissipator.state == DissipatorState.OFF
        ):
            self.activate_dissipator(ActivationMode.AUTOMATIC, triggered_by_alert=True)

    def update_connection_status(
        self, mqtt_connected: bool, wifi_signal: int | None = None
    ) -> None:
        self.sensor.update_connection_status(mqtt_connected, wifi_signal)

    def record_reading(self) -> None:
        self.sensor.record_reading()

    def activate_test_mode(self, timeout_minutes: int = 30) -> None:
        self.sensor.activate_test_mode(timeout_minutes)

    def deactivate_test_mode(self) -> None:
        self.sensor.deactivate_test_mode()

    def is_valve_closed(self) -> bool:
        return self.valve.is_closed() if self.valve else False

    def is_dissipator_active(self) -> bool:
        return self.dissipator.is_active() if self.dissipator else False

    def get_events(self) -> list:
        return self.events.copy()

    def clear_events(self) -> None:
        self.events.clear()
