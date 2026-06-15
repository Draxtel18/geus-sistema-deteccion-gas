from datetime import datetime
from uuid import UUID, uuid4

import structlog

from app.domain.audit.entities import ActionType, AuditLog
from app.domain.audit.repository import IAuditRepository

logger = structlog.get_logger()


class LogAction:
    def __init__(self, audit_repository: IAuditRepository) -> None:
        self.audit_repository = audit_repository

    async def execute(
        self,
        user_id: UUID | None,
        action_type: ActionType,
        resource_type: str,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            id=uuid4(),
            user_id=user_id,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            timestamp=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        saved_log = await self.audit_repository.save(audit_log)

        logger.info(
            "audit_log_created",
            audit_id=str(saved_log.id),
            user_id=str(user_id) if user_id else None,
            action_type=action_type.value,
            resource_type=resource_type,
        )

        return saved_log
