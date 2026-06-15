from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.auth import get_current_user, require_sensor_access, TokenData
from app.infrastructure.database.repositories.sensor_repository import SensorRepository

router = APIRouter(prefix="/sensors", tags=["Sensors"])


class RegisterSensorRequest(BaseModel):
    device_id: str
    location: str
    correction_factor: float = 1.0
    create_valve: bool = True
    create_dissipator: bool = True


class SensorResponse(BaseModel):
    id: str
    device_id: str
    location: str
    status: str
    wifi_signal: int | None
    mqtt_connected: bool
    uptime_seconds: int
    test_mode: bool
    correction_factor: float
    last_reading_at: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ValveResponse(BaseModel):
    id: str
    sensor_id: str
    state: str
    last_state_change: str
    mechanical_status: str
    last_command_source: str | None

    class Config:
        from_attributes = True


class DissipatorResponse(BaseModel):
    id: str
    sensor_id: str
    state: str
    activation_mode: str
    last_state_change: str
    mechanical_status: str
    locked_by_alert: bool

    class Config:
        from_attributes = True


class SensorDetailResponse(BaseModel):
    sensor: SensorResponse
    valve: ValveResponse | None
    dissipator: DissipatorResponse | None


@router.get("/{sensor_id}/health")
async def get_sensor_health(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = SensorRepository(session)
    
    sensor = await repo.get_by_id(sensor_id)
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor {sensor_id} not found"
        )
    
    valve = await repo.get_valve_by_sensor_id(sensor_id)
    dissipator = await repo.get_dissipator_by_sensor_id(sensor_id)
    
    from datetime import datetime, timedelta
    is_online = sensor.mqtt_connected
    last_seen_minutes = None
    if sensor.last_reading_at:
        delta = datetime.utcnow() - sensor.last_reading_at
        last_seen_minutes = int(delta.total_seconds() / 60)
    
    health_status = "healthy"
    issues = []
    
    if not is_online:
        health_status = "critical"
        issues.append("MQTT disconnected")
    
    if last_seen_minutes and last_seen_minutes > 5:
        health_status = "warning" if health_status == "healthy" else health_status
        issues.append(f"No readings for {last_seen_minutes} minutes")
    
    if sensor.wifi_signal and sensor.wifi_signal < -80:
        health_status = "warning" if health_status == "healthy" else health_status
        issues.append("Weak WiFi signal")
    
    if valve and valve.mechanical_status.value == "stuck":
        health_status = "critical"
        issues.append("Valve mechanically stuck")
    
    if dissipator and dissipator.mechanical_status.value == "stuck":
        health_status = "critical"
        issues.append("Dissipator mechanically stuck")
    
    return {
        "sensor_id": str(sensor_id),
        "device_id": sensor.device_id,
        "health_status": health_status,
        "issues": issues,
        "diagnostics": {
            "mqtt_connected": is_online,
            "wifi_signal": sensor.wifi_signal,
            "last_reading_minutes_ago": last_seen_minutes,
            "uptime_seconds": sensor.uptime_seconds,
            "test_mode": sensor.test_mode,
            "valve_status": valve.mechanical_status.value if valve else None,
            "dissipator_status": dissipator.mechanical_status.value if dissipator else None,
        },
    }


