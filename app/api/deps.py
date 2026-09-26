from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import decode_jwt, extract_token_from_header
from app.auth.models import ApiClient
from app.auth.repository import AuthRepository
from app.auth.schemas import UserContext
from app.config import Settings
from app.db.session import Database


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is not None:
        return settings
    from app.config import get_settings as _get_settings
    return _get_settings()


def get_database(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if database is not None:
        return database
    settings = get_settings(request)
    return Database(settings.database_url)



async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = get_database(request)
    async with database.session_factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[Database, Depends(get_database)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Auth Dependencies
# ---------------------------------------------------------------------------


async def get_optional_user(
    request: Request,
    session: SessionDep,
) -> UserContext | None:
    """Extract and validate credentials from Authorization header or API key header.

    Supports:
      - Authorization: Bearer <jwt>
      - Authorization: token <jwt>
      - Authorization: ApiKey <api_key>
      - X-API-Key: <api_key>
    Returns None if no credentials are provided.
    """
    auth_header = request.headers.get("authorization")
    api_key_header = request.headers.get("x-api-key")

    # 1. Try API Key header
    if api_key_header:
        repo = AuthRepository(session)
        client = await repo.get_api_client_by_key(api_key_header.strip())
        if client:
            ctx = UserContext(
                client_id=client.client_id,
                scopes=[s.strip() for s in client.scopes.split(",") if s.strip()],
                rate_limit_tier=client.rate_limit_tier,
                is_api_client=True,
            )
            request.state.current_user = ctx
            request.state.current_api_client = client
            return ctx

    # 2. Try Authorization header
    if auth_header:
        header_val = auth_header.strip()

        # Check for ApiKey scheme
        if header_val.lower().startswith("apikey "):
            raw_key = header_val.split(" ", 1)[1].strip()
            repo = AuthRepository(session)
            client = await repo.get_api_client_by_key(raw_key)
            if client:
                ctx = UserContext(
                    client_id=client.client_id,
                    scopes=[s.strip() for s in client.scopes.split(",") if s.strip()],
                    rate_limit_tier=client.rate_limit_tier,
                    is_api_client=True,
                )
                request.state.current_user = ctx
                request.state.current_api_client = client
                return ctx
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        # Check for Bearer or token scheme
        token = extract_token_from_header(auth_header)
        if token:
            # If the token is actually an API key (e.g. ak_live_...)
            if token.startswith("ak_live_"):
                repo = AuthRepository(session)
                client = await repo.get_api_client_by_key(token)
                if client:
                    ctx = UserContext(
                        client_id=client.client_id,
                        scopes=[s.strip() for s in client.scopes.split(",") if s.strip()],
                        rate_limit_tier=client.rate_limit_tier,
                        is_api_client=True,
                    )
                    request.state.current_user = ctx
                    request.state.current_api_client = client
                    return ctx
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                )

            # Standard JWT token
            try:
                payload = decode_jwt(token)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid or expired token: {err}",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err

            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type: expected access token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            ctx = UserContext(
                user_id=int(payload["sub"]),
                email=payload.get("email"),
                phone=payload.get("phone"),
                roles=payload.get("roles", []),
                org_id=payload.get("org_id"),
                is_api_client=False,
            )
            request.state.current_user = ctx
            return ctx

    return None


async def get_current_user(
    request: Request,
    optional_user: Annotated[UserContext | None, Depends(get_optional_user)],
) -> UserContext:
    """Require an authenticated human user (non-API client)."""
    if optional_user is None or optional_user.is_api_client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return optional_user


async def get_current_auth(
    request: Request,
    optional_user: Annotated[UserContext | None, Depends(get_optional_user)],
) -> UserContext:
    """Require authentication by either a user or an API client."""
    if optional_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return optional_user


async def get_current_api_client(
    request: Request,
    session: SessionDep,
) -> ApiClient:
    """Require authentication via API key."""
    api_key = request.headers.get("x-api-key")
    if not api_key:
        auth_header = request.headers.get("authorization")
        if auth_header:
            token = extract_token_from_header(auth_header)
            if token and token.startswith("ak_live_"):
                api_key = token
            elif auth_header.strip().lower().startswith("apikey "):
                api_key = auth_header.strip().split(" ", 1)[1].strip()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key header (X-API-Key)",
        )

    repo = AuthRepository(session)
    client = await repo.get_api_client_by_key(api_key.strip())
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    request.state.current_api_client = client
    return client


def require_roles(*roles: str):
    """Enforce that the current user has at least one of the specified roles.

    Admins always bypass role restrictions.
    """
    async def role_checker(
        current_user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        if not current_user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: requires one of {list(roles)} roles",
            )
        return current_user

    return role_checker


def require_scopes(*scopes: str):
    """Enforce that the current user or API client has all specified scopes."""
    async def scope_checker(
        auth_ctx: Annotated[UserContext, Depends(get_current_auth)],
    ) -> UserContext:
        if not auth_ctx.has_scope(*scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: missing required scopes {list(scopes)}",
            )
        return auth_ctx

    return scope_checker


def require_org_access(org_param_name: str = "org_id"):
    """Enforce tenant scoping — user can only access their own org/FPO data."""
    async def org_checker(
        request: Request,
        current_user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        if current_user.has_role("admin"):
            return current_user

        target_org = (
            request.path_params.get(org_param_name)
            or request.query_params.get(org_param_name)
            or request.headers.get("x-fpo-id")
            or request.headers.get("x-org-id")
        )

        if target_org and not current_user.has_org_access(target_org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant access denied: cross-tenant access to org '{target_org}' is forbidden",
            )
        return current_user

    return org_checker


CurrentUserDep = Annotated[UserContext, Depends(get_current_user)]
CurrentAuthDep = Annotated[UserContext, Depends(get_current_auth)]
OptionalUserDep = Annotated[UserContext | None, Depends(get_optional_user)]
ApiClientDep = Annotated[ApiClient, Depends(get_current_api_client)]
