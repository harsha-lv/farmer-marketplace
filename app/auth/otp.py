"""OTP service: Generation, hashing, rate limiting, validation, and delivery providers."""

import hashlib
import hmac
import logging
import re
import secrets
from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("app.auth.otp")

# Strict E.164 regex for Indian mobile numbers (starts with +91 followed by 6, 7, 8, or 9 and 9 digits)
INDIAN_MOBILE_REGEX = re.compile(r"^\+91[6-9]\d{9}$")


def normalize_and_validate_indian_phone(phone_number: str) -> str:
    """Normalize and validate an Indian mobile phone number in E.164 format.

    Rejects landlines, special service numbers, and invalid digit lengths.
    """
    if not phone_number or not isinstance(phone_number, str):
        raise ValueError("Phone number is required.")

    # Remove all whitespace, dashes, dots, and parentheses
    cleaned = re.sub(r"[\s\-\(\)\.]", "", phone_number.strip())

    # If starts with 0, replace with +91
    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = "+91" + cleaned[1:]
    # If 10 digits without prefix, prepend +91
    elif len(cleaned) == 10 and cleaned.isdigit():
        cleaned = "+91" + cleaned
    # If starts with 91 without plus, prepend +
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = "+" + cleaned

    if not INDIAN_MOBILE_REGEX.match(cleaned):
        raise ValueError(
            "Invalid Indian mobile number. Must be a valid 10-digit mobile number starting with 6, 7, 8, or 9."
        )

    return cleaned


def generate_otp_code() -> str:
    """Generate a secure, cryptographically random 6-digit numeric OTP code."""
    num = secrets.randbelow(1_000_000)
    return f"{num:06d}"


def hash_otp_code(code: str, pepper: str) -> str:
    """Hash an OTP code using HMAC-SHA256 with the server-side pepper."""
    key = pepper.encode("utf-8")
    msg = code.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_otp_hash(candidate_code: str, stored_hash: str, pepper: str) -> bool:
    """Constant-time comparison between candidate OTP code and stored hash."""
    candidate_hash = hash_otp_code(candidate_code, pepper)
    return hmac.compare_digest(candidate_hash, stored_hash)


# ---------------------------------------------------------------------------
# Delivery Provider Interface & Implementations
# ---------------------------------------------------------------------------


class OtpDeliveryProvider(ABC):
    """Abstract interface for OTP delivery (SMS, WhatsApp, Console Logging)."""

    @abstractmethod
    async def send_otp(self, phone_number: str, code: str) -> bool:
        """Send OTP code to recipient phone number."""


class LogOtpProvider(OtpDeliveryProvider):
    """Dev-only provider that logs OTP at WARNING level. Fails closed in production."""

    def __init__(self, settings: Settings) -> None:
        if settings.is_production:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: LogOtpProvider cannot be activated in production! "
                "Configure a valid SMS gateway provider (e.g. MSG91, Twilio)."
            )
        self.settings = settings

    async def send_otp(self, phone_number: str, code: str) -> bool:
        logger.warning(
            "=================================================================\n"
            "[DEV-ONLY OTP] Target: %s | Verification Code: >>> %s <<<\n"
            "Valid for %d seconds. NEVER log this code in production.\n"
            "=================================================================",
            phone_number,
            code,
            self.settings.otp_ttl_seconds,
        )
        return True


class SmsOtpProvider(OtpDeliveryProvider):
    """SMS Gateway Adapter using MSG91 / generic HTTP webhook API via httpx."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.adapter = settings.otp_sms_adapter.lower()
        self.api_key = settings.otp_sms_api_key
        self.sender_id = settings.otp_sms_sender_id
        self.template_id = settings.otp_sms_template_id

    async def send_otp(self, phone_number: str, code: str) -> bool:
        if not self.api_key:
            logger.error("SMS Gateway API key is not configured.")
            return False

        # Digits without plus for MSG91
        raw_number = phone_number.lstrip("+")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if self.adapter == "msg91":
                    # MSG91 Send OTP API endpoint
                    url = f"https://control.msg91.com/api/v5/otp?template_id={self.template_id}&mobile={raw_number}&authkey={self.api_key}&otp={code}"
                    headers = {"Content-Type": "application/json"}
                    resp = await client.post(url, headers=headers)
                    if resp.status_code == 200:
                        logger.info("MSG91 OTP dispatched successfully to %s", phone_number[-4:])
                        return True
                    logger.error("MSG91 OTP dispatch failed with HTTP %d: %s", resp.status_code, resp.text)
                    return False
                else:
                    logger.warning("Unsupported SMS adapter '%s'; falling back to generic log.", self.adapter)
                    return False
        except httpx.HTTPError as exc:
            logger.error("Failed to transmit SMS OTP: %s", exc)
            return False


def get_otp_provider(settings: Settings | None = None) -> OtpDeliveryProvider:
    """Factory creating the configured OTP delivery provider."""
    s = settings or get_settings()
    if s.otp_provider.lower() == "sms":
        return SmsOtpProvider(s)
    return LogOtpProvider(s)
