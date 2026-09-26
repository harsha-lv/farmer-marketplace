"""Production-grade security and structured logging middleware for FastAPI."""

# Export foundation middleware from app/middleware.py
import importlib.util
from pathlib import Path

from app.middleware.logging import StructuredLoggingMiddleware
from app.middleware.security import (
    RateLimitMiddleware,
    RequestSizeLimiterMiddleware,
    SecurityHeadersMiddleware,
    SecurityMiddleware,
    limiter,
)

_middleware_py = Path(__file__).parent.parent / "middleware.py"
if _middleware_py.exists():
    _spec = importlib.util.spec_from_file_location("app._middleware_module", _middleware_py)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr in [
            "DEFAULT_CORS_ORIGINS",
            "JSONLogFormatter",
            "RequestIDMiddleware",
            "configure_cors",
            "request_id_ctx",
            "setup_structured_logging",
        ]:
            if hasattr(_mod, _attr):
                globals()[_attr] = getattr(_mod, _attr)

__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "JSONLogFormatter",
    "RateLimitMiddleware",
    "RequestIDMiddleware",
    "RequestSizeLimiterMiddleware",
    "SecurityHeadersMiddleware",
    "SecurityMiddleware",
    "StructuredLoggingMiddleware",
    "configure_cors",
    "limiter",
    "request_id_ctx",
    "setup_structured_logging",
]
