from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

from app.infrastructure.api.routes import alerts, audit, auth, commands, config, health, sensors, users
from app.infrastructure.database.connection import close_db, init_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await rabbitmq_client.connect()
    await mqtt_client.connect()
    
    yield
    
    await rabbitmq_client.close()
    await mqtt_client.close()
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

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sensors.router)
app.include_router(alerts.router)
app.include_router(commands.router)
app.include_router(audit.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