@router.get("/{sensor_id}", response_model=SensorDetailResponse)
async def get_sensor(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    session: AsyncSession = Depends(get_current_session),
):
    repo = SensorRepository(session)
    
    sensor = await repo.get_by_id(sensor_id)
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor {sensor_id} not found"
        )
    
    valve = await repo.get_valve_by_sensor_id(sensor_id)
    dissipator = await repo.get_dissipator_by_sensor_id(sensor_id)
    
    sensor_response = SensorResponse(
        id=str(sensor.id),
        device_id=sensor.device_id,
        location=sensor.location.description,
        status=sensor.status.value,
        wifi_signal=sensor.wifi_signal,
        mqtt_connected=sensor.mqtt_connected,
        uptime_seconds=sensor.uptime_seconds,
        test_mode=sensor.test_mode,
        correction_factor=sensor.correction_factor,
        last_reading_at=sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
        created_at=sensor.created_at.isoformat(),
        updated_at=sensor.updated_at.isoformat(),
    )
    
    valve_response = None
    if valve:
        valve_response = ValveResponse(
            id=str(valve.id),
            sensor_id=str(valve.sensor_id),
            state=valve.state.value,
            last_state_change=valve.last_state_change.isoformat(),
            mechanical_status=valve.mechanical_status.value,
            last_command_source=valve.last_command_source.value if valve.last_command_source else None,
        )
    
    dissipator_response = None
    if dissipator:
        dissipator_response = DissipatorResponse(
            id=str(dissipator.id),
            sensor_id=str(dissipator.sensor_id),
            state=dissipator.state.value,
            activation_mode=dissipator.activation_mode.value,
            last_state_change=dissipator.last_state_change.isoformat(),
            mechanical_status=dissipator.mechanical_status.value,
            locked_by_alert=dissipator.locked_by_alert,
        )
    
    return SensorDetailResponse(
        sensor=sensor_response,
        valve=valve_response,
        dissipator=dissipator_response,
    )


@router.get("/{sensor_id}/current")
async def get_current_reading(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.sensor.get_current_reading import GetCurrentReading
    
    repo = SensorRepository(session)
    use_case = GetCurrentReading(repo)
    
    try:
        result = await use_case.execute(sensor_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{sensor_id}/latest-gas")
async def get_latest_gas_reading(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.sensor.get_latest_gas_reading import GetLatestGasReading

    repo = SensorRepository(session)
    use_case = GetLatestGasReading(repo)

    try:
        result = await use_case.execute(sensor_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{sensor_id}/readings")
async def get_readings_history(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    start: str | None = None,
    end: str | None = None,
    limit: int = 1000,
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.sensor.get_readings_history import GetReadingsHistory
    from datetime import datetime

    repo = SensorRepository(session)
    use_case = GetReadingsHistory(repo)

    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    try:
        result = await use_case.execute(sensor_id, start_dt, end_dt, limit)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{sensor_id}/stats")
async def get_sensor_stats(
    sensor_id: UUID,
    _: Annotated[TokenData, Depends(require_sensor_access)],
    period: str = "24h",
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.sensor.get_sensor_stats import GetSensorStats
    
    valid_periods = ["1h", "6h", "24h", "7d", "30d", "1y"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {', '.join(valid_periods)}"
        )
    
    repo = SensorRepository(session)
    use_case = GetSensorStats(repo)
    
    try:
        result = await use_case.execute(sensor_id, period)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("", response_model=list[SensorResponse])
async def list_sensors(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_current_session),
):
    repo = SensorRepository(session)
    sensors = await repo.list_all(skip=skip, limit=limit)
    
    return [
        SensorResponse(
            id=str(sensor.id),
            device_id=sensor.device_id,
            location=sensor.location.description,
            status=sensor.status.value,
            wifi_signal=sensor.wifi_signal,
            mqtt_connected=sensor.mqtt_connected,
            uptime_seconds=sensor.uptime_seconds,
            test_mode=sensor.test_mode,
            correction_factor=sensor.correction_factor,
            last_reading_at=sensor.last_reading_at.isoformat() if sensor.last_reading_at else None,
            created_at=sensor.created_at.isoformat(),
            updated_at=sensor.updated_at.isoformat(),
        )
        for sensor in sensors
    ]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_sensor(
    request: RegisterSensorRequest,
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.sensor.register_sensor import RegisterSensor
    
    repo = SensorRepository(session)
    use_case = RegisterSensor(repo)
    
    try:
        result = await use_case.execute(
            device_id=request.device_id,
            location=request.location,
            correction_factor=request.correction_factor,
            create_valve=request.create_valve,
            create_dissipator=request.create_dissipator,
        )
        await session.commit()
        return result
    except ValueError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register sensor: {str(e)}"
        ) from e
