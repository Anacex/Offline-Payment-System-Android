"""Resolve a stable device identifier for QR / server-side helpers."""

from __future__ import annotations

from typing import Optional

from starlette.requests import Request


def get_device_fingerprint(request: Optional[Request] = None) -> str:
    """Prefer client-provided headers; fall back when missing (e.g. tests, curl)."""
    if request is not None:
        for key in ("X-Device-Fingerprint", "X-Device-Id", "X-Device-ID"):
            v = request.headers.get(key)
            if v and str(v).strip():
                return str(v).strip()
    return "device-unknown"
