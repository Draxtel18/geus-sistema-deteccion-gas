from uuid import UUID

import structlog

from app.domain.sensor.entities import ActivationMode
from app.domain.sensor.repository import ISensorRepository
from app.domain.sensor.services import SensorStateManager
from app.domain.shared.exceptions import DissipatorLockedError, SensorNotFoundError

logger = structlog.get_logger()


class ControlDissipator:
    def __init__(self, sensor_repository: ISensorRepository) -> None:
        self.sensor_repository = sensor_repository

    async def execute(
        self, sensor_id: UUID, command: str, user_id: UUID | None = None
    ) -> dict:
        sensor = await self.sensor_repository.get_by_id(sensor_id)
        if not sensor:
            raise SensorNotFoundError(str(sensor_id))

        dissipator = await self.sensor_repository.get_dissipator_by_sensor_id(sensor_id)
        if not dissipator:
            raise ValueError(f"No dissipator found for sensor {sensor_id}")

        state_manager = SensorStateManager(sensor, None, dissipator)

        if command == "on":
            state_manager.activate_dissipator(ActivationMode.MANUAL, triggered_by_alert=False)
            logger.info(
                "dissipator_activated_manually",
                sensor_id=str(sensor_id),
                user_id=str(user_id) if user_id else None,
            )
        elif command == "off":
            if dissipator.locked_by_alert:
                raise DissipatorLockedError()
            
            state_manager.deactivate_dissipator(user_id)
            logger.info(
                "dissipator_deactivated_manually",
                sensor_id=str(sensor_id),
                user_id=str(user_id) if user_id else None,
            )
        else:
            raise ValueError(f"Invalid command: {command}. Must be 'on' or 'off'")

        await self.sensor_repository.update_dissipator(dissipator)

        events = state_manager.get_events()

        return {
            "sensor_id": str(sensor_id),
            "dissipator_id": str(dissipator.id),
            "command": command,
            "state": dissipator.state.value,
            "activation_mode": dissipator.activation_mode.value,
            "locked_by_alert": dissipator.locked_by_alert,
            "events": [event.to_dict() for event in events],
        }
