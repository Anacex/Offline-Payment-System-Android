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
from datetime import datetime

from app.core.db import get_db
from app.core.auth import get_current_user
from app.core.crypto import CryptoManager
from app.models.user import User
from app.models.wallet import Wallet, WalletTransfer
from app.schemas.wallet import (
    WalletCreate, WalletRead, WalletTransferCreate, 
    WalletTransferRead, QRCodeRequest, QRCodeResponse,
    TopUpRequest, TopUpResponse, TopUpVerifyRequest, TopUpVerifyResponse,
    WalletCreateRequest, WalletCreateResponse, WalletCreateVerifyRequest
)
from app.core import security
from app.core.email import send_email

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
    
    # Store OTP with wallet creation data
    otp_key = f"wallet_create_{current_user.id}_{payload.wallet_type}"
    _wallet_create_otp_store[otp_key] = (
        otp, 
        datetime.utcnow(), 
        payload.wallet_type, 
        payload.currency, 
        payload.bank_account_number
    )
    
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
    
    # Always log to console as backup
    print(f"[OTP LOG] Wallet creation OTP for {payload.wallet_type} wallet (User: {current_user.email}): {otp}")
    
    return WalletCreateResponse(
        msg="Wallet creation initiated. Check your email for verification code.",
        otp_demo=otp  # For development/testing
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
    
    # Verify OTP
    otp_key = f"wallet_create_{current_user.id}_{payload.wallet_type}"
    stored_otp_data = _wallet_create_otp_store.get(otp_key)
    
    if not stored_otp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found or expired. Please initiate wallet creation again."
        )
    
    stored_otp, otp_timestamp, wallet_type, currency, bank_account_number = stored_otp_data
    
    # Check OTP expiration (10 minutes)
    otp_age = datetime.utcnow() - otp_timestamp
    if otp_age.total_seconds() > 600:  # 10 minutes
        _wallet_create_otp_store.pop(otp_key, None)  # Remove expired OTP
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please initiate wallet creation again."
        )
    
    # Verify OTP matches
    if stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )
    
    # Verify wallet type and currency match
    if wallet_type != payload.wallet_type or currency != payload.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet type or currency mismatch"
        )
    
    # Verify bank account number matches
    if bank_account_number != payload.bank_account_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account number mismatch"
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
        private_key_encrypted=private_key  # TODO: Encrypt properly in production
    )
    
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    
    # Remove used OTP
    _wallet_create_otp_store.pop(otp_key, None)
    
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
        private_key_encrypted=private_key  # TODO: Encrypt properly in production
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
    device_id = get_device_fingerprint()  # Get from request headers or generate
    
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
            detail="Wallet does not have a private key"
        )
    
    # In production, decrypt with user's password/PIN
    # For now, return as-is (should be encrypted)
    return {
        "wallet_id": wallet.id,
        "private_key": wallet.private_key_encrypted,
        "warning": "Store this securely on your device. Never share it."
    }


# In-memory OTP storage (for demo - use Redis/DB in production)
# Key: f"topup_{wallet_id}_{user_id}", Value: (otp, timestamp, amount, bank_account_number)
_topup_otp_store: dict[str, tuple[str, datetime, Decimal, str]] = {}

# In-memory OTP storage for wallet creation
# Key: f"wallet_create_{user_id}_{wallet_type}", Value: (otp, timestamp, wallet_type, currency, bank_account_number)
_wallet_create_otp_store: dict[str, tuple[str, datetime, str, str, str]] = {}


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
    
    # Store OTP with amount and bank account number (keyed by wallet_id and user_id for verification)
    otp_key = f"topup_{payload.wallet_id}_{current_user.id}"
    _topup_otp_store[otp_key] = (otp, datetime.utcnow(), payload.amount, payload.bank_account_number)
    
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
    
    # Always log to console as backup
    print(f"[OTP LOG] Top-up OTP for wallet {wallet.id} (User: {current_user.email}): {otp}")
    
    return TopUpResponse(
        msg="Top-up request received. Check your email for verification code.",
        otp_demo=otp  # For development/testing
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
    
    # Verify OTP
    otp_key = f"topup_{payload.wallet_id}_{current_user.id}"
    stored_otp_data = _topup_otp_store.get(otp_key)
    
    if not stored_otp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found or expired. Please request a new top-up."
        )
    
    stored_otp, otp_timestamp, topup_amount, bank_account_number = stored_otp_data
    
    # Check OTP expiration (10 minutes)
    otp_age = datetime.utcnow() - otp_timestamp
    if otp_age.total_seconds() > 600:  # 10 minutes
        _topup_otp_store.pop(otp_key, None)  # Remove expired OTP
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new top-up."
        )
    
    # Verify OTP matches
    if stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )
    
    # Validate offline wallet limit again (in case balance changed)
    MAX_OFFLINE_WALLET_BALANCE = Decimal("5000.00")
    new_balance = wallet.balance + topup_amount
    
    if wallet.wallet_type == "offline" and new_balance > MAX_OFFLINE_WALLET_BALANCE:
        _topup_otp_store.pop(otp_key, None)  # Remove used OTP
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Top-up would exceed maximum offline wallet balance of {MAX_OFFLINE_WALLET_BALANCE} PKR"
        )
    
    # Update wallet balance
    wallet.balance += topup_amount
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    
    # Remove used OTP
    _topup_otp_store.pop(otp_key, None)
    
    return TopUpVerifyResponse(
        msg="Top-up successful. Wallet balance updated.",
        wallet=wallet
    )
