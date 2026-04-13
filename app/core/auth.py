
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from typing import Optional
from .config import settings
from .db import get_db
from app.core.account_status import raise_if_account_blocked
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if not user:
        raise credentials_exception
    # Allow a blocked user to attempt ledger re-sync to recover.
    # Other endpoints remain blocked.
    path = (request.url.path or "").rstrip("/")
    if getattr(user, "account_blocked", False):
        allowed = path in (
            "/api/v1/offline-transactions/sync",
            "/api/v1/offline-transactions/offline-sync",
        )
        if not allowed:
            # Recovery allow-list for benign ledger head mismatches.
            # This prevents a "deadlock" where the app cannot call /auth/me or /wallets
            # to reach the sync UI flow after a non-tamper ledger mismatch.
            reason = (getattr(user, "account_blocked_reason", "") or "")
            benign_ledger_block = (
                "Device ledger integrity check failed during sync" in reason
                and ("LEDGER_INTEGRITY_PREV_MISMATCH" in reason or "LEDGER_INTEGRITY_SEQUENCE_MISMATCH" in reason)
            )
            if benign_ledger_block:
                if path in (
                    "/auth/me",
                    "/api/v1/wallets",
                ) or path.startswith("/api/v1/wallets/"):
                    return user
            raise_if_account_blocked(user)
    return user
