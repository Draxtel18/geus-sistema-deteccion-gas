from dataclasses import dataclass
from datetime import datetime
from typing import NewType
from uuid import UUID

SensorId = NewType("SensorId", UUID)
UserId = NewType("UserId", UUID)
AlertId = NewType("AlertId", UUID)
ValveId = NewType("ValveId", UUID)
DissipatorId = NewType("DissipatorId", UUID)


@dataclass(frozen=True)
class GasLevel:
    ppm: float

    def __post_init__(self) -> None:
        if self.ppm < 0 or self.ppm > 10000:
            raise ValueError(f"Gas level must be between 0 and 10000 ppm, got {self.ppm}")

    def is_safe(self) -> bool:
        return self.ppm < 200

    def is_warning(self) -> bool:
        return 200 <= self.ppm < 500

    def is_critical(self) -> bool:
        return self.ppm >= 500


@dataclass(frozen=True)
class Temperature:
    celsius: float

    def __post_init__(self) -> None:
        if self.celsius < -40 or self.celsius > 85:
            raise ValueError(f"Temperature must be between -40 and 85°C, got {self.celsius}")


@dataclass(frozen=True)
class Humidity:
    percent: float

    def __post_init__(self) -> None:
        if self.percent < 0 or self.percent > 100:
            raise ValueError(f"Humidity must be between 0 and 100%, got {self.percent}")


@dataclass(frozen=True)
class Location:
    description: str

    def __post_init__(self) -> None:
        if not self.description or len(self.description.strip()) == 0:
            raise ValueError("Location description cannot be empty")
        if len(self.description) > 255:
            raise ValueError("Location description cannot exceed 255 characters")


@dataclass(frozen=True)
class Timestamp:
    value: datetime

    @classmethod
    def now(cls) -> "Timestamp":
        return cls(datetime.utcnow())

    def __lt__(self, other: "Timestamp") -> bool:
        return self.value < other.value

    def __le__(self, other: "Timestamp") -> bool:
        return self.value <= other.value

    def __gt__(self, other: "Timestamp") -> bool:
        return self.value > other.value

    def __ge__(self, other: "Timestamp") -> bool:
        return self.value >= other.value
