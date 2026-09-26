"""Base utilities for standalone worker daemons.

Provides:
- Structured startup logging
- SIGTERM/SIGINT graceful shutdown and in-flight request draining
- Periodic heartbeat publishing on NATS JetStream status subject
- Periodic status file export (for Kubernetes/systemd liveness probes)
- Lightweight embedded /healthz HTTP status server
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.telemetry.jetstream import NatsJetStreamEngine, get_jetstream_engine

logger = logging.getLogger("app.workers.base")


class WorkerLifecycleManager:
    """Manages worker startup, heartbeat publishing, status file generation, and graceful drain."""

    def __init__(
        self,
        worker_name: str,
        engine: NatsJetStreamEngine | None = None,
        heartbeat_interval_seconds: float = 10.0,
        status_port: int | None = None,
    ) -> None:
        self.worker_name = worker_name
        self.engine = engine or get_jetstream_engine()
        self.heartbeat_interval = heartbeat_interval_seconds
        self.status_port = status_port

        self.start_time = time.time()
        self.running = False
        self.draining = False
        self.in_flight_count = 0
        self.processed_total = 0
        self.last_error: str | None = None

        self._stop_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._server: Any = None

        # Resolve status file location in temp directory
        temp_dir = Path(tempfile.gettempdir())
        self.status_file_path = temp_dir / f"worker_{worker_name}_status.json"

    def increment_in_flight(self) -> None:
        self.in_flight_count += 1

    def decrement_in_flight(self, success: bool = True, error: str | None = None) -> None:
        self.in_flight_count = max(0, self.in_flight_count - 1)
        self.processed_total += 1
        if not success and error:
            self.last_error = error

    def get_status_payload(self) -> dict[str, Any]:
        """Generate current worker status dictionary."""
        status = "STOPPED"
        if self.running:
            status = "DRAINING" if self.draining else "RUNNING"

        uptime = round(time.time() - self.start_time, 2)
        return {
            "worker": self.worker_name,
            "status": status,
            "pid": os.getpid(),
            "uptime_seconds": uptime,
            "in_flight": self.in_flight_count,
            "processed_total": self.processed_total,
            "last_error": self.last_error,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def write_status_file(self) -> None:
        """Write current status payload to filesystem."""
        try:
            payload = self.get_status_payload()
            with open(self.status_file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.debug("Could not write worker status file: %s", exc)

    async def _heartbeat_loop(self) -> None:
        """Publish periodic heartbeat to NATS status subject and update status file."""
        subject = f"agri.system.workers.heartbeat.{self.worker_name}"
        while self.running and not self._stop_event.is_set():
            try:
                payload = self.get_status_payload()
                self.write_status_file()
                await self.engine.publish(
                    subject=subject,
                    payload=payload,
                    msg_id=f"hb_{self.worker_name}_{int(time.time())}",
                )
            except Exception as exc:
                logger.debug("Heartbeat publish failed (%s): %s", subject, exc)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.heartbeat_interval)
            except TimeoutError:
                pass

    async def _handle_http_healthz(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Minimal non-blocking /healthz HTTP responder."""
        try:
            line = await reader.readline()
            if line:
                payload = self.get_status_payload()
                body = json.dumps(payload).encode("utf-8")
                code = "200 OK" if (self.running and not self.draining) else "503 Service Unavailable"
                response = (
                    f"HTTP/1.1 {code}\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                writer.write(response)
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> None:
        """Initialize worker monitoring, start heartbeat loop and status server."""
        self.running = True
        self.draining = False
        self.write_status_file()

        # Start status server if port specified
        if self.status_port is not None:
            try:
                self._server = await asyncio.start_server(
                    self._handle_http_healthz, "0.0.0.0", self.status_port
                )
                logger.info(
                    "Worker %s status endpoint listening on http://0.0.0.0:%d/healthz",
                    self.worker_name,
                    self.status_port,
                )
            except Exception as exc:
                logger.warning("Could not bind status port %d: %s", self.status_port, exc)

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(
            "Worker '%s' started (pid=%d, status_file=%s)",
            self.worker_name,
            os.getpid(),
            self.status_file_path,
        )

    async def stop(self, drain_timeout_seconds: float = 15.0) -> None:
        """Signal drain, wait for in-flight requests to complete, and shut down cleanly."""
        logger.info(
            "Initiating graceful drain for worker '%s' (in_flight=%d, max_wait=%.1fs)...",
            self.worker_name,
            self.in_flight_count,
            drain_timeout_seconds,
        )
        self.draining = True
        self._stop_event.set()

        # Wait for in-flight requests to drain
        deadline = time.time() + drain_timeout_seconds
        while self.in_flight_count > 0 and time.time() < deadline:
            await asyncio.sleep(0.2)

        if self.in_flight_count > 0:
            logger.warning(
                "Worker '%s' drain timed out with %d operations still in-flight.",
                self.worker_name,
                self.in_flight_count,
            )
        else:
            logger.info("Worker '%s' in-flight operations drained successfully.", self.worker_name)

        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        self.write_status_file()
        logger.info("Worker '%s' cleanly terminated.", self.worker_name)
