from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.messaging.mqtt_client import mqtt_client
from app.infrastructure.messaging.rabbitmq_client import rabbitmq_client
from app.infrastructure.telemetry.influx_client import influx_client

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "geus-gas-detection-api"}


@router.get("/health/ready")
async def readiness_check(session: AsyncSession = Depends(get_current_session)):
    checks = {
        "database": False,
        "rabbitmq": False,
        "mqtt": False,
        "influxdb": False,
    }
    
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    
    try:
        checks["rabbitmq"] = rabbitmq_client.connection is not None and not rabbitmq_client.connection.is_closed
    except Exception:
        pass
    
    try:
        checks["mqtt"] = mqtt_client.client is not None
    except Exception:
        pass
    
    try:
        checks["influxdb"] = influx_client.client is not None
    except Exception:
        pass
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks,
    }
