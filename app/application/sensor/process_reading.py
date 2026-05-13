from datetime import datetime
from uuid import UUID

import structlog

from app.domain.safety.services import GasLevelAnalyzer, create_default_safety_protocol
from app.domain.sensor.entities import ActivationMode, CommandSource
from app.domain.sensor.repository import ISensorRepository
from app.domain.sensor.services import SensorStateManager
from app.domain.shared.exceptions import SensorNotFoundError

logger = structlog.get_logger()


class ProcessSensorReading:
    def __init__(
        self,
        sensor_repository: ISensorRepository,
        gas_analyzer: GasLevelAnalyzer | None = None,
    ) -> None:
        self.sensor_repository = sensor_repository
        self.gas_analyzer = gas_analyzer or GasLevelAnalyzer(create_default_safety_protocol())

    async def execute(
        self,
        device_id: str,
        gas_ppm: float,
        temperature_c: float,
        humidity_percent: float,
        wifi_signal: int | None = None,
        timestamp: datetime | None = None,
    ) -> dict:
        sensor = await self.sensor_repository.get_by_device_id(device_id)
        if not sensor:
            raise SensorNotFoundError(device_id)

        valve = await self.sensor_repository.get_valve_by_sensor_id(sensor.id)
        dissipator = await self.sensor_repository.get_dissipator_by_sensor_id(sensor.id)

        state_manager = SensorStateManager(sensor, valve, dissipator)

        state_manager.update_connection_status(mqtt_connected=True, wifi_signal=wifi_signal)
        state_manager.record_reading()

        analysis = self.gas_analyzer.analyze_reading(
            gas_ppm=gas_ppm,
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            test_mode=sensor.test_mode,
        )

        if not sensor.test_mode:
            state_manager.execute_safety_protocol(
                gas_ppm=gas_ppm,
                should_close_valve=analysis["should_close_valve"],
                should_activate_dissipator=analysis["should_activate_dissipator"],
            )

        await self.sensor_repository.update(sensor)
        if valve:
            await self.sensor_repository.update_valve(valve)
        if dissipator:
            await self.sensor_repository.update_dissipator(dissipator)

        events = state_manager.get_events()

        logger.info(
            "sensor_reading_processed",
            sensor_id=str(sensor.id),
            device_id=device_id,
            gas_ppm=gas_ppm,
            safety_level=analysis["safety_level"],
            valve_closed=state_manager.is_valve_closed(),
            dissipator_active=state_manager.is_dissipator_active(),
            test_mode=sensor.test_mode,
            events_count=len(events),
        )

        return {
            "sensor_id": str(sensor.id),
            "device_id": device_id,
            "analysis": analysis,
            "valve_closed": state_manager.is_valve_closed(),
            "dissipator_active": state_manager.is_dissipator_active(),
            "events": [event.to_dict() for event in events],
            "timestamp": timestamp or datetime.utcnow(),
        }
