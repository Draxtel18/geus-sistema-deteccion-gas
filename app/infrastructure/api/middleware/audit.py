from functools import wraps
from typing import Callable
from uuid import UUID

from fastapi import Request

from app.domain.audit.entities import ActionType


def audit_action(action_type: ActionType, resource_type: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from app.infrastructure.api.dependencies import get_current_session
            from app.infrastructure.database.repositories.audit_repository import AuditRepository
            from app.application.audit.log_action import LogAction

            result = await func(*args, **kwargs)

            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            user_id = None
            ip_address = None
            user_agent = None

            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

                if hasattr(request.state, "user"):
                    user_id = request.state.user.user_id

            resource_id = kwargs.get("sensor_id") or kwargs.get("alert_id") or kwargs.get("user_id")

            try:
                async for session in get_current_session():
                    repo = AuditRepository(session)
                    use_case = LogAction(repo)

                    await use_case.execute(
                        user_id=user_id,
                        action_type=action_type,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details={"endpoint": str(request.url) if request else None},
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    await session.commit()
                    break
            except Exception:
                pass

            return result

        return wrapper
    return decorator
