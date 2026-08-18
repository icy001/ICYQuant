"""ICYQuant Worker - Background task processor."""
from __future__ import annotations
import asyncio
import logging
import signal
import sys
from typing import Optional

from core.bootstrap import BootstrapManager, get_bootstrap
from core.settings import get_settings

logger = logging.getLogger(__name__)

class Worker:
    def __init__(self):
        self.bootstrap: BootstrapManager = get_bootstrap()
        self._running = False
        self._tasks: list = []

    async def start(self) -> None:
        await self.bootstrap.startup()
        self._running = True
        logger.info("Worker started")
        await self._run_loop()

    async def _run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        await self.bootstrap.shutdown()
        logger.info("Worker stopped")

async def run() -> None:
    worker = Worker()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))
        except NotImplementedError:
            pass
    
    await worker.start()

def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()