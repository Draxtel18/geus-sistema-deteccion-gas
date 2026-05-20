from datetime import datetime
from uuid import uuid4

import structlog

from app.domain.sensor.entities import (
    ActivationMode,
    Dissipator,
    DissipatorState,
    MechanicalStatus,
    Sensor,
    SensorStatus,
    Valve,
    ValveState,
)
from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.value_objects import Location

logger = structlog.get_logger()


class RegisterSensor:
    def __init__(self, repository: ISensorRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        device_id: str,
        location: str,
        correction_factor: float = 1.0,
        create_valve: bool = True,
        create_dissipator: bool = True,
    ) -> dict:
        existing = await self.repository.get_by_device_id(device_id)
        if existing:
            logger.warning("sensor_already_exists", device_id=device_id)
            raise ValueError(f"Sensor with device_id '{device_id}' already exists")

        sensor = Sensor(
            id=uuid4(),
            device_id=device_id,
            location=Location(location),
            status=SensorStatus.OFFLINE,
            wifi_signal=None,
            mqtt_connected=False,
            uptime_seconds=0,
            test_mode=False,
            test_mode_expires_at=None,
            correction_factor=correction_factor,
            last_reading_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        saved_sensor = await self.repository.save(sensor)
        logger.info("sensor_registered", sensor_id=str(saved_sensor.id), device_id=device_id)

        valve = None
        if create_valve:
            valve = Valve(
                id=uuid4(),
                sensor_id=saved_sensor.id,
                state=ValveState.OPEN,
                last_state_change=datetime.utcnow(),
                mechanical_status=MechanicalStatus.OK,
                last_command_source=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            valve = await self.repository.save_valve(valve)
            logger.info("valve_created", valve_id=str(valve.id), sensor_id=str(saved_sensor.id))

        dissipator = None
        if create_dissipator:
            dissipator = Dissipator(
                id=uuid4(),
                sensor_id=saved_sensor.id,
                state=DissipatorState.OFF,
                activation_mode=ActivationMode.MANUAL,
                last_state_change=datetime.utcnow(),
                mechanical_status=MechanicalStatus.OK,
                locked_by_alert=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            dissipator = await self.repository.save_dissipator(dissipator)
            logger.info("dissipator_created", dissipator_id=str(dissipator.id), sensor_id=str(saved_sensor.id))

        return {
            "sensor": {
                "id": str(saved_sensor.id),
                "device_id": saved_sensor.device_id,
                "location": saved_sensor.location.description,
                "status": saved_sensor.status.value,
                "correction_factor": saved_sensor.correction_factor,
                "created_at": saved_sensor.created_at.isoformat(),
            },
            "valve": {
                "id": str(valve.id),
                "state": valve.state.value,
                "mechanical_status": valve.mechanical_status.value,
            } if valve else None,
            "dissipator": {
                "id": str(dissipator.id),
                "state": dissipator.state.value,
                "activation_mode": dissipator.activation_mode.value,
            } if dissipator else None,
        }
