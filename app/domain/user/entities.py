from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    TECHNICIAN = "technician"
    AUDITOR = "auditor"

class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass
class User:
    id: UUID
    email: str
    password_hash: str
    full_name: str
    role: UserRole
    status: UserStatus
    phone: str | None = None
    notifications_enabled: bool = True
    notification_devices: list[str] = field(default_factory=list)
    last_login_at: datetime | None = None
    last_login_ip: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.email or "@" not in self.email:
            raise ValueError("Invalid email address")
        if len(self.full_name.strip()) == 0:
            raise ValueError("Name cannot be empty")

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_operator(self) -> bool:
        return self.role == UserRole.OPERATOR

    def is_technician(self) -> bool:
        return self.role == UserRole.TECHNICIAN

    def is_auditor(self) -> bool:
        return self.role == UserRole.AUDITOR

    def suspend(self) -> None:
        self.status = UserStatus.SUSPENDED
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def record_login(self, ip_address: str) -> None:
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.updated_at = datetime.utcnow()

    def add_notification_device(self, device_token: str) -> None:
        if device_token not in self.notification_devices:
            self.notification_devices.append(device_token)
            self.updated_at = datetime.utcnow()

    def remove_notification_device(self, device_token: str) -> None:
        if device_token in self.notification_devices:
            self.notification_devices.remove(device_token)
            self.updated_at = datetime.utcnow()


@dataclass
class UserSensorAssignment:
    id: UUID
    user_id: UUID
    sensor_id: UUID
    assigned_at: datetime
    assigned_by: UUID | None = None

    def __post_init__(self) -> None:
        if not self.user_id or not self.sensor_id:
            raise ValueError("user_id and sensor_id are required")
