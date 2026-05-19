import asyncio
import os
import signal
import sys

import structlog
from aiohttp import web

from worker.alert_handler.consumer import AlertHandlerConsumer
from worker.data_collector.consumer import DataCollectorConsumer
from worker.gas_detection.consumer import GasDetectionConsumer
from worker.shared.database import worker_db

logger = structlog.get_logger()
HEALTH_PORT = int(os.getenv("WORKER_HEALTH_PORT", "8080"))


class WorkerManager:
    def __init__(self):
        self.running = True
        self.tasks = []
        self.consumers = [
            DataCollectorConsumer(),
            GasDetectionConsumer(),
            AlertHandlerConsumer(),
        ]

    async def start(self):
        logger.info("Starting GEUS Gas Detection Workers")

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        # Iniciar healthcheck HTTP en background
        health_task = asyncio.create_task(self._start_health_server())
        self.tasks.append(health_task)

        for consumer in self.consumers:
            task = asyncio.create_task(consumer.start())
            self.tasks.append(task)
            logger.info(f"Started {consumer.__class__.__name__}")

        try:
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error("Worker error", error=str(e))
        finally:
            await self.shutdown()

    def handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received", signal=signum)
        self.running = False

    async def shutdown(self):
        logger.info("Shutting down workers")
        for consumer in self.consumers:
            await consumer.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Workers stopped")

    async def _health(self, request: web.Request) -> web.Response:
        checks = {}

        # RabbitMQ
        rabbitmq_ok = False
        for c in self.consumers:
            if hasattr(c, "rabbitmq") and c.rabbitmq.connection:
                rabbitmq_ok = not c.rabbitmq.connection.is_closed
                break
        checks["rabbitmq"] = rabbitmq_ok

        # MQTT
        mqtt_ok = False
        for c in self.consumers:
            if hasattr(c, "mqtt") and c.mqtt.client:
                mqtt_ok = True
                break
        checks["mqtt"] = mqtt_ok

        # PostgreSQL (con timeout para evitar healthcheck colgado)
        postgres_ok = False
        try:
            if worker_db.pool:
                await asyncio.wait_for(worker_db.fetchrow("SELECT 1"), timeout=5.0)
                postgres_ok = True
        except TimeoutError:
            logger.warning("healthcheck_postgres_timeout")
        except Exception:
            pass
        checks["postgres"] = postgres_ok

        checks["running"] = self.running
        all_ok = all(checks.values())
        status = 200 if all_ok else 503
        return web.json_response(checks, status=status)

    async def _start_health_server(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
        await site.start()
        logger.info("health_server_started", port=HEALTH_PORT)

        while self.running:
            await asyncio.sleep(1)

        await runner.cleanup()
        logger.info("health_server_stopped")


async def main():
    manager = WorkerManager()
    await manager.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
