from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.audit.entities import ActionType, AuditLog


class IAuditRepository(ABC):
    @abstractmethod
    async def save(self, audit_log: AuditLog) -> AuditLog:
        pass

    @abstractmethod
    async def list_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        pass

    @abstractmethod
    async def list_by_action_type(
        self, action_type: ActionType, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        pass

    @abstractmethod
    async def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[AuditLog]:
        pass

    @abstractmethod
    async def count_by_action_type(self, action_type: ActionType) -> int:
        pass

    @abstractmethod
    async def get_security_metrics(self, days: int = 7) -> dict:
        pass
