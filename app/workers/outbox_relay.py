"""Standalone entrypoint for running the transactional outbox relay worker.

Usage:
    python -m app.workers.outbox_relay
"""

import asyncio
import logging
import os
import signal
import sys

from app.config import get_settings
from app.db.session import Database
from app.events.kafka import KafkaProducerClient
from app.events.relay import OutboxRelayWorker
from app.logging_config import setup_structured_logging
from app.telemetry.jetstream import get_jetstream_engine
from app.workers.base import WorkerLifecycleManager

logger = logging.getLogger("app.workers.outbox_relay")


async def main() -> None:
    settings = get_settings()
    setup_structured_logging(settings.log_level)
    logger.info("Initializing Outbox Relay Worker (pid=%d)...", os.getpid())

    database = Database(settings.database_url)
    producer = KafkaProducerClient(settings)
    engine = get_jetstream_engine()

    worker = OutboxRelayWorker(
        session_factory=database.session_factory,
        producer=producer,
        settings=settings,
    )

    lifecycle = WorkerLifecycleManager(
        worker_name="outbox_relay",
        engine=engine,
        heartbeat_interval_seconds=10.0,
    )
    await lifecycle.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_signal() -> None:
        logger.info("Received termination signal in outbox_relay worker. Initiating graceful drain...")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _on_signal)
    else:
        signal.signal(signal.SIGINT, lambda *_: _on_signal())

    await worker.start()

    try:
        while not stop_event.is_set():
            lifecycle.increment_in_flight()
            try:
                processed = await worker.run_once()
                lifecycle.decrement_in_flight(success=True)
                if processed == 0:
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                    except TimeoutError:
                        pass
            except Exception as loop_err:
                lifecycle.decrement_in_flight(success=False, error=str(loop_err))
                logger.exception("Error in outbox relay cycle")
                await asyncio.sleep(2.0)
    finally:
        await lifecycle.stop(drain_timeout_seconds=15.0)
        await worker.stop()
        await database.dispose()
        logger.info("Outbox relay worker cleanly terminated.")


if __name__ == "__main__":
    asyncio.run(main())
