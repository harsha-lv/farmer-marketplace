"""Events module for event-sourcing, transactional outbox, and audit logging."""

from app.events.models import OutboxEvent

__all__ = ["OutboxEvent"]
