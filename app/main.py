import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.infrastructure.api.routes import (
    alerts,
    audit,
    auth,
    commands,
    config,
    health,
    notifications,
    sensors,
    users,
)
from app.infrastructure.database.connection import AsyncSessionLocal, close_db, init_db
from app.infrastructure.messaging.mqtt_client import mqtt_client
from app.infrastructure.messaging.rabbitmq_client import rabbitmq_client


class AppSettings(BaseSettings):
    app_name: str = "GEUS Gas Detection System"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    class Config:
        env_file = ".env"


settings = AppSettings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.utcnow()

        timestamps = self._requests[client_ip]
        timestamps[:] = [ts for ts in timestamps if (now - ts).total_seconds() < self.window_seconds]

        if len(timestamps) >= self.max_requests:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        timestamps.append(now)
        return await call_next(request)


async def _expire_test_mode_task():
    logger = structlog.get_logger()
    while True:
        await asyncio.sleep(60)
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.utcnow()
                result = await session.execute(
                    text(
                        """
                        UPDATE sensors
                        SET test_mode = false,
                            test_mode_expires_at = NULL,
                            updated_at = :now
                        WHERE test_mode = true
                          AND test_mode_expires_at < :now
                        """
                    ),
                    {"now": now},
                )
                await session.commit()
                affected = result.rowcount
                if affected:
                    logger.info("test_mode_expired", sensors_affected=affected)
        except Exception as e:
            logger.error("test_mode_expiration_check_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = structlog.get_logger()

    await init_db()

    try:
        await rabbitmq_client.connect()
    except Exception as e:
        logger.error("rabbitmq_startup_failed", error=str(e))

    try:
        await mqtt_client.connect()
    except Exception as e:
        logger.error("mqtt_startup_failed", error=str(e))

    test_mode_task = asyncio.create_task(_expire_test_mode_task())

    yield

    test_mode_task.cancel()
    try:
        await test_mode_task
    except asyncio.CancelledError:
        pass

    try:
        await rabbitmq_client.close()
    except Exception:
        pass

    try:
        await mqtt_client.close()
    except Exception:
        pass

    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

origins = settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sensors.router)
app.include_router(alerts.router)
app.include_router(commands.router)
app.include_router(notifications.router)
app.include_router(audit.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
