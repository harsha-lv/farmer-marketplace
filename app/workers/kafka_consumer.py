"""Standalone entrypoint for running the background Kafka event consumer worker.

Usage:
    python -m app.workers.kafka_consumer
"""

import asyncio
import logging
import signal
import sys

from app.config import get_settings
from app.db.session import Database
from app.events.consumers import BaseIdempotentEventConsumer
from app.events.schemas import (
    TOPIC_ASSAY_EVENTS,
    TOPIC_CONSENT_EVENTS,
    TOPIC_LOT_EVENTS,
    TOPIC_PRICE_EVENTS,
    TOPIC_SHIPMENT_EVENTS,
    TOPIC_TRADE_EVENTS,
)
from app.logging_config import setup_structured_logging

logger = logging.getLogger("app.workers.kafka_consumer")


async def main() -> None:
    settings = get_settings()
    setup_structured_logging(settings.log_level)
    logger.info("Initializing Kafka Consumer Worker (group_id=agri-platform-consumer-group)...")

    database = Database(settings.database_url)
    session_factory = database.session_factory

    topics = [
        TOPIC_CONSENT_EVENTS,
        TOPIC_TRADE_EVENTS,
        TOPIC_PRICE_EVENTS,
        TOPIC_LOT_EVENTS,
        TOPIC_ASSAY_EVENTS,
        TOPIC_SHIPMENT_EVENTS,
    ]

    consumer = BaseIdempotentEventConsumer(
        topics=topics,
        group_id="agri-platform-consumer-group",
        session_factory=session_factory,
        settings=settings,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_exit() -> None:
        logger.info("Received termination signal in kafka_consumer worker. Stopping...")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_exit)
    else:
        signal.signal(signal.SIGINT, lambda *_: _handle_exit())

    consumer_task = asyncio.create_task(consumer.run_forever())
    stop_task = asyncio.create_task(stop_event.wait())

    _done, pending = await asyncio.wait(
        [consumer_task, stop_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_event.is_set():
        await consumer.stop()

    for task in pending:
        task.cancel()

    await database.dispose()
    logger.info("Kafka consumer worker shutdown cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
