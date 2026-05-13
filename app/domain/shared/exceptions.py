class DomainException(Exception):
    pass


class SensorNotFoundError(DomainException):
    def __init__(self, sensor_id: str) -> None:
        super().__init__(f"Sensor not found: {sensor_id}")


class AlertNotFoundError(DomainException):
    def __init__(self, alert_id: str) -> None:
        super().__init__(f"Alert not found: {alert_id}")


class UserNotFoundError(DomainException):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User not found: {user_id}")


class InvalidGasLevelError(DomainException):
    def __init__(self, ppm: float) -> None:
        super().__init__(f"Invalid gas level: {ppm} ppm")


class InvalidCredentialsError(DomainException):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class UnauthorizedError(DomainException):
    def __init__(self, message: str = "Unauthorized access") -> None:
        super().__init__(message)


class PermissionDeniedError(DomainException):
    def __init__(self, action: str, role: str) -> None:
        super().__init__(f"Role '{role}' does not have permission to: {action}")


class ValveOperationError(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Valve operation failed: {message}")


class DissipatorOperationError(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Dissipator operation failed: {message}")


class DissipatorLockedError(DomainException):
    def __init__(self) -> None:
        super().__init__("Cannot deactivate dissipator while alert is active")


class AlertAlreadyResolvedError(DomainException):
    def __init__(self, alert_id: str) -> None:
        super().__init__(f"Alert {alert_id} is already resolved")


class TestModeActiveError(DomainException):
    def __init__(self, sensor_id: str) -> None:
        super().__init__(f"Sensor {sensor_id} is in test mode")


class SensorOfflineError(DomainException):
    def __init__(self, sensor_id: str) -> None:
        super().__init__(f"Sensor {sensor_id} is offline")


class InvalidSensorAssignmentError(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid sensor assignment: {message}")
