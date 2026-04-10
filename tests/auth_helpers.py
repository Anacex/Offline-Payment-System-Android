"""Shared auth helpers for API tests (matches current /auth/login behavior)."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi.testclient import TestClient


def get_auth_headers(
    client: TestClient,
    test_user: dict[str, Any],
    device_fingerprint: str | None = "device123",
    *,
    unique_device: bool = False,
) -> dict[str, str]:
    """
    Log in and return Authorization header.

    Verified users: /auth/login returns tokens immediately (no OTP step).
    Unverified users: /auth/login returns nonce_demo + otp_demo when DEBUG is True;
    tests then complete /auth/login/confirm.

    If unique_device is True, or device_fingerprint is None, a fresh fingerprint is used
    (avoids refresh-token collisions in sync tests that log in many times).
    """
    if unique_device:
        fp = f"device_{secrets.token_hex(8)}"
    elif device_fingerprint is None:
        fp = f"device_{secrets.token_hex(8)}"
    else:
        fp = device_fingerprint
    email = test_user["email"]
    password = test_user["password"]
    payload = {"email": email, "password": password, "device_fingerprint": fp}
    login_resp = client.post("/auth/login", json=payload)
    assert login_resp.status_code == 200, login_resp.text
    body = login_resp.json()

    if body.get("requires_otp") is False:
        token = body["access_token"]
    else:
        nonce = body.get("nonce_demo")
        otp = body.get("otp_demo")
        assert nonce and otp, (
            "OTP login path requires DEBUG=True so otp_demo is present in /auth/login response"
        )
        confirm_resp = client.post(
            "/auth/login/confirm",
            json={
                "email": email,
                "otp": otp,
                "nonce": nonce,
                "device_fingerprint": fp,
            },
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        token = confirm_resp.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}
