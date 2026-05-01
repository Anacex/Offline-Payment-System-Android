# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Header
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.account_status import raise_if_account_blocked
from app.core.validators import SecurityValidator
from app.core.otp_service import (
    PURPOSE_LOGIN_UNVERIFIED,
    PURPOSE_PASSWORD_RESET,
    PURPOSE_SIGNUP_VERIFY,
    create_challenge,
    log_otp_dev_only,
    verify_by_nonce,
    verify_latest_for_subject,
)
from app.models import User
from app.models_refresh_token import RefreshToken

router = APIRouter(prefix="/auth", tags=["auth"])

# Import email service
from app.core.email import send_email


def _require_strong_password(password: str) -> None:
    ok, _err = SecurityValidator.validate_password_strength(password)
    if not ok:
        raise HTTPException(status_code=422, detail="Password does not meet complexity rules")


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

    _require_strong_password(password)

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
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

    # create email verification token (short lived) - 6 digit numeric code
    otp_code = secrets.randbelow(1000000)  # Generate 0-999999
    otp = f"{otp_code:06d}"  # Format as 6-digit string with leading zeros
    # store OTP embedded in a server side cache in prod (Redis). For now, we "email" it and print.
    # In production, persist OTP with expiry in DB or Redis keyed by user id.
    
    # Send verification email with formatted template
    email_body = f"""
Hello {name},

Thank you for signing up for Offline Pay Service! Please verify your email address using the code below:

Your verification code: {otp}

This code will expire in 10 minutes.

If you didn't create an account, please ignore this email.
"""
    
    # HTML version for better formatting
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #4CAF50; text-align: center; 
                        background-color: white; padding: 20px; margin: 20px 0; 
                        border-radius: 5px; letter-spacing: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Email Verification</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{name}</strong>,</p>
                <p>Thank you for signing up! Please verify your email address using the code below:</p>
                <div class="otp-code">{otp}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't create an account, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(email, "Verify your Offline Pay email address", email_body, html_body)

    subj = email.strip().lower()
    create_challenge(
        db,
        purpose=PURPOSE_SIGNUP_VERIFY,
        subject=subj,
        code=otp,
        metadata={"user_id": user.id},
    )
    log_otp_dev_only(PURPOSE_SIGNUP_VERIFY, subj, otp)

    return {
        "msg": "User created. Check your email for verification code.",
        "otp_demo": otp if settings.DEBUG else None,
    }

# Verify email endpoint (user posts otp)
@router.post("/verify-email")
def verify_email(email: str = Body(...), otp: str = Body(...), db: Session = Depends(get_db)):
    subj = email.strip().lower()
    ok, info = verify_latest_for_subject(
        db, purpose=PURPOSE_SIGNUP_VERIFY, subject=subj, code=otp.strip()
    )
    if not ok or not info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )
    user = db.query(User).filter(func.lower(User.email) == subj).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_email_verified = True
    db.add(user)
    db.commit()

    return {"msg": "Email verified"}

