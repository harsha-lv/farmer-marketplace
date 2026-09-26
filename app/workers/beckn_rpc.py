"""Standalone entrypoint for running the Beckn RPC NATS worker.

Usage:
    python -m app.workers.beckn_rpc
"""

import asyncio
import logging
import signal
import sys

from app.config import get_settings
from app.db.session import Database
from app.logging_config import setup_structured_logging
from app.telemetry.jetstream import get_jetstream_engine
from app.telemetry.rpc import BecknRpcBroker
from app.workers.base import WorkerLifecycleManager

logger = logging.getLogger("app.workers.beckn_rpc")


async def main() -> None:
    settings = get_settings()
    setup_structured_logging(settings.log_level)
    logger.info("Initializing Beckn RPC Worker over NATS JetStream...")

    database = Database(settings.database_url)
    engine = get_jetstream_engine()
    _broker = BecknRpcBroker(engine=engine)

    lifecycle = WorkerLifecycleManager(
        worker_name="beckn_rpc",
        engine=engine,
        heartbeat_interval_seconds=10.0,
    )
    await lifecycle.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_exit() -> None:
        logger.info("Received termination signal in beckn_rpc worker. Initiating graceful drain...")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_exit)
    else:
        signal.signal(signal.SIGINT, lambda *_: _handle_exit())

    logger.info("Beckn RPC worker running and awaiting incoming NATS RPC requests...")

    try:
        await stop_event.wait()
    finally:
        await lifecycle.stop(drain_timeout_seconds=15.0)
        await database.dispose()
        logger.info("Beckn RPC worker shutdown cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
