from datetime import datetime
from uuid import UUID

import structlog

from app.domain.audit.entities import ActionType
from app.domain.audit.repository import IAuditRepository

logger = structlog.get_logger()


class QueryLogs:
    def __init__(self, audit_repository: IAuditRepository) -> None:
        self.audit_repository = audit_repository

    async def execute(
        self,
        user_id: UUID | None = None,
        action_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        if start_date and end_date:
            logs = await self.audit_repository.list_by_date_range(
                start_date=start_date,
                end_date=end_date,
                skip=skip,
                limit=limit,
            )
        elif user_id:
            logs = await self.audit_repository.list_by_user(
                user_id=user_id,
                skip=skip,
                limit=limit,
            )
        elif action_type:
            action_enum = ActionType(action_type)
            logs = await self.audit_repository.list_by_action_type(
                action_type=action_enum,
                skip=skip,
                limit=limit,
            )
        else:
            logs = await self.audit_repository.list_all(skip=skip, limit=limit)

        log_list = [log.to_dict() for log in logs]

        logger.info(
            "audit_logs_queried",
            count=len(log_list),
            user_id=str(user_id) if user_id else None,
            action_type=action_type,
        )

        return {
            "logs": log_list,
            "count": len(log_list),
            "skip": skip,
            "limit": limit,
        }
