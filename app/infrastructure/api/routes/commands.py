from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.sensor.control_dissipator import ControlDissipator
from app.domain.audit.entities import ActionType
from app.domain.shared.exceptions import DissipatorLockedError, SensorNotFoundError
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.audit import audit_action
from app.infrastructure.api.middleware.auth import get_current_user, require_sensor_access, TokenData
from app.infrastructure.database.repositories.sensor_repository import SensorRepository
from app.infrastructure.messaging.mqtt_client import mqtt_client

router = APIRouter(prefix="/commands", tags=["Commands"])


class DissipatorCommandRequest(BaseModel):
    command: str

    class Config:
        json_schema_extra = {"example": {"command": "on"}}


class DissipatorCommandResponse(BaseModel):
    sensor_id: str
    dissipator_id: str
    command: str
    state: str
    activation_mode: str
    locked_by_alert: bool
    mqtt_published: bool


@router.post("/panic/{sensor_id}")
@audit_action(action_type=ActionType.PANIC_BUTTON_PRESSED, resource_type="valve")
async def panic_button(
    request: Request,
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    session: AsyncSession = Depends(get_current_session),
):
    from app.domain.sensor.entities import CommandSource
    from app.infrastructure.database.repositories.sensor_repository import SensorRepository

    repo = SensorRepository(session)

    sensor = await repo.get_by_id(sensor_id)
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Sensor {sensor_id} not found"
        )

    valve = await repo.get_valve_by_sensor_id(sensor_id)
    if not valve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No valve found for sensor {sensor_id}"
        )

    from app.domain.sensor.services import SensorStateManager

    state_manager = SensorStateManager(sensor, valve, None)

    state_manager.close_valve(CommandSource.REMOTE, gas_level_ppm=0.0)
    await repo.update_valve(valve)

    await mqtt_client.publish_valve_command(
        device_id=sensor.device_id,
        command="close",
        source="panic",
    )

    return {
        "sensor_id": str(sensor_id),
        "valve_id": str(valve.id),
        "command": "panic_close",
        "state": valve.state.value,
        "mqtt_published": True,
    }


@router.post("/test-mode/{sensor_id}")
@audit_action(action_type=ActionType.TEST_MODE_ACTIVATED, resource_type="sensor")
async def activate_test_mode(
    request: Request,
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    timeout_minutes: int = 30,
    session: AsyncSession = Depends(get_current_session),
):
    from app.infrastructure.database.repositories.sensor_repository import SensorRepository

    repo = SensorRepository(session)

    sensor = await repo.get_by_id(sensor_id)
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Sensor {sensor_id} not found"
        )

    sensor.activate_test_mode(timeout_minutes)
    await repo.update(sensor)

    return {
        "sensor_id": str(sensor_id),
        "test_mode": sensor.test_mode,
        "test_mode_expires_at": sensor.test_mode_expires_at.isoformat()
        if sensor.test_mode_expires_at
        else None,
    }


@router.post("/dissipator/{sensor_id}", response_model=DissipatorCommandResponse)
@audit_action(action_type=ActionType.DISSIPATOR_ACTIVATED, resource_type="dissipator")
async def control_dissipator(
    request: Request,
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    command_request: DissipatorCommandRequest,
    session: AsyncSession = Depends(get_current_session),
):
    if command_request.command not in ["on", "off"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Command must be 'on' or 'off'"
        )

    repo = SensorRepository(session)
    use_case = ControlDissipator(repo)

    try:
        result = await use_case.execute(
            sensor_id=sensor_id,
            command=command_request.command,
            user_id=None,
        )

        sensor = await repo.get_by_id(sensor_id)
        if sensor:
            await mqtt_client.publish_dissipator_command(
                device_id=sensor.device_id,
                state=command_request.command,
                mode="manual",
            )
            mqtt_published = True
        else:
            mqtt_published = False

        return DissipatorCommandResponse(
            sensor_id=result["sensor_id"],
            dissipator_id=result["dissipator_id"],
            command=result["command"],
            state=result["state"],
            activation_mode=result["activation_mode"],
            locked_by_alert=result["locked_by_alert"],
            mqtt_published=mqtt_published,
        )

    except SensorNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DissipatorLockedError:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cannot deactivate dissipator while alert is active. Dissipator is locked by safety protocol.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
