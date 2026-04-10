"""
One-off migration: encrypt plaintext PEM rows in wallets.private_key_encrypted using current Fernet settings.

Run from repo root (with DATABASE_URL / .env loaded):
  python -m scripts.reseal_wallet_private_keys

Safe to re-run: rows already prefixed OFFLINK_F1: are skipped.
"""

from __future__ import annotations

import os
import sys

# Allow `python scripts/reseal_wallet_private_keys.py` from repo root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.core.db import SessionLocal  # noqa: E402
from app.core.wallet_storage import seal_private_key_pem, unseal_private_key_pem  # noqa: E402
from app.models.wallet import Wallet  # noqa: E402


def main() -> None:
    db = SessionLocal()
    updated = 0
    try:
        rows = db.query(Wallet).filter(Wallet.private_key_encrypted.isnot(None)).all()
        for w in rows:
            raw = (w.private_key_encrypted or "").strip()
            if not raw or raw.startswith("OFFLINK_F1:"):
                continue
            try:
                pem = unseal_private_key_pem(raw)
            except ValueError:
                print(f"skip wallet id={w.id}: cannot read key blob")
                continue
            if not pem or "BEGIN" not in pem:
                continue
            w.private_key_encrypted = seal_private_key_pem(pem)
            db.add(w)
            updated += 1
        db.commit()
        print(f"Resealed {updated} wallet private key row(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
