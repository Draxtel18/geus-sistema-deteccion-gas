from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from worker.shared.constants import GAS_THRESHOLD_CRITICAL, GAS_THRESHOLD_WARNING


class SensorReadingSchema(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    gas_ppm: float = Field(..., ge=0, le=10000)
    temperature_c: float = Field(..., ge=-40, le=85)
    humidity_percent: float = Field(..., ge=0, le=100)
    wifi_signal: int | None = Field(None, ge=-100, le=0)
    timestamp: datetime

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("device_id cannot be empty")
        return v


class AlertSchema(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    gas_level_ppm: float = Field(..., ge=0, le=10000)
    severity: Literal["warning", "critical"]
    timestamp: datetime

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str, values: dict) -> str:
        gas_level = values.data.get("gas_level_ppm", 0)
        if v == "warning" and not (GAS_THRESHOLD_WARNING <= gas_level < GAS_THRESHOLD_CRITICAL):
            raise ValueError(f"Warning severity requires gas level between {GAS_THRESHOLD_WARNING:.0f}-{GAS_THRESHOLD_CRITICAL:.0f} ppm")
        if v == "critical" and gas_level < GAS_THRESHOLD_CRITICAL:
            raise ValueError(f"Critical severity requires gas level >= {GAS_THRESHOLD_CRITICAL:.0f} ppm")
        return v


class ValveCommandSchema(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    command: Literal["open", "close"]
    source: Literal["local", "remote", "panic"]
    timestamp: datetime


class DissipatorCommandSchema(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    state: Literal["on", "off"]
    mode: Literal["manual", "automatic"]
    timestamp: datetime
