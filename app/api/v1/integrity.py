"""
Optional Google Play Integrity token verification.

Configure PLAY_INTEGRITY_SERVICE_ACCOUNT_JSON (path to GCP service account JSON with Play Integrity API)
and PLAY_INTEGRITY_PACKAGE_NAME. Without configuration, endpoint returns not_configured.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException
from pydantic import AliasChoices, BaseModel, Field

from app.core.config import settings
from app.core.logging_config import app_logger

router = APIRouter(prefix="/api/v1/device", tags=["device"])


class PlayIntegrityRequest(BaseModel):
    integrity_token: str = Field(
        ...,
        validation_alias=AliasChoices("integrity_token", "integrityToken"),
    )


@router.post("/play-integrity/decode")
def decode_play_integrity(payload: PlayIntegrityRequest = Body(...)) -> dict[str, Any]:
    """
    Verifies an integrity token from the Android Play Integrity API (server-side decode).
    Use the verdicts (device integrity, app integrity) in your risk engine — do not treat as sole auth.
    """
    sa_path = (settings.PLAY_INTEGRITY_SERVICE_ACCOUNT_JSON or "").strip()
    pkg = (settings.PLAY_INTEGRITY_PACKAGE_NAME or "").strip() or "com.offlinepayment"
    if not sa_path or not os.path.isfile(sa_path):
        return {
            "configured": False,
            "message": "Set PLAY_INTEGRITY_SERVICE_ACCOUNT_JSON to a service account JSON path with Play Integrity API access.",
        }

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail="google-auth not installed; add google-auth to requirements for Play Integrity.",
        ) from e

    scopes = ["https://www.googleapis.com/auth/playintegrity"]
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
    creds.refresh(Request())
    if not creds.token:
        raise HTTPException(status_code=503, detail="Could not obtain access token for Play Integrity")

    url = f"https://playintegrity.googleapis.com/v1/{pkg}:decodeIntegrityToken"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                json={"integrityToken": payload.integrity_token.strip()},
            )
    except httpx.RequestError as e:
        app_logger.exception("Play Integrity HTTP error: %s", e)
        raise HTTPException(status_code=502, detail="Play Integrity request failed") from e

    if r.status_code != 200:
        app_logger.warning("Play Integrity decode failed: %s %s", r.status_code, r.text[:500])
        raise HTTPException(
            status_code=400,
            detail="Play Integrity decode rejected",
        )

    body = r.json()
    if not settings.DEBUG:
        # Avoid logging full verdict payloads in production
        app_logger.info("Play Integrity decode OK for package=%s", pkg)
    return {"configured": True, "packageName": pkg, "tokenPayloadExternal": body.get("tokenPayloadExternal")}
