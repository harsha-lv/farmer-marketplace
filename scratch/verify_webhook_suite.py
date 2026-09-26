"""Comprehensive verification suite for Consent Manager Revocation Webhook (DPDP-critical path)."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import time
import urllib.request
import urllib.error

from sqlalchemy import delete, select, text
from app.config import get_settings
from app.consent.models import ConsentArtifact
from app.consent.signing import PURPOSE, canonical_grant, sign
from app.db.session import Database
from app.farmers.models import Farmer, LandParcel
from app.lots.models import Lot
from app.events.models import OutboxEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("webhook_test")

BASE_URL = "http://127.0.0.1:8000"

async def setup_test_data():
    settings = get_settings()
    db = Database(settings.database_url)
    now_dt = datetime.now(UTC)
    exp_dt = now_dt + timedelta(days=365)
    secret = settings.consent_signing_secret

    async with db.session_factory() as session:
        # Clean previous test artifacts
        test_artifacts = ["consent-webhook-test-001", "consent-webhook-root-001"]
        test_farmers = ["farmer-webhook-001", "farmer-webhook-root-001"]
        
        await session.execute(
            delete(Lot).where(Lot.farmer_id.in_(test_farmers))
        )
        await session.execute(
            delete(LandParcel).where(LandParcel.farmer_id.in_(
                select(Farmer.id).where(Farmer.farmer_id.in_(test_farmers))
            ))
        )
        await session.execute(
            delete(Farmer).where(Farmer.farmer_id.in_(test_farmers))
        )
        await session.execute(
            delete(ConsentArtifact).where(ConsentArtifact.artifact_id.in_(test_artifacts))
        )
        await session.commit()

        # Seed test-001
        c1_sig = sign(canonical_grant(
            artifact_id="consent-webhook-test-001",
            farmer_id="farmer-webhook-001",
            purpose=PURPOSE,
            attributes=["profile", "land"],
            created_at=now_dt,
            expires_at=exp_dt,
        ), secret)
        
        c1 = ConsentArtifact(
            artifact_id="consent-webhook-test-001",
            farmer_id="farmer-webhook-001",
            purpose=PURPOSE,
            attributes=["profile", "land"],
            created_at=now_dt,
            expires_at=exp_dt,
            recorded_at=now_dt,
            status="active",
            signature=c1_sig,
        )
        session.add(c1)
        await session.flush()

        f1 = Farmer(
            farmer_id="farmer-webhook-001",
            state_lgd_code="23",
            display_name="Devendra Patel",
            consent_artifact_id="consent-webhook-test-001",
            org_id="FPO-MP-001",
        )
        session.add(f1)
        await session.flush()

        p1 = LandParcel(
            farmer_id=f1.id,
            farm_id="FARM-WH-001",
            area_hectares=Decimal("2.5000"),
        )
        session.add(p1)

        l1 = Lot(
            lot_code="LOT-WH-001",
            farmer_id="farmer-webhook-001",
            commodity="Wheat",
            variety="Sharbati",
            quantity_mt=Decimal("5.000"),
            consent_artifact_id="consent-webhook-test-001",
            status="active",
            org_id="FPO-MP-001",
        )
        session.add(l1)

        # Seed root-001
        c2_sig = sign(canonical_grant(
            artifact_id="consent-webhook-root-001",
            farmer_id="farmer-webhook-root-001",
            purpose=PURPOSE,
            attributes=["profile", "land"],
            created_at=now_dt,
            expires_at=exp_dt,
        ), secret)
        
        c2 = ConsentArtifact(
            artifact_id="consent-webhook-root-001",
            farmer_id="farmer-webhook-root-001",
            purpose=PURPOSE,
            attributes=["profile", "land"],
            created_at=now_dt,
            expires_at=exp_dt,
            recorded_at=now_dt,
            status="active",
            signature=c2_sig,
        )
        session.add(c2)
        await session.flush()

        f2 = Farmer(
            farmer_id="farmer-webhook-root-001",
            state_lgd_code="23",
            display_name="Sunil Sharma",
            consent_artifact_id="consent-webhook-root-001",
            org_id="FPO-MP-001",
        )
        session.add(f2)
        await session.commit()
        logger.info("Test data seeded successfully for webhook verification.")


def do_post(url: str, raw_bytes: bytes, headers: dict) -> tuple[int, dict | str, float]:
    req = urllib.request.Request(url, data=raw_bytes, headers=headers, method="POST")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req) as resp:
            elapsed = time.perf_counter() - start
            status_code = resp.status
            body = resp.read().decode()
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return status_code, parsed, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        body = e.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed, elapsed


def run_tests():
    settings = get_settings()
    secret = settings.consent_manager_webhook_secret or settings.consent_signing_secret
    logger.info("Using webhook secret: %s...", secret[:8])

    results = {}

    # Test A: Happy Path
    now_utc = datetime.now(UTC).isoformat()
    payload_a = {
        "event_id": "cm-deliv-001",
        "event_type": "CONSENT_REVOKED",
        "consent_id": "consent-webhook-test-001",
        "farmer_id": "farmer-webhook-001",
        "timestamp": now_utc,
        "reason": "Data Principal exercised statutory right to withdraw consent under DPDP Act",
    }
    raw_a = json.dumps(payload_a, separators=(",", ":")).encode("utf-8")
    sig_a = hmac.new(secret.encode(), raw_a, hashlib.sha256).hexdigest()
    
    headers_a = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-001",
        "X-Signature-256": sig_a,
    }
    status_a, body_a, dur_a = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_a, headers_a)
    results["a_happy_path"] = {
        "status": status_a,
        "body": body_a,
        "duration_ms": round(dur_a * 1000, 2),
    }

    # Test B: Tampered Signature
    # Flip last hex character
    tampered_sig = sig_a[:-1] + ("0" if sig_a[-1] != "0" else "1")
    headers_b = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-002",
        "X-Signature-256": tampered_sig,
    }
    status_b, body_b, dur_b = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_a, headers_b)
    results["b_tampered_signature"] = {
        "status": status_b,
        "body": body_b,
        "duration_ms": round(dur_b * 1000, 2),
    }

    # Test C: Replay (resend identical request with same delivery ID)
    status_c, body_c, dur_c = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_a, headers_a)
    results["c_replay"] = {
        "status": status_c,
        "body": body_c,
        "duration_ms": round(dur_c * 1000, 2),
    }

    # Test D: Stale Timestamp (10 minutes in past, >300s skew)
    stale_utc = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    payload_d = {
        "event_id": "cm-deliv-004-stale",
        "event_type": "CONSENT_REVOKED",
        "consent_id": "consent-webhook-test-001",
        "farmer_id": "farmer-webhook-001",
        "timestamp": stale_utc,
        "reason": "Stale timestamp test",
    }
    raw_d = json.dumps(payload_d, separators=(",", ":")).encode("utf-8")
    sig_d = hmac.new(secret.encode(), raw_d, hashlib.sha256).hexdigest()
    headers_d = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-004-stale",
        "X-Signature-256": sig_d,
    }
    status_d, body_d, dur_d = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_d, headers_d)
    results["d_stale_timestamp"] = {
        "status": status_d,
        "body": body_d,
        "duration_ms": round(dur_d * 1000, 2),
    }

    # Test E: Already-withdrawn (new delivery ID for already-withdrawn artifact)
    fresh_utc = datetime.now(UTC).isoformat()
    payload_e = {
        "event_id": "cm-deliv-005-already-withdrawn",
        "event_type": "CONSENT_REVOKED",
        "consent_id": "consent-webhook-test-001",
        "farmer_id": "farmer-webhook-001",
        "timestamp": fresh_utc,
        "reason": "Duplicate revocation notice",
    }
    raw_e = json.dumps(payload_e, separators=(",", ":")).encode("utf-8")
    sig_e = hmac.new(secret.encode(), raw_e, hashlib.sha256).hexdigest()
    headers_e = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-005-already-withdrawn",
        "X-Signature-256": sig_e,
    }
    status_e, body_e, dur_e = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_e, headers_e)
    results["e_already_withdrawn"] = {
        "status": status_e,
        "body": body_e,
        "duration_ms": round(dur_e * 1000, 2),
    }

    # Test F: No signature (omit signature header and body signature)
    payload_f = {
        "event_id": "cm-deliv-006-no-sig",
        "event_type": "CONSENT_REVOKED",
        "consent_id": "consent-webhook-test-001",
        "farmer_id": "farmer-webhook-001",
        "timestamp": fresh_utc,
        "reason": "Omitted signature",
    }
    raw_f = json.dumps(payload_f, separators=(",", ":")).encode("utf-8")
    headers_f = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-006-no-sig",
    }
    status_f, body_f, dur_f = do_post(f"{BASE_URL}/api/v1/consents/webhook", raw_f, headers_f)
    results["f_no_signature"] = {
        "status": status_f,
        "body": body_f,
        "duration_ms": round(dur_f * 1000, 2),
    }

    # Test G: Timing (< 2s)
    # The happy path timing was dur_a, but let's test root endpoint for timing verification
    root_utc = datetime.now(UTC).isoformat()
    payload_g = {
        "event_id": "cm-deliv-root-001",
        "event_type": "CONSENT_REVOKED",
        "consent_id": "consent-webhook-root-001",
        "farmer_id": "farmer-webhook-root-001",
        "timestamp": root_utc,
        "reason": "Root alias revocation test",
    }
    raw_g = json.dumps(payload_g, separators=(",", ":")).encode("utf-8")
    sig_g = hmac.new(secret.encode(), raw_g, hashlib.sha256).hexdigest()
    headers_g = {
        "Content-Type": "application/json",
        "X-Delivery-Id": "cm-deliv-root-001",
        "X-Signature-256": sig_g,
    }
    status_g, body_g, dur_g = do_post(f"{BASE_URL}/consents/webhook", raw_g, headers_g)
    results["g_timing_and_root_alias"] = {
        "status": status_g,
        "body": body_g,
        "duration_seconds": round(dur_g, 4),
        "timing_pass": dur_g < 2.0,
    }

    return results

async def verify_db_cascade():
    settings = get_settings()
    db = Database(settings.database_url)
    async with db.session_factory() as session:
        c1 = await session.scalar(select(ConsentArtifact).where(ConsentArtifact.artifact_id == "consent-webhook-test-001"))
        f1 = await session.scalar(select(Farmer).where(Farmer.farmer_id == "farmer-webhook-001"))
        lots1 = (await session.execute(select(Lot).where(Lot.farmer_id == "farmer-webhook-001"))).scalars().all()
        events = (await session.execute(
            select(OutboxEvent).where(OutboxEvent.stream_id == "consent:consent-webhook-test-001")
        )).scalars().all()

        return {
            "artifact_status": c1.status if c1 else None,
            "artifact_withdrawn_at": c1.withdrawn_at.isoformat() if (c1 and c1.withdrawn_at) else None,
            "farmer_exists": f1 is not None,
            "lots_count": len(lots1),
            "lot_statuses": [l.status for l in lots1],
            "events_count": len(events),
            "event_types": [e.event_type for e in events],
        }

async def main():
    await setup_test_data()
    results = run_tests()
    cascade = await verify_db_cascade()

    output = {
        "webhook_tests": results,
        "postgres_cascade": cascade,
    }
    print("=== LIVE TEST RESULTS ===")
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
