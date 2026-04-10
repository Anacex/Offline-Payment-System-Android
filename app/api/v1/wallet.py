"""
Wallet management endpoints for offline payment system.
Handles wallet creation, balance management, and transfers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from sqlalchemy.orm import Session
from typing import List
import secrets
from decimal import Decimal
from app.core.db import get_db
from app.core.auth import get_current_user
from app.core.crypto import CryptoManager
from app.models.user import User
from app.models.wallet import Wallet, WalletTransfer
from app.schemas.wallet import (
    WalletCreate, WalletRead, WalletTransferCreate,
    WalletTransferRead, QRCodeRequest, QRCodeResponse,
    TopUpRequest, TopUpResponse, TopUpVerifyRequest, TopUpVerifyResponse,
    WalletCreateRequest, WalletCreateResponse, WalletCreateVerifyRequest,
    DeviceSigningKeyUpdate,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from app.core import security
from app.core.config import settings
from app.core.email import send_email
from app.core.otp_service import (
    PURPOSE_TOPUP,
    PURPOSE_WALLET_CREATE,
    create_challenge,
    log_otp_dev_only,
    verify_latest_for_subject,
)
from app.core.wallet_storage import seal_private_key_pem, unseal_private_key_pem

router = APIRouter(prefix="/api/v1/wallets", tags=["wallets"], dependencies=[Depends(get_current_user)])


@router.post("/create-request", response_model=WalletCreateResponse, status_code=status.HTTP_200_OK)
def initiate_wallet_creation(
    payload: WalletCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate wallet creation by sending OTP to user's email.
    User must verify OTP before wallet is actually created.
    Each user can have only one wallet.
    """
    # Check if user already has a wallet (only one wallet per user)
    existing_wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if existing_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a wallet. Each user can have only one wallet."
        )
    
    # Generate OTP (reuse same logic as signup)
    otp_code = secrets.randbelow(1000000)  # Generate 0-999999
    otp = f"{otp_code:06d}"  # Format as 6-digit string with leading zeros

    wsubject = f"{current_user.id}:{payload.wallet_type}"
    create_challenge(
        db,
        purpose=PURPOSE_WALLET_CREATE,
        subject=wsubject,
        code=otp,
        metadata={
            "wallet_type": payload.wallet_type,
            "currency": payload.currency,
            "bank_account_number": payload.bank_account_number,
        },
    )
    log_otp_dev_only(PURPOSE_WALLET_CREATE, wsubject, otp)

    # Send email with OTP
    email_body = f"""
Hello {current_user.name},

You have initiated the creation of a {payload.wallet_type} wallet.

Bank Account Number: {payload.bank_account_number}
Wallet Type: {payload.wallet_type}
Currency: {payload.currency}

Please use the verification code below to complete wallet creation:

Your verification code: {otp}

This code will expire in 10 minutes.

If you didn't initiate this wallet creation, please ignore this email or contact support immediately.
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
            .header {{ background-color: #059669; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #059669; text-align: center; 
                        background-color: white; padding: 20px; margin: 20px 0; 
                        border-radius: 5px; letter-spacing: 5px; }}
            .info-box {{ background-color: white; padding: 15px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #059669; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Wallet Creation Verification</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{current_user.name}</strong>,</p>
                <p>You have initiated the creation of a <strong>{payload.wallet_type}</strong> wallet.</p>
                
                <div class="info-box">
                    <p><strong>Bank Account Number:</strong> {payload.bank_account_number}</p>
                    <p><strong>Wallet Type:</strong> {payload.wallet_type}</p>
                    <p><strong>Currency:</strong> {payload.currency}</p>
                </div>
                
                <p>Please use the verification code below to complete wallet creation:</p>
                <div class="otp-code">{otp}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't initiate this wallet creation, please ignore this email or contact support immediately.</p>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(current_user.email, "Verify your wallet creation", email_body, html_body)

    return WalletCreateResponse(
        msg="Wallet creation initiated. Check your email for verification code.",
        otp_demo=otp if settings.DEBUG else None,
    )


@router.post("/create-verify", response_model=WalletRead, status_code=status.HTTP_201_CREATED)
def verify_and_create_wallet(
    payload: WalletCreateVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify OTP and create wallet with bank account number.
    Each user can have only one wallet.
    """
    # Check if user already has a wallet (only one wallet per user)
    existing_wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if existing_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a wallet. Each user can have only one wallet."
        )
    
    wsubject = f"{current_user.id}:{payload.wallet_type}"
    ok, info = verify_latest_for_subject(
        db,
        purpose=PURPOSE_WALLET_CREATE,
        subject=wsubject,
        code=payload.otp.strip(),
    )
    if not ok or not info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found, expired, or invalid. Please initiate wallet creation again.",
        )
    meta = info.get("metadata") or {}
    if meta.get("wallet_type") != payload.wallet_type or meta.get("currency") != payload.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet type or currency mismatch",
        )
    if meta.get("bank_account_number") != payload.bank_account_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account number mismatch",
        )

    # Create wallet (always offline type with cryptographic keys)
    public_key, private_key = CryptoManager.generate_key_pair()
    wallet = Wallet(
        user_id=current_user.id,
        wallet_type="offline",  # All wallets are offline type
        currency=payload.currency,
        balance=0,
        bank_account_number=payload.bank_account_number,
        public_key=public_key,
        private_key_encrypted=seal_private_key_pem(private_key),
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return wallet


# Keep old endpoint for backward compatibility (deprecated)
@router.post("/", response_model=WalletRead, status_code=status.HTTP_201_CREATED)
def create_wallet(
    payload: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new wallet for the authenticated user.
    DEPRECATED: Use /create-request and /create-verify endpoints instead.
    Each user can have only one wallet. All wallets are offline type with cryptographic keys.
    """
    # Check if user already has a wallet (only one wallet per user)
    existing_wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if existing_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a wallet. Each user can have only one wallet."
        )
    
    # Create wallet (always offline type with cryptographic keys)
    public_key, private_key = CryptoManager.generate_key_pair()
    wallet = Wallet(
        user_id=current_user.id,
        wallet_type="offline",  # All wallets are offline type
        currency=payload.currency,
        balance=0,
        bank_account_number=payload.bank_account_number if hasattr(payload, 'bank_account_number') and payload.bank_account_number else "N/A",
        public_key=public_key,
        private_key_encrypted=seal_private_key_pem(private_key),
    )
    
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    
    return wallet


@router.get("/", response_model=List[WalletRead])
def list_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all wallets for the authenticated user."""
    wallets = db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).all()
    return wallets


@router.get("/{wallet_id}", response_model=WalletRead)
def get_wallet(
    wallet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific wallet details."""
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    return wallet


@router.post("/transfer", response_model=WalletTransferRead, status_code=status.HTTP_201_CREATED)
def transfer_between_wallets(
    payload: WalletTransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transfer money between user's wallets (e.g., preload offline wallet from current wallet).
    This requires online connectivity and updates the global ledger immediately.
    """
    # Validate both wallets belong to current user
    from_wallet = db.query(Wallet).filter(
        Wallet.id == payload.from_wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    to_wallet = db.query(Wallet).filter(
        Wallet.id == payload.to_wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if not from_wallet or not to_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both wallets not found"
        )
    
    # Validate sufficient balance
    if from_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance in source wallet"
        )
    
    # Validate currency match
    if from_wallet.currency != payload.currency or to_wallet.currency != payload.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currency mismatch between wallets"
        )
    
    # Perform transfer
    from_wallet.balance -= payload.amount
    to_wallet.balance += payload.amount
    
    # Create transfer record
    reference = f"WT-{secrets.token_hex(8).upper()}"
    transfer = WalletTransfer(
        user_id=current_user.id,
        from_wallet_id=from_wallet.id,
        to_wallet_id=to_wallet.id,
        amount=payload.amount,
        currency=payload.currency,
        status="completed",
        reference=reference
    )
    
    db.add(from_wallet)
    db.add(to_wallet)
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    
    return transfer


@router.get("/transfers/history", response_model=List[WalletTransferRead])
def get_transfer_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """Get wallet transfer history for the authenticated user."""
    transfers = db.query(WalletTransfer).filter(
        WalletTransfer.user_id == current_user.id
    ).order_by(WalletTransfer.timestamp.desc()).limit(limit).all()
    
    return transfers


@router.post("/qr-code", response_model=QRCodeResponse)
def generate_qr_code(
    payload: QRCodeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate QR code for receiving offline payments.
    QR code contains receiver's public key and wallet information.
    """
    # Get wallet
    wallet = db.query(Wallet).filter(
        Wallet.id == payload.wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline",
        Wallet.is_active == True
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offline wallet not found"
        )
    
    if not wallet.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet does not have a public key"
        )
    
    # Create Payee QR payload (new MVP format)
    # Use device fingerprint as deviceId, user ID as payeeId
    from app.core.device_fingerprint import get_device_fingerprint

    device_id = get_device_fingerprint(request)
    
    qr_data = CryptoManager.create_payee_qr_payload(
        payee_id=str(current_user.id),
        payee_name=current_user.name,
        device_id=device_id
    )
    
    # Generate QR code image
    import qrcode
    import io
    import base64
    import json
    
    qr = qrcode.QRCode(
        version=None,  # Auto-detect version
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return QRCodeResponse(
        qr_data=qr_data,
        qr_image_base64=img_base64
    )


@router.put("/{wallet_id}/offline-signing-key", response_model=WalletRead)
def register_device_offline_signing_key(
    wallet_id: int,
    payload: DeviceSigningKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Replace offline wallet public key with device-held key (Android Keystore).
    Clears server-side extractable private key material.
    """
    try:
        serialization.load_pem_public_key(
            payload.public_key_pem.encode("utf-8"),
            backend=default_backend(),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid public_key_pem",
        )

    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline",
        Wallet.is_active == True,
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offline wallet not found",
        )

    wallet.public_key = payload.public_key_pem
    wallet.private_key_encrypted = None
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/{wallet_id}/private-key")
def get_wallet_private_key(
    wallet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get private key for offline wallet.
    WARNING: This is sensitive data. In production, this should require additional authentication.
    The private key should be stored securely on the user's device only.
    """
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline"
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offline wallet not found"
        )
    
    if not wallet.private_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet uses device-bound signing; private key is not available from the server",
        )

    try:
        pem_plain = unseal_private_key_pem(wallet.private_key_encrypted)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    if not pem_plain:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet key material is empty",
        )

    return {
        "wallet_id": wallet.id,
        "private_key": pem_plain,
        "warning": "Store this securely on your device. Never share it.",
    }


@router.post("/topup", response_model=TopUpResponse, status_code=status.HTTP_200_OK)
def request_topup(
    payload: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Request wallet top-up. Validates password, checks limits, generates OTP and sends email.
    Reuses the same OTP sending service as signup.
    """
    # Verify password
    if not security.verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Get wallet
    wallet = db.query(Wallet).filter(
        Wallet.id == payload.wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    # Validate offline wallet limit (5000 PKR max)
    MAX_OFFLINE_WALLET_BALANCE = Decimal("5000.00")
    new_balance = wallet.balance + payload.amount
    
    if wallet.wallet_type == "offline" and new_balance > MAX_OFFLINE_WALLET_BALANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Top-up would exceed maximum offline wallet balance of {MAX_OFFLINE_WALLET_BALANCE} PKR"
        )
    
    # Generate OTP (reuse same logic as signup)
    otp_code = secrets.randbelow(1000000)  # Generate 0-999999
    otp = f"{otp_code:06d}"  # Format as 6-digit string with leading zeros

    tsubject = f"{current_user.id}:topup:{payload.wallet_id}"
    create_challenge(
        db,
        purpose=PURPOSE_TOPUP,
        subject=tsubject,
        code=otp,
        metadata={
            "amount": str(payload.amount),
            "bank_account_number": payload.bank_account_number,
        },
    )
    log_otp_dev_only(PURPOSE_TOPUP, tsubject, otp)

    # Send email with OTP (reuse same email service as signup)
    email_body = f"""
Hello {current_user.name},

You have requested to top up your {wallet.wallet_type} wallet.

Top-up amount: {payload.amount} {wallet.currency}
Bank Account Number: {payload.bank_account_number}
Wallet ID: {wallet.id}

Please use the verification code below to complete your top-up:

Your verification code: {otp}

This code will expire in 10 minutes.

If you didn't request this top-up, please ignore this email or contact support immediately.
"""
    
    # HTML version for better formatting (reuse same template style as signup)
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #8B5CF6; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #8B5CF6; text-align: center; 
                        background-color: white; padding: 20px; margin: 20px 0; 
                        border-radius: 5px; letter-spacing: 5px; }}
            .info-box {{ background-color: white; padding: 15px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #8B5CF6; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Wallet Top-Up Verification</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{current_user.name}</strong>,</p>
                <p>You have requested to top up your <strong>{wallet.wallet_type}</strong> wallet.</p>
                
                <div class="info-box">
                    <p><strong>Top-up Amount:</strong> {payload.amount} {wallet.currency}</p>
                    <p><strong>Bank Account Number:</strong> {payload.bank_account_number}</p>
                    <p><strong>Wallet ID:</strong> {wallet.id}</p>
                    <p><strong>Current Balance:</strong> {wallet.balance} {wallet.currency}</p>
                    <p><strong>New Balance:</strong> {new_balance} {wallet.currency}</p>
                </div>
                
                <p>Please use the verification code below to complete your top-up:</p>
                <div class="otp-code">{otp}</div>
                <p>This code will expire in <strong>10 minutes</strong>.</p>
                <p>If you didn't request this top-up, please ignore this email or contact support immediately.</p>
            </div>
            <div class="footer">
                <p>Offline Payment System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(current_user.email, "Verify your wallet top-up", email_body, html_body)

    return TopUpResponse(
        msg="Top-up request received. Check your email for verification code.",
        otp_demo=otp if settings.DEBUG else None,
    )


@router.post("/topup/verify", response_model=TopUpVerifyResponse, status_code=status.HTTP_200_OK)
def verify_topup(
    payload: TopUpVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify top-up OTP and update wallet balance.
    """
    # Get wallet
    wallet = db.query(Wallet).filter(
        Wallet.id == payload.wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.is_active == True
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    tsubject = f"{current_user.id}:topup:{payload.wallet_id}"
    ok, info = verify_latest_for_subject(
        db,
        purpose=PURPOSE_TOPUP,
        subject=tsubject,
        code=payload.otp.strip(),
    )
    if not ok or not info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found, expired, or invalid. Please request a new top-up.",
        )
    meta = info.get("metadata") or {}
    try:
        topup_amount = Decimal(str(meta.get("amount", "0")))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid top-up metadata",
        )

    # Validate offline wallet limit again (in case balance changed)
    MAX_OFFLINE_WALLET_BALANCE = Decimal("5000.00")
    new_balance = wallet.balance + topup_amount
    
    if wallet.wallet_type == "offline" and new_balance > MAX_OFFLINE_WALLET_BALANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Top-up would exceed maximum offline wallet balance of {MAX_OFFLINE_WALLET_BALANCE} PKR"
        )

    # Update wallet balance
    wallet.balance += topup_amount
    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return TopUpVerifyResponse(
        msg="Top-up successful. Wallet balance updated.",
        wallet=wallet
    )
