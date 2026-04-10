"""
At-rest encryption for server-stored wallet PEM material (legacy path before device-bound keys).

Uses Fernet (symmetric AES). Configure via .env / environment (see Settings):
  WALLET_AT_REST_FERNET_KEY — url-safe base64 44-char key from
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  or AWS_KMS_CIPHERTEXT_BLOB_BASE64 (+ AWS_REGION) for KMS-wrapped 32-byte key material.

If unset, derives a key from SECRET_KEY (dev only; set explicit keys in production).
Plaintext legacy rows (BEGIN PRIVATE KEY) are still readable and should be re-saved encrypted on rotation.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX: Final[str] = "OFFLINK_F1:"


def _fernet_key_from_kms() -> str | None:
    """
    Optional: 32-byte Fernet key material wrapped by AWS KMS.
    Set AWS_KMS_CIPHERTEXT_BLOB_BASE64 to standard Base64 of KMS Encrypt output.
    """
    b64 = (settings.AWS_KMS_CIPHERTEXT_BLOB_BASE64 or "").strip()
    if not b64:
        return None
    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise RuntimeError("Install boto3 to use AWS_KMS_CIPHERTEXT_BLOB_BASE64") from e
    try:
        client = boto3.client("kms", region_name=(settings.AWS_REGION or "us-east-1").strip())
        blob = base64.standard_b64decode(b64)
        pt = client.decrypt(CiphertextBlob=blob)["Plaintext"]
        if len(pt) != 32:
            raise ValueError("KMS plaintext must be 32 bytes (raw AES key for Fernet)")
        return base64.urlsafe_b64encode(pt).decode("ascii")
    except Exception as e:
        raise RuntimeError("Failed to decrypt WALLET fernet key via KMS") from e


def _fernet() -> Fernet:
    kms_key = _fernet_key_from_kms()
    if kms_key:
        return Fernet(kms_key.encode("ascii"))
    env_k = (settings.WALLET_AT_REST_FERNET_KEY or "").strip()
    if env_k:
        return Fernet(env_k.encode("ascii"))
    digest = hashlib.sha256(
        (settings.SECRET_KEY + "|offlink-wallet-at-rest-v1").encode("utf-8")
    ).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def seal_private_key_pem(pem_plaintext: str) -> str:
    """Store PEM ciphertext prefixed for recognition."""
    token = _fernet().encrypt(pem_plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def unseal_private_key_pem(stored: str | None) -> str | None:
    """
    Decrypt sealed value, or return legacy plaintext PEM unchanged.
    Returns None if stored is None or empty.
    """
    if not stored:
        return None
    s = stored.strip()
    if not s:
        return None
    if s.startswith(_PREFIX):
        raw = s[len(_PREFIX) :].encode("ascii")
        try:
            return _fernet().decrypt(raw).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("Wallet private key decryption failed (wrong WALLET_AT_REST_FERNET_KEY?)") from e
    if "BEGIN PRIVATE KEY" in s or "BEGIN RSA PRIVATE KEY" in s:
        return s
    raise ValueError("Unrecognized wallet private key blob format")
