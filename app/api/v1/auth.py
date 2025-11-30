# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets

from app.core import security
from app.core.db import get_db
from app.core.deps import get_current_user
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

    # Always log to console as backup
    print(f"[OTP LOG] Email verification OTP for {email}: {otp} (User ID: {user.id})")

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

# Login step 1: credential check -> send MFA OTP (or skip if email verified)
@router.post("/login")
def login_step1(email: str = Body(...), password: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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

    # For demo return a temporary nonce token to validate OTP step (in prod you would save OTP.)
    nonce = secrets.token_urlsafe(16)
    
    # Always log to console as backup
    print(f"[OTP LOG] Email verification OTP for login {user.email}: {otp} (User ID: {user.id})")
    
    # Return OTP requirement for unverified users
    return {
        "requires_otp": True,
        "nonce_demo": nonce,
        "otp_demo": otp,
        "email_verified": False
    }

# Login step 2: verify OTP -> issue access & refresh token (and verify email if unverified)
@router.post("/login/confirm")
def login_confirm(email: str = Body(...), otp: str = Body(...), nonce: str = Body(...), device_fingerprint: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # In production verify OTP via DB/Redis store keyed to nonce.
    # Here assume otp valid for demo.
    
    # If email is not verified, verify it now after OTP confirmation
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

# Get current user info
@router.get("/me")
def get_current_user_info(user: User = Depends(get_current_user)):
    """Returns current authenticated user's information including email verification status"""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "emailVerified": user.is_email_verified
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
