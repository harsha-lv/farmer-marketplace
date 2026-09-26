"""Database repository for authentication, authorization, and audit persistence."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.crypto import generate_api_key, hash_token, utcnow
from app.auth.models import (
    ApiClient,
    AuditLog,
    OtpChallenge,
    RefreshToken,
    Role,
    User,
    UserRole,
)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_user_by_identifier(self, identifier: str) -> User | None:
        """Find user by email or phone number."""
        stmt = (
            select(User)
            .where((User.email == identifier) | (User.phone == identifier))
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create_role(self, role_name: str) -> Role:
        stmt = select(Role).where(Role.name == role_name)
        result = await self.session.execute(stmt)
        role = result.scalars().first()
        if not role:
            role = Role(name=role_name, description=f"{role_name} role")
            self.session.add(role)
            await self.session.flush()
        return role

    async def create_user(
        self,
        email: str | None,
        phone: str | None,
        password_hash: str,
        role_names: list[str],
        fpo_id: str | None = None,
    ) -> User:
        user = User(
            email=email,
            phone=phone,
            password_hash=password_hash,
            status="active",
            fpo_id=fpo_id,
        )
        self.session.add(user)
        await self.session.flush()

        for role_name in role_names:
            role = await self.get_or_create_role(role_name)
            user_role = UserRole(user_id=user.id, role_id=role.id, org_id=fpo_id)
            self.session.add(user_role)

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_password(self, user_id: int, new_password_hash: str) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_password_hash, updated_at=utcnow())
        )
        await self.session.execute(stmt)

    async def store_refresh_token(
        self,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            token_hash=token_hash,
            user_id=user_id,
            family_id=family_id,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def revoke_family(self, family_id: str) -> None:
        """Revoke all tokens in a family (used when reuse is detected)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)

    async def rotate_refresh_token(
        self,
        old_token_hash: str,
        new_token_hash: str,
        new_expires_at: datetime,
    ) -> tuple[RefreshToken, str]:
        """Rotate a refresh token.

        Detects reuse: if old token was already revoked or used, revokes the whole family
        and raises ValueError.
        """
        old_token = await self.get_refresh_token(old_token_hash)
        if not old_token:
            raise ValueError("Refresh token not found")

        family_id = old_token.family_id
        if old_token.is_revoked or old_token.used_at is not None:
            # REUSE DETECTED: Revoke the entire family
            await self.revoke_family(family_id)
            raise ValueError("Refresh token reuse detected: token family revoked")

        if ensure_utc(old_token.expires_at) < utcnow():
            old_token.is_revoked = True
            raise ValueError("Refresh token expired")

        # Invalidate old token
        old_token.used_at = utcnow()
        old_token.is_revoked = True

        # Create new token under same family
        new_token = RefreshToken(
            token_hash=new_token_hash,
            user_id=old_token.user_id,
            family_id=family_id,
            expires_at=new_expires_at,
            is_revoked=False,
        )
        self.session.add(new_token)
        await self.session.flush()
        return new_token, family_id

    # -----------------------------------------------------------------------
    # API Client Management
    # -----------------------------------------------------------------------

    async def create_api_client(
        self,
        name: str,
        scopes: list[str],
        allowed_origins: list[str],
        rate_limit_tier: str = "standard",
        expires_days: int | None = None,
    ) -> tuple[ApiClient, str]:
        plain_key, key_prefix, hashed_key = generate_api_key()
        client_id = f"client_{uuid.uuid4().hex[:16]}"
        expires_at = utcnow() + timedelta(days=expires_days) if expires_days else None

        client = ApiClient(
            client_id=client_id,
            name=name,
            hashed_api_key=hashed_key,
            key_prefix=key_prefix,
            scopes=",".join(scopes),
            allowed_origins=",".join(allowed_origins),
            rate_limit_tier=rate_limit_tier,
            status="active",
            expires_at=expires_at,
        )
        self.session.add(client)
        await self.session.flush()
        return client, plain_key

    async def get_api_client_by_key(self, raw_api_key: str) -> ApiClient | None:
        hashed = hash_token(raw_api_key)
        stmt = select(ApiClient).where(
            ApiClient.hashed_api_key == hashed,
            ApiClient.status == "active",
        )
        result = await self.session.execute(stmt)
        client = result.scalars().first()
        if client and client.expires_at and ensure_utc(client.expires_at) < utcnow():
            return None
        return client

    async def get_api_client_by_client_id(self, client_id: str) -> ApiClient | None:
        stmt = select(ApiClient).where(ApiClient.client_id == client_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_api_clients(self) -> list[ApiClient]:
        stmt = select(ApiClient).order_by(ApiClient.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def rotate_api_client_key(self, client_id: str) -> tuple[ApiClient, str]:
        client = await self.get_api_client_by_client_id(client_id)
        if not client:
            raise ValueError(f"API Client {client_id} not found")

        plain_key, key_prefix, hashed_key = generate_api_key()
        client.hashed_api_key = hashed_key
        client.key_prefix = key_prefix
        client.rotated_at = utcnow()
        await self.session.flush()
        return client, plain_key

    async def revoke_api_client(self, client_id: str) -> ApiClient:
        client = await self.get_api_client_by_client_id(client_id)
        if not client:
            raise ValueError(f"API Client {client_id} not found")

        client.status = "revoked"
        await self.session.flush()
        return client

    # -----------------------------------------------------------------------
    # Audit Logging
    # -----------------------------------------------------------------------

    async def write_audit_log(
        self,
        actor_id: str | None,
        actor_type: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        consent_artifact_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | str | None = None,
    ) -> AuditLog:
        details_str = (
            json.dumps(details, default=str)
            if isinstance(details, dict)
            else details
        )
        entry = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            consent_artifact_id=consent_artifact_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            details=details_str,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    # -----------------------------------------------------------------------
    # OTP Challenge Management
    # -----------------------------------------------------------------------

    async def create_otp_challenge(
        self,
        *,
        phone_number: str,
        code_hash: str,
        purpose: str = "login",
        expires_at: datetime,
        request_ip: str | None = None,
        user_agent: str | None = None,
    ) -> OtpChallenge:
        now = datetime.now(UTC)
        # Invalidate previous unconsumed challenges
        await self.session.execute(
            update(OtpChallenge)
            .where(
                OtpChallenge.phone_number == phone_number,
                OtpChallenge.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        challenge = OtpChallenge(
            phone_number=phone_number,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=expires_at,
            request_ip=request_ip,
            user_agent=user_agent,
            created_at=now,
        )
        self.session.add(challenge)
        await self.session.flush()
        return challenge

    async def get_latest_otp_challenge(self, phone_number: str) -> OtpChallenge | None:
        stmt = (
            select(OtpChallenge)
            .where(
                OtpChallenge.phone_number == phone_number,
                OtpChallenge.consumed_at.is_(None),
            )
            .order_by(OtpChallenge.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def check_otp_rate_limit(
        self, phone_number: str, request_ip: str | None = None
    ) -> tuple[bool, int]:
        """Check rate limits: max 3 per phone/hr, max 10 per IP/hr.

        Returns (allowed, retry_after_seconds).
        """
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)

        phone_count_stmt = select(func.count(OtpChallenge.id)).where(
            OtpChallenge.phone_number == phone_number,
            OtpChallenge.created_at >= one_hour_ago,
        )
        phone_count = await self.session.scalar(phone_count_stmt) or 0
        if phone_count >= 3:
            return False, 3600

        if request_ip:
            ip_count_stmt = select(func.count(OtpChallenge.id)).where(
                OtpChallenge.request_ip == request_ip,
                OtpChallenge.created_at >= one_hour_ago,
            )
            ip_count = await self.session.scalar(ip_count_stmt) or 0
            if ip_count >= 10:
                return False, 3600

        return True, 0

    async def find_or_create_otp_user(self, phone_number: str) -> tuple[User, bool]:
        """Find existing user by phone or create new with 'farmer' role and pending profile."""
        user = await self.get_user_by_identifier(phone_number)
        if user:
            return user, False

        import secrets

        dummy_hash = f"!otp_login_{secrets.token_hex(16)}"
        user = User(
            phone=phone_number,
            password_hash=dummy_hash,
            status="pending_profile",
            profile_complete=False,
        )
        self.session.add(user)
        await self.session.flush()

        role = await self.get_or_create_role("farmer")
        user_role = UserRole(user_id=user.id, role_id=role.id)
        self.session.add(user_role)
        await self.session.flush()

        reloaded = await self.get_user_by_id(user.id)
        return reloaded or user, True

