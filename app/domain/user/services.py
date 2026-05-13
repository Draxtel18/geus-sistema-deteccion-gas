from enum import StrEnum
from uuid import UUID

import structlog

from app.domain.user.entities import UserRole

logger = structlog.get_logger()


class Permission(StrEnum):
    READ_SENSORS = "read:sensors"
    WRITE_SENSORS = "write:sensors"
    READ_ALERTS = "read:alerts"
    WRITE_ALERTS = "write:alerts"
    CONTROL_DEVICES = "control:devices"
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT = "view:audit"
    EXPORT_DATA = "export:data"
    TEST_MODE = "test:mode"
    VIEW_HEALTH = "view:health"


ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.READ_SENSORS,
        Permission.WRITE_SENSORS,
        Permission.READ_ALERTS,
        Permission.WRITE_ALERTS,
        Permission.CONTROL_DEVICES,
        Permission.MANAGE_USERS,
        Permission.VIEW_AUDIT,
        Permission.EXPORT_DATA,
        Permission.TEST_MODE,
        Permission.VIEW_HEALTH,
    ],
    UserRole.OPERATOR: [
        Permission.READ_SENSORS,
        Permission.READ_ALERTS,
        Permission.WRITE_ALERTS,
        Permission.CONTROL_DEVICES,
    ],
    UserRole.TECHNICIAN: [
        Permission.READ_SENSORS,
        Permission.READ_ALERTS,
        Permission.TEST_MODE,
        Permission.VIEW_HEALTH,
    ],
    UserRole.AUDITOR: [
        Permission.READ_SENSORS,
        Permission.READ_ALERTS,
        Permission.VIEW_AUDIT,
        Permission.EXPORT_DATA,
    ],
}


class PermissionChecker:
    def __init__(self) -> None:
        pass

    def has_permission(self, role: UserRole, permission: Permission) -> bool:
        role_perms = ROLE_PERMISSIONS.get(role, [])
        return permission in role_perms

    def has_any_permission(self, role: UserRole, permissions: list[Permission]) -> bool:
        return any(self.has_permission(role, perm) for perm in permissions)

    def has_all_permissions(self, role: UserRole, permissions: list[Permission]) -> bool:
        return all(self.has_permission(role, perm) for perm in permissions)

    def can_read_sensor(self, role: UserRole, user_id: UUID, sensor_owner_id: UUID | None = None) -> bool:
        if role == UserRole.ADMIN:
            return True
        if role == UserRole.OPERATOR and sensor_owner_id:
            return user_id == sensor_owner_id
        if role in [UserRole.TECHNICIAN, UserRole.AUDITOR]:
            return self.has_permission(role, Permission.READ_SENSORS)
        return False

    def can_control_device(self, role: UserRole, user_id: UUID, sensor_owner_id: UUID | None = None) -> bool:
        if role == UserRole.ADMIN:
            return True
        if role == UserRole.OPERATOR and sensor_owner_id:
            return user_id == sensor_owner_id
        return False

    def can_manage_users(self, role: UserRole) -> bool:
        return self.has_permission(role, Permission.MANAGE_USERS)

    def can_view_audit(self, role: UserRole) -> bool:
        return self.has_permission(role, Permission.VIEW_AUDIT)

    def can_activate_test_mode(self, role: UserRole) -> bool:
        return self.has_permission(role, Permission.TEST_MODE)


permission_checker = PermissionChecker()
