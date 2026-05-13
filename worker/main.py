import asyncio
import signal
import sys

import structlog

logger = structlog.get_logger()


class WorkerManager:
    def __init__(self):
        self.running = True
        self.tasks = []

    async def start(self):
        logger.info("Starting GEUS Gas Detection Workers")

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

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
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Workers stopped")


async def main():
    manager = WorkerManager()
    await manager.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
