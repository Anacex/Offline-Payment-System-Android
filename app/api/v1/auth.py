# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import sys
from pathlib import Path

# Add project root to path for logging import
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from log_to_supabase import log_event, log_event_blocking

from app.core import security
from app.core.db import get_db
from app.models import User
from app.models_refresh_token import RefreshToken

router = APIRouter(prefix="/auth", tags=["auth"])

# Import email service
from app.core.email import send_email

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

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        # Log the duplicate email attempt
        log_event("warning", "Signup attempt with existing email", {
            "email": email,
            "existing_user_id": existing_user.id,
            "endpoint": "/auth/signup"
        })
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

    # Log OTP generation for team visibility - CRITICAL: Must be logged
    # Use blocking log to ensure it's written before response is sent
    otp_logged = False
    for attempt in range(3):  # Try up to 3 times
        try:
            otp_logged = log_event_blocking("info", "Email verification OTP generated", {
                "user_id": user.id,
                "email": email,
                "otp": otp,
                "type": "email_verification",
                "endpoint": "/auth/signup",
                "attempt": attempt + 1
            }, timeout=2.0)
            if otp_logged:
                break  # Success, exit retry loop
        except Exception as e:
            if attempt < 2:  # Not the last attempt
                import time
                time.sleep(0.1)  # Small delay before retry
            else:
                # Last attempt failed - log to console as backup
                print(f"[OTP LOG ERROR] Failed to log OTP to Supabase after 3 attempts: {e}")
    
    # Always log to console as backup (even if Supabase logging succeeded)
    print(f"[OTP LOG] Email verification OTP for {email}: {otp} (User ID: {user.id}, Supabase: {'✓' if otp_logged else '✗'})")

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
    
    # Log OTP verification
    log_event("info", "Email verification OTP verified", {
        "user_id": user.id,
        "email": email,
        "otp": otp,
        "type": "email_verification",
        "endpoint": "/auth/verify-email",
        "status": "verified"
    })
    
    return {"msg": "Email verified"}

# Login step 1: credential check -> send MFA OTP
@router.post("/login")
def login_step1(email: str = Body(...), password: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_email_verified:
        raise HTTPException(status_code=401, detail="Email not verified")

    # generate email MFA OTP - 6 digit numeric code
    mfa_otp_code = secrets.randbelow(1000000)  # Generate 0-999999
    mfa_otp = f"{mfa_otp_code:06d}"  # Format as 6-digit string with leading zeros
    # In production save OTP in DB/Redis with expiry; here we print/send for demo
    
    # Send login OTP email with formatted template
    email_body = f"""
Hello {user.name},

You requested a login code. Use the code below to complete your login:

Your login code: {mfa_otp}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email or contact support.
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
            .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #2196F3; text-align: center; 
                        background-color: white; padding: 20px; margin: 20px 0; 
                        border-radius: 5px; letter-spacing: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Login Verification Code</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{user.name}</strong>,</p>
                <p>You requested a login code. Use the code below to complete your login:</p>
                <div class="otp-code">{mfa_otp}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <div class="warning">
                    <p><strong>⚠️ Security Notice:</strong> If you didn't request this code, please ignore this email or contact support immediately.</p>
                </div>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(user.email, "Your login verification code", email_body, html_body)

    # For demo return a temporary nonce token to validate OTP step (in prod you would save OTP.)
    nonce = secrets.token_urlsafe(16)
    
    # Log MFA OTP generation for team visibility - CRITICAL: Must be logged
    # Use blocking log to ensure it's written before response is sent
    otp_logged = False
    for attempt in range(3):  # Try up to 3 times
        try:
            otp_logged = log_event_blocking("info", "Login MFA OTP generated", {
                "user_id": user.id,
                "email": user.email,
                "otp": mfa_otp,
                "nonce": nonce,
                "type": "login_mfa",
                "endpoint": "/auth/login",
                "device_fingerprint": device_fingerprint,
                "attempt": attempt + 1
            }, timeout=2.0)
            if otp_logged:
                break  # Success, exit retry loop
        except Exception as e:
            if attempt < 2:  # Not the last attempt
                import time
                time.sleep(0.1)  # Small delay before retry
            else:
                # Last attempt failed - log to console as backup
                print(f"[OTP LOG ERROR] Failed to log MFA OTP to Supabase after 3 attempts: {e}")
    
    # Always log to console as backup (even if Supabase logging succeeded)
    print(f"[OTP LOG] Login MFA OTP for {user.email}: {mfa_otp} (User ID: {user.id}, Supabase: {'✓' if otp_logged else '✗'})")
    
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

    # Log OTP verification and successful login
    log_event("info", "Login MFA OTP verified - login successful", {
        "user_id": user.id,
        "email": email,
        "otp": otp,
        "nonce": nonce,
        "type": "login_mfa",
        "endpoint": "/auth/login/confirm",
        "status": "verified",
        "device_fingerprint": device_fingerprint
    })

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
