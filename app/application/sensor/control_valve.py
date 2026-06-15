from uuid import UUID

import structlog

from app.domain.sensor.entities import CommandSource
from app.domain.sensor.repository import ISensorRepository
from app.domain.sensor.services import SensorStateManager
from app.domain.shared.exceptions import SensorNotFoundError, ValveOperationError

logger = structlog.get_logger()


class ControlValve:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(
        self, sensor_id: UUID, command: str, user_id: UUID | None = None
    ) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        valve = await self.sensor_repository.get_valve_by_sensor_id(sensor_id)
        if not valve:
            raise ValueError(f"No valve found for sensor {sensor_id}")

        state_manager = SensorStateManager(sensor, valve, None)

        if command == "open":
            state_manager.open_valve(CommandSource.REMOTE, user_id)
            logger.info(
                "valve_opened_manually",
                sensor_id=str(sensor_id),
                user_id=str(user_id) if user_id else None,
            )
        elif command == "close":
            state_manager.close_valve(CommandSource.REMOTE, gas_level_ppm=0.0)
            logger.info(
                "valve_closed_manually",
                sensor_id=str(sensor_id),
                user_id=str(user_id) if user_id else None,
            )
        else:
            raise ValueError(f"Invalid command: {command}. Must be 'open' or 'close'")

        try:
            updated_valve = await self.sensor_repository.update_valve(valve)
        except Exception as exc:
            raise ValveOperationError(str(exc)) from exc

        events = state_manager.get_events()

        return {
            "sensor_id": str(sensor_id),
            "valve_id": str(updated_valve.id),
            "command": command,
            "state": updated_valve.state.value,
            "last_command_source": updated_valve.last_command_source.value
            if updated_valve.last_command_source
            else None,
            "events": [event.to_dict() for event in events],
        }
