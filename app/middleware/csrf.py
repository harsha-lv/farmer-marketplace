"""CSRF Protection Middleware using X-XSRF-Token Double-Submit Cookie Pattern."""

import hmac
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Methods that modify state and require CSRF validation when cookie-authenticated
MUTATING_METHODS = frozenset(["POST", "PUT", "PATCH", "DELETE"])

# Cookie names that signify a browser session / cookie-authenticated request
SESSION_COOKIE_NAMES = frozenset(["session", "access_token", "refresh_token", "jwt", "auth_token"])

# Paths that are public authentication onboarding where user doesn't have a session cookie yet
PUBLIC_EXEMPT_PATHS = frozenset([
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/beckn/",
    "/health",
    "/ready",
    "/healthz",
])


class CSRFDoubleSubmitMiddleware(BaseHTTPMiddleware):
    """Enforces Double-Submit Cookie CSRF protection for browser-based session requests.

    - If the request includes an authentication/session cookie or an XSRF-TOKEN cookie,
      and is a mutating HTTP method (POST, PUT, PATCH, DELETE):
      it MUST include a matching 'X-XSRF-Token' header.
    - Pure API requests using 'Authorization: Bearer' or 'X-API-Key' without session cookies
      are exempt.
    """

    def __init__(
        self,
        app: Any,
        cookie_name: str = "XSRF-TOKEN",
        header_name: str = "X-XSRF-Token",
    ) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Check if exempt path
        if any(path.startswith(exempt) for exempt in PUBLIC_EXEMPT_PATHS):
            return await call_next(request)

        # Check if mutating request
        if request.method in MUTATING_METHODS:
            cookies = request.cookies
            has_session_cookie = any(name in cookies for name in SESSION_COOKIE_NAMES)
            xsrf_cookie = cookies.get(self.cookie_name)

            # If browser authentication cookie or XSRF cookie is present
            if has_session_cookie or xsrf_cookie:
                # Look for header (case-insensitive)
                xsrf_header = request.headers.get(self.header_name) or request.headers.get(self.header_name.lower())

                if not xsrf_cookie or not xsrf_header:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Forbidden",
                            "detail": "CSRF validation failed: missing XSRF cookie or X-XSRF-Token header.",
                        },
                    )

                if not hmac.compare_digest(xsrf_cookie.strip(), xsrf_header.strip()):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Forbidden",
                            "detail": "CSRF validation failed: token mismatch.",
                        },
                    )

        response = await call_next(request)
        return response
