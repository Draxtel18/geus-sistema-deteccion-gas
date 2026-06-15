from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.sensor.control_dissipator import ControlDissipator
from app.application.sensor.control_valve import ControlValve
from app.domain.sensor.entities import (
    ActivationMode,
    Dissipator,
    DissipatorState,
    Sensor,
    SensorStatus,
    Valve,
    ValveState,
)
from app.domain.shared.value_objects import Location
from worker.alert_handler.consumer import AlertHandlerConsumer
from worker.gas_detection.consumer import GasDetectionConsumer


class FakeSensorRepository:
    def __init__(
        self,
        sensor: Sensor | None,
        valve: Valve | None = None,
        dissipator: Dissipator | None = None,
    ) -> None:
        self.sensor = sensor
        self.valve = valve
        self.dissipator = dissipator

    async def get_by_id(self, sensor_id):
        if self.sensor and self.sensor.id == sensor_id:
            return self.sensor
        return None

    async def get_valve_by_sensor_id(self, sensor_id):
        if self.valve and self.valve.sensor_id == sensor_id:
            return self.valve
        return None

    async def get_dissipator_by_sensor_id(self, sensor_id):
        if self.dissipator and self.dissipator.sensor_id == sensor_id:
            return self.dissipator
        return None

    async def update_valve(self, valve: Valve) -> Valve:
        self.valve = valve
        return valve

    async def update_dissipator(self, dissipator: Dissipator) -> Dissipator:
        self.dissipator = dissipator
        return dissipator


def build_sensor(sensor_id):
    return Sensor(
        id=sensor_id,
        device_id="sensor-1",
        location=Location("Kitchen"),
        status=SensorStatus.ONLINE,
    )


@pytest.mark.asyncio
async def test_control_valve_open_persists_remote_command():
    sensor_id = uuid4()
    repo = FakeSensorRepository(
        sensor=build_sensor(sensor_id),
        valve=Valve(
            id=uuid4(),
            sensor_id=sensor_id,
            state=ValveState.CLOSED,
            last_state_change=datetime.utcnow(),
        ),
    )

    result = await ControlValve(repo).execute(
        sensor_id=sensor_id,
        command="open",
        user_id=uuid4(),
    )

    assert result["command"] == "open"
    assert result["state"] == "open"
    assert result["last_command_source"] == "remote"
    assert repo.valve is not None
    assert repo.valve.state == ValveState.OPEN


@pytest.mark.asyncio
async def test_control_dissipator_off_unlocks_alert_lock():
    sensor_id = uuid4()
    repo = FakeSensorRepository(
        sensor=build_sensor(sensor_id),
        dissipator=Dissipator(
            id=uuid4(),
            sensor_id=sensor_id,
            state=DissipatorState.ON,
            activation_mode=ActivationMode.AUTOMATIC,
            last_state_change=datetime.utcnow(),
            locked_by_alert=True,
        ),
    )

    result = await ControlDissipator(repo).execute(
        sensor_id=sensor_id,
        command="off",
        user_id=uuid4(),
    )

    assert result["command"] == "off"
    assert result["state"] == "off"
    assert result["activation_mode"] == "manual"
    assert result["locked_by_alert"] is False


@pytest.mark.asyncio
async def test_alert_handler_build_notification_data_includes_snapshot_context():
    consumer = AlertHandlerConsumer()
    sensor_id = uuid4()
    consumer.alert_store.get_sensor_snapshot = AsyncMock(
        return_value={
            "sensor_id": sensor_id,
            "location": "Kitchen",
            "sensor_status": "online",
            "mqtt_connected": True,
            "valve_state": "closed",
            "dissipator_state": "on",
        }
    )

    data = await consumer._build_notification_data(
        device_id="sensor-1",
        severity="critical",
        gas_level_ppm=650.0,
        event="alert",
    )

    assert data["event"] == "alert"
    assert data["sensor_id"] == str(sensor_id)
    assert data["location"] == "Kitchen"
    assert data["sensor_status"] == "online"
    assert data["mqtt_connected"] is True
    assert data["valve_state"] == "closed"
    assert data["dissipator_state"] == "on"


@pytest.mark.asyncio
async def test_gas_detection_process_reading_sends_resolution_notification_with_context():
    consumer = GasDetectionConsumer()
    snapshot_sensor_id = uuid4()
    reading = SimpleNamespace(
        device_id="sensor-1",
        gas_ppm=120.0,
        temperature_c=24.0,
        humidity_percent=40.0,
        timestamp=datetime.utcnow(),
    )

    consumer.validator.validate = lambda data: (True, reading, None)
    consumer.processor.analyze_reading = lambda **kwargs: {
        "should_alert": False,
        "is_safe": True,
    }
    consumer.alert_store.resolve_active_alerts = AsyncMock(return_value=True)
    consumer.alert_store.get_notification_targets = AsyncMock(
        return_value=(["user@example.com"], ["ExponentPushToken[test]"])
    )
    consumer.alert_store.get_sensor_snapshot = AsyncMock(
        return_value={
            "sensor_id": snapshot_sensor_id,
            "location": "Kitchen",
            "sensor_status": "online",
            "mqtt_connected": True,
            "valve_state": "closed",
            "dissipator_state": "off",
        }
    )
    consumer.notifier.send_notification = AsyncMock(return_value=True)

    await consumer.process_reading({"device_id": "sensor-1"})

    consumer.notifier.send_notification.assert_awaited_once()
    kwargs = consumer.notifier.send_notification.await_args.kwargs
    assert kwargs["severity"] == "resolved"
    assert kwargs["recipients"] == ["user@example.com"]
    assert kwargs["push_tokens"] == ["ExponentPushToken[test]"]
    assert kwargs["data"]["event"] == "resolved"
    assert kwargs["data"]["sensor_id"] == str(snapshot_sensor_id)
    assert kwargs["data"]["location"] == "Kitchen"
    assert kwargs["data"]["valve_state"] == "closed"
    assert kwargs["data"]["dissipator_state"] == "off"
