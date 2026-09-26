"""Standalone entrypoint for running the AGMARKNET continuous price ingestion worker.

Usage:
    python -m app.workers.ingestion
"""

import asyncio
import logging
import os
import signal
import sys

from app.config import get_settings
from app.db.session import Database
from app.logging_config import setup_structured_logging
from app.prices.consumer import ContinuousIngestionConsumer
from app.prices.feed import MandiFeed
from app.prices.ingest import PriceSink
from app.prices.repository import PriceObservationRepository
from app.telemetry.jetstream import get_jetstream_engine
from app.workers.base import WorkerLifecycleManager

logger = logging.getLogger("app.workers.ingestion")


async def main() -> None:
    settings = get_settings()
    setup_structured_logging(settings.log_level)
    logger.info("Initializing AGMARKNET Continuous Ingestion Worker (pid=%d)...", os.getpid())

    database = Database(settings.database_url)
    engine = get_jetstream_engine()
    feed = MandiFeed(
        api_key=settings.data_gov_api_key,
        resource_url=settings.data_gov_resource_url,
    )

    async def get_sink() -> PriceSink:
        return PriceObservationRepository(database.session_factory)

    consumer = ContinuousIngestionConsumer(
        engine=engine,
        feed=feed,
        sink_factory=get_sink,
    )
    await consumer.initialize()

    lifecycle = WorkerLifecycleManager(
        worker_name="ingestion",
        engine=engine,
        heartbeat_interval_seconds=10.0,
    )
    await lifecycle.start()

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        logger.info("Received termination signal in ingestion worker. Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _on_signal)
    else:
        signal.signal(signal.SIGINT, lambda *_: _on_signal())

    logger.info("Continuous Ingestion Worker running. Polling queue for AGMARKNET triggers...")

    # Main continuous polling loop
    try:
        while not stop_event.is_set():
            lifecycle.increment_in_flight()
            try:
                processed = await consumer.poll_and_process_next_batch(batch_size=5)
                lifecycle.decrement_in_flight(success=True)
                if not processed:
                    # Brief sleep when queue is empty
                    await asyncio.sleep(1.0)
            except Exception as loop_err:
                lifecycle.decrement_in_flight(success=False, error=str(loop_err))
                logger.exception("Error in ingestion consumer polling loop")
                await asyncio.sleep(2.0)
    finally:
        await lifecycle.stop(drain_timeout_seconds=15.0)
        await database.dispose()
        logger.info("Ingestion worker shutdown cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