# Login step 1: credential check -> send MFA OTP (or skip if email verified)
@router.post("/login")
def login_step1(email: str = Body(...), password: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # NOTE: Do not block login. A blocked user must be able to obtain a token to attempt
    # recovery via the offline sync endpoint (which is explicitly allowed server-side).
    # Access to other protected endpoints is still gated by `get_current_user`.

    # If email is verified, skip OTP and directly issue tokens
    if user.is_email_verified:
        access_token = security.create_access_token(subject=str(user.id), device_fingerprint=device_fingerprint)
        refresh_token, expires_at = security.create_refresh_token(subject=str(user.id), device_fingerprint=device_fingerprint)
        
        # persist refresh token record
        rt = RefreshToken(token=refresh_token, user_id=user.id, device_fingerprint=device_fingerprint, expires_at=expires_at)
        db.add(rt)
        db.commit()
        
        # Return tokens directly for verified users (skip OTP step)
        return {
            "requires_otp": False,
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": refresh_token
        }
    
    # Email not verified - require OTP verification
    # Generate email verification OTP - 6 digit numeric code
    otp_code = secrets.randbelow(1000000)  # Generate 0-999999
    otp = f"{otp_code:06d}"  # Format as 6-digit string with leading zeros
    # In production save OTP in DB/Redis with expiry; here we print/send for demo
    
    # Send verification email with formatted template
    email_body = f"""
Hello {user.name},

You need to verify your email to complete login. Please use the code below:

Your verification code: {otp}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.
"""
    
    # HTML version for better formatting
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #FF9800; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #FF9800; text-align: center; 
                        background-color: white; padding: 20px; margin: 20px 0; 
                        border-radius: 5px; letter-spacing: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Email Verification Required</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{user.name}</strong>,</p>
                <p>You need to verify your email to complete login. Please use the code below:</p>
                <div class="otp-code">{otp}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't request this code, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(user.email, "Verify your email to complete login", email_body, html_body)

    subj = user.email.strip().lower()
    nonce = create_challenge(
        db,
        purpose=PURPOSE_LOGIN_UNVERIFIED,
        subject=subj,
        code=otp,
    )
    log_otp_dev_only(PURPOSE_LOGIN_UNVERIFIED, subj, otp)

    return {
        "requires_otp": True,
        "nonce_demo": nonce,
        "otp_demo": otp if settings.DEBUG else None,
        "email_verified": False,
    }

# Login step 2: verify OTP -> issue access & refresh token (and verify email if unverified)
@router.post("/login/confirm")
def login_confirm(email: str = Body(...), otp: str = Body(...), nonce: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    subj = email.strip().lower()
    ok, info = verify_by_nonce(db, nonce=nonce.strip(), code=otp.strip())
    if not ok or not info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )
    if info["purpose"] != PURPOSE_LOGIN_UNVERIFIED or info["subject"] != subj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    user = db.query(User).filter(func.lower(User.email) == subj).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # NOTE: Do not block login confirmation; blocked users must be able to obtain a token
    # to attempt recovery via offline sync.

    if not user.is_email_verified:
        user.is_email_verified = True
        db.add(user)
        db.commit()

    access_token = security.create_access_token(subject=str(user.id), device_fingerprint=device_fingerprint)
    refresh_token, expires_at = security.create_refresh_token(subject=str(user.id), device_fingerprint=device_fingerprint)

    # persist refresh token record
    rt = RefreshToken(token=refresh_token, user_id=user.id, device_fingerprint=device_fingerprint, expires_at=expires_at)
    db.add(rt)
    db.commit()

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@router.post("/forgot-password")
def forgot_password_request(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Sends a one-time code to the user's email when the account exists."""
    email = payload.get("email")
    if not email or not str(email).strip():
        raise HTTPException(status_code=422, detail="email is required")
    subj = str(email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == subj).first()
    generic_msg = "If an account exists for this email, a password reset code has been sent."
    if not user:
        return {"msg": generic_msg, "nonce_demo": None, "otp_demo": None}

    otp_code = secrets.randbelow(1000000)
    otp = f"{otp_code:06d}"

    email_body = f"""
Hello {user.name},

We received a request to reset your Offlink password. Use the code below:

Your reset code: {otp}

This code will expire in 10 minutes.

If you didn't request a reset, you can ignore this email.
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1E3A8A; color: white; padding: 20px; text-align: center;
                       border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #1E3A8A; text-align: center;
                        background-color: white; padding: 20px; margin: 20px 0;
                        border-radius: 5px; letter-spacing: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Password reset</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{user.name}</strong>,</p>
                <p>Use the code below to reset your password:</p>
                <div class="otp-code">{otp}</div>
                <p>This code expires in <strong>10 minutes</strong>.</p>
                <p>If you didn't request this, you can ignore this email.</p>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(user.email, "Reset your Offlink password", email_body, html_body)

    nonce = create_challenge(
        db,
        purpose=PURPOSE_PASSWORD_RESET,
        subject=subj,
        code=otp,
        metadata={"user_id": user.id},
    )
    log_otp_dev_only(PURPOSE_PASSWORD_RESET, subj, otp)

    return {
        "msg": generic_msg,
        "nonce_demo": nonce,
        "otp_demo": otp if settings.DEBUG else None,
    }


@router.post("/forgot-password/confirm")
def forgot_password_confirm(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Verify reset code and set a new password (same complexity rules as signup)."""
    email = payload.get("email")
    otp = payload.get("otp")
    nonce = payload.get("nonce")
    new_password = payload.get("new_password")
    confirm_password = payload.get("confirm_password")
    if not email or not otp or not nonce or not new_password or not confirm_password:
        raise HTTPException(
            status_code=422,
            detail="email, otp, nonce, new_password, and confirm_password are required",
        )
    if new_password != confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match")

    _require_strong_password(new_password)

    subj = str(email).strip().lower()
    ok, info = verify_by_nonce(db, nonce=str(nonce).strip(), code=str(otp).strip())
    if not ok or not info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code",
        )
    if info["purpose"] != PURPOSE_PASSWORD_RESET or info["subject"] != subj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code",
        )

    user = db.query(User).filter(func.lower(User.email) == subj).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = security.get_password_hash(new_password)
    db.add(user)

    for rt in (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .all()
    ):
        rt.revoked = True
        db.add(rt)

    db.commit()

    return {"msg": "Password updated. Sign in with your new password."}


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

    user = db.query(User).filter(User.id == rt_record.user_id).first()
    if user:
        # Refresh remains blocked for suspended accounts. They can sign-in again to recover via sync.
        raise_if_account_blocked(user)

    # issue new access token
    access_token = security.create_access_token(subject=str(rt_record.user_id), device_fingerprint=device_fingerprint)
    return {"access_token": access_token, "token_type": "bearer"}

