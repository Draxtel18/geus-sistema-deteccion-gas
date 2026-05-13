from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.export_data import ExportData
from app.application.audit.query_logs import QueryLogs
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.auth import require_permission, Permission
from app.infrastructure.database.repositories.audit_repository import AuditRepository

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs", dependencies=[Depends(require_permission(Permission.VIEW_AUDIT))])
async def get_audit_logs(
    user_id: UUID | None = Query(None),
    action_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_current_session),
):
    repo = AuditRepository(session)
    use_case = QueryLogs(repo)

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    try:
        result = await use_case.execute(
            user_id=user_id,
            action_type=action_type,
            start_date=start_dt,
            end_date=end_dt,
            skip=skip,
            limit=limit,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/export", dependencies=[Depends(require_permission(Permission.EXPORT_DATA))])
async def export_audit_data(
    start_date: str = Query(...),
    end_date: str = Query(...),
    format: str = Query("csv"),
    session: AsyncSession = Depends(get_current_session),
):
    repo = AuditRepository(session)
    use_case = ExportData(repo)

    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        content, content_type = await use_case.execute(
            start_date=start_dt,
            end_date=end_dt,
            format=format,
        )

        filename = f"audit_export_{start_date}_{end_date}.{format}"

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/security", dependencies=[Depends(require_permission(Permission.VIEW_AUDIT))])
async def get_security_metrics(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_current_session),
):
    repo = AuditRepository(session)
    metrics = await repo.get_security_metrics(days=days)
    return metrics
