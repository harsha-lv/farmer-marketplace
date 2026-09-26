"""FastAPI router for authentication, profile management, and API client administration."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_roles,
)
from app.auth.crypto import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    hash_token,
    verify_password,
)
from app.auth.otp import (
    generate_otp_code,
    get_otp_provider,
    hash_otp_code,
    normalize_and_validate_indian_phone,
    verify_otp_hash,
)
from app.auth.rate_limiter import (
    check_login_rate_limit,
    check_refresh_rate_limit,
    get_client_ip,
)
from app.auth.repository import AuthRepository
from app.auth.schemas import (
    ApiClientCreatedResponse,
    ApiClientCreateRequest,
    ApiClientResponse,
    ApiClientRotateResponse,
    ChangePasswordRequest,
    OtpSendRequest,
    OtpSendResponse,
    OtpUserResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserProfileResponse,
    UserRegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# OTP Phone Authentication Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/otp/send",
    response_model=OtpSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Send OTP to Indian mobile number for passwordless login",
)
async def send_otp(
    payload: OtpSendRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OtpSendResponse:
    # 1. Validate & normalize Indian mobile number
    try:
        normalized_phone = normalize_and_validate_indian_phone(payload.phone_number)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    client_ip = get_client_ip(request)
    repo = AuthRepository(session)

    # 2. Rate limiting check (max 3/phone/hr, max 10/ip/hr)
    allowed, retry_after = await repo.check_otp_rate_limit(normalized_phone, client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Generate cryptographic 6-digit code and secure hash
    code = generate_otp_code()
    code_hash = hash_otp_code(code, settings.otp_pepper)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.otp_ttl_seconds)

    # 4. Invalidate previous challenges & persist new challenge
    await repo.create_otp_challenge(
        phone_number=normalized_phone,
        code_hash=code_hash,
        purpose="login",
        expires_at=expires_at,
        request_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    # 5. Audit log
    await repo.write_audit_log(
        actor_id=normalized_phone,
        actor_type="phone",
        action="otp_send",
        resource_type="otp_challenge",
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )
    await session.commit()

    # 6. Deliver OTP via configured provider
    provider = get_otp_provider(settings)
    await provider.send_otp(normalized_phone, code)

    return OtpSendResponse(
        success=True,
        message="OTP sent",
        expires_in=settings.otp_ttl_seconds,
        retry_after=30,
    )


@router.post(
    "/otp/verify",
    response_model=OtpVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP code and issue JWT credentials",
)
async def verify_otp(
    payload: OtpVerifyRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> OtpVerifyResponse:
    # 1. Validate & normalize Indian mobile number
    try:
        normalized_phone = normalize_and_validate_indian_phone(payload.phone_number)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    client_ip = get_client_ip(request)
    repo = AuthRepository(session)
    now = datetime.now(UTC)

    # 2. Retrieve latest unconsumed challenge
    challenge = await repo.get_latest_otp_challenge(normalized_phone)
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP challenge found. Please request a new OTP.",
        )

    # 3. Check attempt lockouts
    if challenge.attempts >= challenge.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many invalid attempts. Account temporarily locked for {settings.otp_lockout_seconds // 60} minutes. Request a new OTP.",
            headers={"Retry-After": str(settings.otp_lockout_seconds)},
        )

    # 4. Check expiration (HTTP 410 Gone)
    if now >= challenge.expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="OTP expired. Please request a new one.",
        )

    # 5. Constant-time hash verification
    if not verify_otp_hash(payload.otp_code, challenge.code_hash, settings.otp_pepper):
        challenge.attempts += 1
        await repo.write_audit_log(
            actor_id=normalized_phone,
            actor_type="phone",
            action="otp_verify_failed",
            resource_type="otp_challenge",
            resource_id=str(challenge.id),
            ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
            details={"attempts": challenge.attempts},
        )
        await session.commit()
        if challenge.attempts >= challenge.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Maximum attempts exceeded. Account locked for {settings.otp_lockout_seconds // 60} minutes.",
                headers={"Retry-After": str(settings.otp_lockout_seconds)},
            )
        remaining = challenge.max_attempts - challenge.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP code. {remaining} attempt(s) remaining.",
        )

    # 6. Consume challenge
    challenge.consumed_at = now

    # 7. Find or create user
    user, is_new = await repo.find_or_create_otp_user(normalized_phone)
    roles = [r.role.name for r in user.roles]

    # 8. Generate JWT tokens
    access_token = create_access_token(
        user_id=user.id,
        roles=roles,
        phone=user.phone,
        org_id=user.fpo_id,
    )
    raw_refresh, family_id, refresh_exp = create_refresh_token(user_id=user.id)
    refresh_hash = hash_token(raw_refresh)
    await repo.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_hash,
        family_id=family_id,
        expires_at=refresh_exp,
    )

    # 9. Audit log
    await repo.write_audit_log(
        actor_id=str(user.id),
        actor_type="user",
        action="otp_verify_success",
        resource_type="user",
        resource_id=str(user.id),
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        details={"is_new_user": is_new, "family_id": family_id},
    )
    await session.commit()

    return OtpVerifyResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=OtpUserResponse(
            id=user.id,
            phone_number=user.phone or normalized_phone,
            roles=roles,
            profile_complete=bool(user.profile_complete),
        ),
    )


# ---------------------------------------------------------------------------
# Public Auth Endpoints
# ---------------------------------------------------------------------------



@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new platform user",
)
async def register(
    payload: UserRegisterRequest,
    request: Request,
    session: SessionDep,
) -> UserProfileResponse:
    repo = AuthRepository(session)

    # Check uniqueness of email or phone
    identifier = payload.email or payload.phone
    if identifier:
        existing = await repo.get_user_by_identifier(identifier)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with identifier '{identifier}' already exists",
            )

    password_hash = hash_password(payload.password)
    user = await repo.create_user(
        email=payload.email,
        phone=payload.phone,
        password_hash=password_hash,
        role_names=payload.roles or ["farmer"],
        fpo_id=payload.fpo_id,
    )
    await session.commit()

    # Audit logging
    await repo.write_audit_log(
        actor_id=str(user.id),
        actor_type="user",
        action="user_registered",
        resource_type="user",
        resource_id=str(user.id),
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        details={"roles": [r.role.name for r in user.roles], "fpo_id": user.fpo_id},
    )
    await session.commit()

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        status=user.status,
        fpo_id=user.fpo_id,
        roles=[r.role.name for r in user.roles],
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login via OAuth2 password flow or JSON credentials",
)
async def login(
    request: Request,
    session: SessionDep,
) -> TokenResponse:
    # 1. Parse body (supports JSON or form-encoded OAuth2PasswordRequestForm)
    content_type = request.headers.get("content-type", "")
    username: str | None = None
    password: str | None = None

    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
    else:
        try:
            body = await request.json()
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request body. Expected JSON or Form URL-encoded.",
            )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both username and password are required.",
        )

    # 2. Rate limiting by IP and Account
    await check_login_rate_limit(request, account_identifier=username)

    # 3. Look up user
    repo = AuthRepository(session)
    user = await repo.get_user_by_identifier(username)

    if not user or not verify_password(password, user.password_hash):
        await repo.write_audit_log(
            actor_id=username,
            actor_type="anonymous",
            action="login_failed",
            ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
            details={"reason": "invalid_credentials"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status}",
        )

    roles = [r.role.name for r in user.roles]

    # 4. Generate Tokens
    access_token = create_access_token(
        user_id=user.id,
        roles=roles,
        org_id=user.fpo_id,
        email=user.email,
        phone=user.phone,
    )
    raw_refresh_token, family_id, refresh_expires_at = create_refresh_token(user_id=user.id)

    # 5. Store Refresh Token
    refresh_hash = hash_token(raw_refresh_token)
    await repo.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_hash,
        family_id=family_id,
        expires_at=refresh_expires_at,
    )

    # 6. Audit Log
    await repo.write_audit_log(
        actor_id=str(user.id),
        actor_type="user",
        action="login_success",
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        details={"family_id": family_id},
    )
    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=900,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new access token (with reuse detection)",
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    request: Request,
    session: SessionDep,
) -> TokenResponse:
    # 1. Rate limiting by IP
    await check_refresh_rate_limit(request)

    raw_token = payload.refresh_token.strip()
    try:
        token_claims = decode_jwt(raw_token)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {err}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    if token_claims.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token type must be 'refresh'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(token_claims["sub"])
    family_id = token_claims.get("family_id")
    old_hash = hash_token(raw_token)

    repo = AuthRepository(session)
    user = await repo.get_user_by_id(user_id)
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new refresh token under the same family
    new_raw_refresh, _, new_expires_at = create_refresh_token(user_id=user.id, family_id=family_id)
    new_hash = hash_token(new_raw_refresh)

    try:
        await repo.rotate_refresh_token(
            old_token_hash=old_hash,
            new_token_hash=new_hash,
            new_expires_at=new_expires_at,
        )
    except ValueError as err:
        await session.commit()
        # REUSE DETECTED OR EXPIRED
        await repo.write_audit_log(
            actor_id=str(user_id),
            actor_type="user",
            action="token_reuse_detected",
            ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
            details={"error": str(err), "family_id": family_id},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    # Create new access token
    roles = [r.role.name for r in user.roles]
    new_access_token = create_access_token(
        user_id=user.id,
        roles=roles,
        org_id=user.fpo_id,
        email=user.email,
        phone=user.phone,
    )

    await session.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=900,
    )


@router.post(
    "/logout",
    summary="Revoke active refresh tokens for the current user or family",
)
async def logout(
    request: Request,
    current_user: CurrentUserDep,
    session: SessionDep,
    payload: RefreshTokenRequest | None = None,
) -> dict[str, str]:
    repo = AuthRepository(session)
    if payload and payload.refresh_token:
        try:
            claims = decode_jwt(payload.refresh_token)
            family_id = claims.get("family_id")
            if family_id:
                await repo.revoke_family(family_id)
        except Exception:
            pass

    await repo.write_audit_log(
        actor_id=str(current_user.user_id),
        actor_type="user",
        action="user_logout",
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )
    await session.commit()
    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> UserProfileResponse:
    repo = AuthRepository(session)
    user = await repo.get_user_by_id(current_user.user_id)  # type: ignore[arg-type]
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        status=user.status,
        fpo_id=user.fpo_id,
        roles=[r.role.name for r in user.roles],
        created_at=user.created_at,
    )


@router.post(
    "/change-password",
    summary="Change current authenticated user's password",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserDep,
    request: Request,
    session: SessionDep,
) -> dict[str, str]:
    repo = AuthRepository(session)
    user = await repo.get_user_by_id(current_user.user_id)  # type: ignore[arg-type]
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    new_hash = hash_password(payload.new_password)
    await repo.update_password(user.id, new_hash)

    await repo.write_audit_log(
        actor_id=str(user.id),
        actor_type="user",
        action="password_changed",
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )
    await session.commit()
    return {"message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# Admin API-Client CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/clients",
    response_model=ApiClientCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new API client (Admin only)",
    dependencies=[Depends(require_roles("admin"))],
)
async def create_api_client(
    payload: ApiClientCreateRequest,
    request: Request,
    session: SessionDep,
) -> ApiClientCreatedResponse:
    repo = AuthRepository(session)
    client, plain_key = await repo.create_api_client(
        name=payload.name,
        scopes=payload.scopes,
        allowed_origins=payload.allowed_origins,
        rate_limit_tier=payload.rate_limit_tier,
        expires_days=payload.expires_days,
    )

    await repo.write_audit_log(
        actor_id=str(request.state.current_user.user_id),
        actor_type="user",
        action="api_client_created",
        resource_type="api_client",
        resource_id=client.client_id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        details={"name": client.name, "scopes": payload.scopes},
    )
    await session.commit()

    return ApiClientCreatedResponse(
        client_id=client.client_id,
        name=client.name,
        api_key=plain_key,
        key_prefix=client.key_prefix,
        scopes=[s.strip() for s in client.scopes.split(",") if s.strip()],
        allowed_origins=[o.strip() for o in client.allowed_origins.split(",") if o.strip()],
        rate_limit_tier=client.rate_limit_tier,
        status=client.status,
        expires_at=client.expires_at,
        created_at=client.created_at,
    )


@router.get(
    "/clients",
    response_model=list[ApiClientResponse],
    summary="List all registered API clients (Admin only)",
    dependencies=[Depends(require_roles("admin"))],
)
async def list_api_clients(
    session: SessionDep,
) -> list[ApiClientResponse]:
    repo = AuthRepository(session)
    clients = await repo.list_api_clients()
    return [
        ApiClientResponse(
            client_id=c.client_id,
            name=c.name,
            key_prefix=c.key_prefix,
            scopes=[s.strip() for s in c.scopes.split(",") if s.strip()],
            allowed_origins=[o.strip() for o in c.allowed_origins.split(",") if o.strip()],
            rate_limit_tier=c.rate_limit_tier,
            status=c.status,
            rotated_at=c.rotated_at,
            expires_at=c.expires_at,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.post(
    "/clients/{client_id}/rotate",
    response_model=ApiClientRotateResponse,
    summary="Rotate API client key (Admin only)",
    dependencies=[Depends(require_roles("admin"))],
)
async def rotate_api_client(
    client_id: str,
    request: Request,
    session: SessionDep,
) -> ApiClientRotateResponse:
    repo = AuthRepository(session)
    try:
        client, plain_key = await repo.rotate_api_client_key(client_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    await repo.write_audit_log(
        actor_id=str(request.state.current_user.user_id),
        actor_type="user",
        action="api_client_rotated",
        resource_type="api_client",
        resource_id=client.client_id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )
    await session.commit()

    return ApiClientRotateResponse(
        client_id=client.client_id,
        api_key=plain_key,
        key_prefix=client.key_prefix,
        rotated_at=client.rotated_at or datetime.now(UTC),
    )


@router.delete(
    "/clients/{client_id}",
    summary="Revoke API client access (Admin only)",
    dependencies=[Depends(require_roles("admin"))],
)
async def revoke_api_client(
    client_id: str,
    request: Request,
    session: SessionDep,
) -> dict[str, str]:
    repo = AuthRepository(session)
    try:
        client = await repo.revoke_api_client(client_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    await repo.write_audit_log(
        actor_id=str(request.state.current_user.user_id),
        actor_type="user",
        action="api_client_revoked",
        resource_type="api_client",
        resource_id=client.client_id,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )
    await session.commit()
    return {"message": f"Client {client_id} successfully revoked"}
