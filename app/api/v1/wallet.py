"""
Wallet management endpoints for offline payment system.
Handles wallet creation, balance management, and transfers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
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
    WalletTransferRead, QRCodeRequest, QRCodeResponse
)

router = APIRouter(prefix="/api/v1/wallets", tags=["wallets"], dependencies=[Depends(get_current_user)])


@router.post("/", response_model=WalletRead, status_code=status.HTTP_201_CREATED)
def create_wallet(
    payload: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new wallet (current or offline) for the authenticated user.
    For offline wallets, generates RSA key pair automatically.
    """
    # Check if user already has a wallet of this type
    existing_wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == payload.wallet_type,
        Wallet.is_active == True
    ).first()
    
    if existing_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User already has an active {payload.wallet_type} wallet"
        )
    
    # Create wallet
    wallet = Wallet(
        user_id=current_user.id,
        wallet_type=payload.wallet_type,
        currency=payload.currency,
        balance=0
    )
    
    # Generate keys for offline wallet
    if payload.wallet_type == "offline":
        public_key, private_key = CryptoManager.generate_key_pair()
        wallet.public_key = public_key
        # In production, encrypt private key with user's password/PIN
        # For now, we'll encrypt with a placeholder (user should store securely on device)
        wallet.private_key_encrypted = private_key  # TODO: Encrypt properly
    
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
    
    # Create QR payload
    qr_data = CryptoManager.create_qr_payload(
        public_key=wallet.public_key,
        user_id=current_user.id,
        wallet_id=wallet.id
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