# Get current user info
@router.get("/me")
def get_current_user_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_device_fingerprint: str = Header(None),
):
    """Returns current authenticated user's information including email verification status and wallet balance"""
    from app.models.wallet import Wallet
    from app.models.wallet import DeviceLedgerHead
    from app.api.v1.offline_transaction import GENESIS_PREV_HASH
    from decimal import Decimal
    
    # Get user's wallet (only one wallet per user)
    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id,
        Wallet.is_active == True
    ).first()
    
    # Get wallet balance (user has only one wallet)
    wallet_balance = Decimal(str(wallet.balance)) if wallet else Decimal("0.00")

    # Seed the device ledger chain for fresh installs:
    # return the server-expected (prev_hash, next_sequence) for this (user, device_fingerprint).
    df = (x_device_fingerprint or "").strip()
    head = (
        db.query(DeviceLedgerHead)
        .filter(
            DeviceLedgerHead.user_id == user.id,
            DeviceLedgerHead.device_fingerprint == df,
        )
        .first()
    )
    ledger_prev_hash = head.last_entry_hash if head is not None else GENESIS_PREV_HASH
    ledger_next_sequence = int(head.last_sequence) + 1 if head is not None else 1
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "emailVerified": user.is_email_verified,
        "totalBalance": float(wallet_balance),
        "offlineBalance": float(wallet_balance),  # Same as total since user has only one wallet
        "deviceLedgerPrevHash": ledger_prev_hash,
        "deviceLedgerNextSequence": ledger_next_sequence,
    }

# Logout (revoke refresh token)
@router.post("/logout")
def logout(refresh_token: str = Body(...), db: Session = Depends(get_db)):
    rt_record = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if rt_record:
        rt_record.revoked = True
        db.add(rt_record)
        db.commit()
    return {"msg": "Logged out"}
