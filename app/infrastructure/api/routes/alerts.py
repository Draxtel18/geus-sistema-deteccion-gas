from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alert.entities import AlertStatus
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.database.repositories.alert_repository import AlertRepository

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class AlertResponse(BaseModel):
    id: str
    sensor_id: str
    gas_level_ppm: float
    severity: str
    status: str
    triggered_at: str
    acknowledged_at: str | None
    acknowledged_by: str | None
    resolved_at: str | None
    resolved_by: str | None
    auto_resolved: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    status_filter: str | None = Query(None, description="Filter by status: active, acknowledged, resolved"),
    severity: str | None = Query(None, description="Filter by severity: warning, critical"),
    sensor_id: UUID | None = Query(None, description="Filter by sensor ID"),
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_current_session),
):
    repo = AlertRepository(session)
    
    if status_filter == "active":
        alerts = await repo.list_active_alerts(skip=skip, limit=limit)
    elif status_filter:
        try:
            alert_status = AlertStatus(status_filter)
            alerts = await repo.list_by_status(alert_status, skip=skip, limit=limit)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    elif sensor_id:
        alerts = await repo.list_by_sensor(sensor_id, skip=skip, limit=limit)
    else:
        alerts = await repo.list_active_alerts(skip=skip, limit=limit)
    
    return [
        AlertResponse(
            id=str(alert.id),
            sensor_id=str(alert.sensor_id),
            gas_level_ppm=alert.gas_level_ppm,
            severity=alert.severity.value,
            status=alert.status.value,
            triggered_at=alert.triggered_at.isoformat(),
            acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            acknowledged_by=str(alert.acknowledged_by) if alert.acknowledged_by else None,
            resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
            resolved_by=str(alert.resolved_by) if alert.resolved_by else None,
            auto_resolved=alert.auto_resolved,
            created_at=alert.created_at.isoformat(),
        )
        for alert in alerts
    ]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_current_session),
):
    repo = AlertRepository(session)
    
    alert = await repo.get_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    
    return AlertResponse(
        id=str(alert.id),
        sensor_id=str(alert.sensor_id),
        gas_level_ppm=alert.gas_level_ppm,
        severity=alert.severity.value,
        status=alert.status.value,
        triggered_at=alert.triggered_at.isoformat(),
        acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        acknowledged_by=str(alert.acknowledged_by) if alert.acknowledged_by else None,
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
        resolved_by=str(alert.resolved_by) if alert.resolved_by else None,
        auto_resolved=alert.auto_resolved,
        created_at=alert.created_at.isoformat(),
    )


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.alert.acknowledge_alert import AcknowledgeAlert
    from uuid import uuid4
    
    repo = AlertRepository(session)
    use_case = AcknowledgeAlert(repo)
    
    try:
        result = await use_case.execute(alert_id, user_id=uuid4())
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_current_session),
):
    from app.application.alert.resolve_alert import ResolveAlert
    from uuid import uuid4
    
    repo = AlertRepository(session)
    use_case = ResolveAlert(repo)
    
    try:
        result = await use_case.execute(alert_id, user_id=uuid4())
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
