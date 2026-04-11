"""
OTP challenges: Redis when REDIS_ENABLED and REDIS_URL are set, else PostgreSQL (OtpChallenge).

Codes are stored as SHA-256 hex of pepper||purpose||subject||nonce||code (constant-time compare).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import app_logger
from app.models.otp_challenge import OtpChallenge

PURPOSE_SIGNUP_VERIFY = "signup_verify"
PURPOSE_LOGIN_UNVERIFIED = "login_unverified"
PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_WALLET_CREATE = "wallet_create"
PURPOSE_TOPUP = "topup"

DEFAULT_TTL_SECONDS = 600
MAX_ATTEMPTS = 5
_NONCE_BYTES = 18


def _pepper() -> str:
    return (settings.OTP_PEPPER or "").strip() or (settings.SECRET_KEY + "|offlink-otp-v1")


def _hash_code(purpose: str, subject: str, nonce: str, code: str) -> str:
    raw = f"{_pepper()}|{purpose}|{subject}|{nonce}|{code}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _redis():
    if not settings.REDIS_ENABLED:
        return None
    if not (settings.REDIS_URL or "").strip():
        return None
    try:
        import redis  # type: ignore

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        app_logger.warning("Redis URL set but client unavailable: %s", e)
        return None


def _redis_key(nonce: str) -> str:
    return f"offlink:otp:v1:{nonce}"


def _subject_index_key(purpose: str, subject: str) -> str:
    h = hashlib.sha256(f"{purpose}|{subject}".encode("utf-8")).hexdigest()[:40]
    return f"offlink:otp:idx:v1:{h}"


def _invalidate_sql_subject(db: Session, purpose: str, subject: str) -> None:
    db.query(OtpChallenge).filter(
        OtpChallenge.purpose == purpose,
        OtpChallenge.subject == subject,
        OtpChallenge.consumed.is_(False),
    ).update({OtpChallenge.consumed: True})
    db.commit()


def create_challenge(
    db: Session,
    *,
    purpose: str,
    subject: str,
    code: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    metadata: Optional[dict[str, Any]] = None,
    invalidate_previous: bool = True,
) -> str:
    nonce = secrets.token_urlsafe(_NONCE_BYTES)
    code_hash = _hash_code(purpose, subject, nonce, code)
    meta_s = json.dumps(metadata, sort_keys=True) if metadata else None
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    r = _redis()
    if r:
        idx = _subject_index_key(purpose, subject)
        if invalidate_previous:
            old_nonce = r.get(idx)
            if old_nonce:
                r.delete(_redis_key(old_nonce))
        payload = {
            "purpose": purpose,
            "subject": subject,
            "code_hash": code_hash,
            "metadata": meta_s,
            "attempts": 0,
            "expires_at": expires_at.isoformat(),
        }
        r.setex(_redis_key(nonce), ttl_seconds, json.dumps(payload))
        r.setex(idx, ttl_seconds, nonce)
        if settings.DEBUG:
            app_logger.debug("OTP challenge created purpose=%s subject=%s nonce=%s", purpose, subject, nonce)
        return nonce

    if invalidate_previous:
        _invalidate_sql_subject(db, purpose, subject)
    row = OtpChallenge(
        nonce=nonce,
        purpose=purpose,
        subject=subject,
        code_hash=code_hash,
        metadata_json=meta_s,
        expires_at=expires_at,
        attempt_count=0,
        consumed=False,
    )
    db.add(row)
    db.commit()
    if settings.DEBUG:
        app_logger.debug("OTP challenge created purpose=%s subject=%s nonce=%s", purpose, subject, nonce)
    return nonce


def _verify_core(
    purpose: str,
    subject: str,
    nonce: str,
    code: str,
    code_hash_stored: str,
    attempts: int,
    expires_at: datetime,
    metadata_raw: Optional[str],
    bump_attempts_callback,
    consume_callback,
) -> tuple[bool, Optional[dict]]:
    if datetime.utcnow() > expires_at:
        return False, None
    if attempts >= MAX_ATTEMPTS:
        return False, None
    expected = _hash_code(purpose, subject, nonce, code)
    ok = hmac.compare_digest(expected, code_hash_stored)
    if not ok:
        bump_attempts_callback()
        return False, None
    consume_callback()
    meta = json.loads(metadata_raw) if metadata_raw else None
    return True, {"purpose": purpose, "subject": subject, "metadata": meta}


def verify_by_nonce(db: Session, *, nonce: str, code: str) -> tuple[bool, Optional[dict]]:
    """On success, dict has purpose, subject, metadata (optional)."""
    r = _redis()
    if r:
        key = _redis_key(nonce)
        raw = r.get(key)
        if not raw:
            return False, None
        data = json.loads(raw)
        purpose = data["purpose"]
        subject = data["subject"]
        expires_at = datetime.fromisoformat(data["expires_at"])
        attempts = int(data.get("attempts", 0))

        def bump():
            raw2 = r.get(key)
            if not raw2:
                return
            d2 = json.loads(raw2)
            d2["attempts"] = int(d2.get("attempts", 0)) + 1
            t = r.ttl(key)
            if t and t > 0:
                r.setex(key, t, json.dumps(d2))

        def consume():
            r.delete(key)
            idx = _subject_index_key(purpose, subject)
            if r.get(idx) == nonce:
                r.delete(idx)

        return _verify_core(
            purpose,
            subject,
            nonce,
            code,
            data["code_hash"],
            attempts,
            expires_at,
            data.get("metadata"),
            bump,
            consume,
        )

    row = (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.nonce == nonce,
            OtpChallenge.consumed.is_(False),
        )
        .first()
    )
    if not row:
        return False, None

    def bump_sql():
        row.attempt_count += 1
        db.add(row)
        db.commit()

    def consume_sql():
        row.consumed = True
        db.add(row)
        db.commit()

    return _verify_core(
        row.purpose,
        row.subject,
        row.nonce,
        code,
        row.code_hash,
        row.attempt_count,
        row.expires_at,
        row.metadata_json,
        bump_sql,
        consume_sql,
    )


def verify_latest_for_subject(
    db: Session, *, purpose: str, subject: str, code: str
) -> tuple[bool, Optional[dict]]:
    r = _redis()
    if r:
        idx = _subject_index_key(purpose, subject)
        nonce = r.get(idx)
        if not nonce:
            return False, None
        ok, info = verify_by_nonce(db, nonce=nonce, code=code)
        if ok and info and info.get("subject") != subject:
            return False, None
        return ok, info

    row = (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.purpose == purpose,
            OtpChallenge.subject == subject,
            OtpChallenge.consumed.is_(False),
            OtpChallenge.expires_at > datetime.utcnow(),
        )
        .order_by(OtpChallenge.id.desc())
        .first()
    )
    if not row:
        return False, None

    def bump_sql():
        row.attempt_count += 1
        db.add(row)
        db.commit()

    def consume_sql():
        row.consumed = True
        db.add(row)
        db.commit()

    return _verify_core(
        row.purpose,
        row.subject,
        row.nonce,
        code,
        row.code_hash,
        row.attempt_count,
        row.expires_at,
        row.metadata_json,
        bump_sql,
        consume_sql,
    )


def log_otp_dev_only(purpose: str, subject: str, otp_plain: str) -> None:
    if settings.DEBUG:
        app_logger.info("[OTP dev] purpose=%s subject=%s code=%s", purpose, subject, otp_plain)
    else:
        sub_h = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:12]
        app_logger.info("OTP issued purpose=%s subject_sha256_prefix=%s", purpose, sub_h)
