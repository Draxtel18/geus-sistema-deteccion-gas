"""Pydantic schemas for strict MQTT payload validation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class MQTTReadingPayload(BaseModel):
    """Schema for sensors/+/data MQTT topic."""

    sensor_id: str = Field(..., min_length=1, max_length=64)
    readings: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(...)

    @field_validator("readings")
    @classmethod
    def validate_readings(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("readings must be a dict")
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("metadata must be a dict")
        return v


class MQTTStatusPayload(BaseModel):
    """Schema for sensors/+/status MQTT topic."""

    sensor_id: str = Field(..., min_length=1, max_length=64)
    status: Literal["online", "offline"] = Field(...)
    device_status: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = Field(None)

    @field_validator("device_status")
    @classmethod
    def validate_device_status(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("device_status must be a dict")
        return v


class MQTTCommandPayload(BaseModel):
    """Schema for gas/command/+/valve and gas/command/+/dissipator MQTT topics."""

    command: str = Field(..., min_length=1, max_length=32)
    state: str | None = Field(None, max_length=32)
    source: Literal["local", "remote", "panic"] = Field(default="remote")
    mode: Literal["manual", "automatic"] | None = Field(None)
    timestamp: str | None = Field(None)


class MQTTBridgeMessage(BaseModel):
    """Unified wrapper used by the MQTT→RabbitMQ bridge."""

    topic: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(...)
    received_at: datetime = Field(default_factory=datetime.utcnow)
