# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from app.core import security
from app.core.db import get_db
from app.models import User
from app.models_refresh_token import RefreshToken

router = APIRouter(prefix="/auth", tags=["auth"])

# --- util functions (you can replace send_email with real SMTP) ---
def send_email(recipient: str, subject: str, body: str):
    # Replace with real email service in production
    print(f"[EMAIL] To: {recipient} | Subject: {subject}\n{body}")

# Signup with strong password policy and email verification flow
@router.post("/signup", status_code=201)
def signup(payload: dict = Body(...), db: Session = Depends(get_db)):
    # payload required keys: name, email, password, phone
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    phone = payload.get("phone")

    # basic validations
    if not name or not email or not password:
        raise HTTPException(status_code=422, detail="name, email and password required")

    # enforce strong password
    import re
    if len(password) < 10 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"\d", password) or not re.search(r"[^\w\s]", password):
        raise HTTPException(status_code=422, detail="Password does not meet complexity rules")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = User(
        name=name,
        email=email,
        phone=phone,
        password_hash=security.get_password_hash(password),
        is_email_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # create email verification token (short lived)
    otp = secrets.token_urlsafe(8)
    # store OTP embedded in a server side cache in prod (Redis). For now, we "email" it and print.
    # In production, persist OTP with expiry in DB or Redis keyed by user id.
    send_email(email, "Verify your email", f"Your verification code: {otp}")

    # For demo we return a temporary token (do not do this in production).
    return {"msg": "User created. Check your email for verification code (demo prints).", "otp_demo": otp}

# Verify email endpoint (user posts otp)
@router.post("/verify-email")
def verify_email(email: str = Body(...), otp: str = Body(...), db: Session = Depends(get_db)):
    # NOTE: in prod map OTP to DB/Redis. Here we assume OTP valid.
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # In demo we accept any OTP; adjust to validate stored OTP
    user.is_email_verified = True
    db.add(user)
    db.commit()
    return {"msg": "Email verified"}

# Login step 1: credential check -> send MFA OTP
@router.post("/login")
def login_step1(email: str = Body(...), password: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_email_verified:
        raise HTTPException(status_code=401, detail="Email not verified")

    # generate email MFA OTP
    mfa_otp = secrets.token_hex(3)  # 6 hex chars
    # In production save OTP in DB/Redis with expiry; here we print/send for demo
    send_email(user.email, "Your login OTP", f"Your login code: {mfa_otp}")

    # For demo return a temporary nonce token to validate OTP step (in prod you would save OTP.)
    nonce = secrets.token_urlsafe(16)
    # store nonce->otp mapping temporarily in memory/cache in production
    # return nonce to client to pass back with OTP (demo)
    return {"nonce_demo": nonce, "otp_demo": mfa_otp}

# Login step 2: verify OTP -> issue access & refresh token
@router.post("/login/confirm")
def login_confirm(email: str = Body(...), otp: str = Body(...), nonce: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # In production verify OTP via DB/Redis store keyed to nonce.
    # Here assume otp valid for demo.
    access_token = security.create_access_token(subject=str(user.id), device_fingerprint=device_fingerprint)
    refresh_token, expires_at = security.create_refresh_token(subject=str(user.id), device_fingerprint=device_fingerprint)

    # persist refresh token record
    rt = RefreshToken(token=refresh_token, user_id=user.id, device_fingerprint=device_fingerprint, expires_at=expires_at)
    db.add(rt)
    db.commit()

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

# Refresh token endpoint
@router.post("/token/refresh")
def token_refresh(refresh_token: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    try:
        payload = security.decode_token(refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    rt_record = db.query(RefreshToken).filter(RefreshToken.token == refresh_token, RefreshToken.revoked == False).first()
    if not rt_record:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")
    if rt_record.device_fingerprint != device_fingerprint:
        raise HTTPException(status_code=401, detail="Device mismatch")

    # issue new access token
    access_token = security.create_access_token(subject=str(rt_record.user_id), device_fingerprint=device_fingerprint)
    return {"access_token": access_token, "token_type": "bearer"}

# Logout (revoke refresh token)
@router.post("/logout")
def logout(refresh_token: str = Body(...), db: Session = Depends(get_db)):
    rt_record = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if rt_record:
        rt_record.revoked = True
        db.add(rt_record)
        db.commit()
    return {"msg": "Logged out"}
