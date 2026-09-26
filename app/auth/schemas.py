"""Pydantic v2 schemas for authentication, authorization, and API clients."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    phone: str | None = None
    password: str = Field(min_length=8, description="Minimum 8 characters")
    roles: list[str] = Field(default_factory=lambda: ["farmer"])
    fpo_id: str | None = Field(default=None, description="FPO / Organization identifier")

    @model_validator(mode="after")
    def validate_identity(self) -> "UserRegisterRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone must be provided")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(description="Email or phone number")
    password: str = Field(description="User password")


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class OtpSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str = Field(description="Indian mobile number in E.164 format (+91XXXXXXXXXX)")


class OtpSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str = "OTP sent"
    expires_in: int = 300
    retry_after: int = 30


class OtpVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str = Field(description="Indian mobile number in E.164 format (+91XXXXXXXXXX)")
    otp_code: str = Field(min_length=4, max_length=8, description="6-digit verification code")


class OtpUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    roles: list[str] = Field(default_factory=list)
    profile_complete: bool = False


class OtpVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    user: OtpUserResponse



class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str = Field(min_length=8)


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None = None
    phone: str | None = None
    status: str
    fpo_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class ApiClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["lots:read", "prices:read"])
    allowed_origins: list[str] = Field(default_factory=list)
    rate_limit_tier: str = Field(default="standard")
    expires_days: int | None = Field(default=None, ge=1, le=365)


class ApiClientCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    name: str
    api_key: str = Field(description="Plaintext API key. Only returned once upon creation or rotation.")
    key_prefix: str
    scopes: list[str]
    allowed_origins: list[str]
    rate_limit_tier: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime


class ApiClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    allowed_origins: list[str]
    rate_limit_tier: str
    status: str
    rotated_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class ApiClientRotateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    api_key: str
    key_prefix: str
    rotated_at: datetime


class UserContext(BaseModel):
    """Context object representing the authenticated caller."""

    model_config = ConfigDict(extra="allow")

    user_id: int | None = None
    client_id: str | None = None
    email: str | None = None
    phone: str | None = None
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    org_id: str | None = None
    is_api_client: bool = False
    rate_limit_tier: str = "standard"

    def has_role(self, *required_roles: str) -> bool:
        if "admin" in self.roles:
            return True
        return any(role in self.roles for role in required_roles)

    def has_scope(self, *required_scopes: str) -> bool:
        if "admin" in self.scopes or "all" in self.scopes:
            return True
        return all(scope in self.scopes for scope in required_scopes)

    def has_org_access(self, target_org_id: str | None) -> bool:
        if "admin" in self.roles:
            return True
        if not target_org_id:
            return True
        return self.org_id == target_org_id
