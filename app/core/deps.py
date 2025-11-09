# app/core/deps.py
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.core.db import get_db
from app.core import security
from app.models import User

security_scheme = HTTPBearer()

def get_current_user(authorization=Depends(security_scheme), db: Session = Depends(get_db), x_device_fingerprint: str = Header(None)):
    token = authorization.credentials
    try:
        payload = security.decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    # Optionally enforce device_fingerprint on access token usage
    token_df = payload.get("df")
    if token_df and x_device_fingerprint and token_df != x_device_fingerprint:
        raise HTTPException(status_code=401, detail="Device mismatch")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def admin_required(user: User = Depends(get_current_user)):
    # admin concept: we made universal user model; define admin by email or admin flag if you prefer
    # For Phase-1, use a special env configured admin email or DB flag (here we check email)
    admin_emails = ("admin@offlinepay.pk", )  # replace or prefer DB field in production
    if user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
