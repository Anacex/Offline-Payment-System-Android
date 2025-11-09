"""
Offline transaction endpoints for the offline payment system.
Handles offline transaction creation, signing, syncing, and verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime
from decimal import Decimal

from app.core.db import get_db
from app.core.auth import get_current_user
from app.core.crypto import CryptoManager
from app.models.user import User
from app.models.wallet import Wallet, OfflineTransaction
from app.schemas.wallet import (
    OfflineTransactionCreate, OfflineTransactionRead,
    OfflineTransactionSync, ReceiptVerification
)

router = APIRouter(
    prefix="/api/v1/offline-transactions",
    tags=["offline-transactions"],
    dependencies=[Depends(get_current_user)]
)


@router.post("/create-local", status_code=status.HTTP_201_CREATED)
def create_offline_transaction_local(
    payload: OfflineTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an offline transaction locally (on mobile device).
    This endpoint helps the mobile app prepare the transaction data for signing.
    Returns transaction data that needs to be signed with sender's private key.
    """
    # Validate sender's wallet
    sender_wallet = db.query(Wallet).filter(
        Wallet.id == payload.sender_wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline",
        Wallet.is_active == True
    ).first()
    
    if not sender_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender's offline wallet not found"
        )
    
    # Validate sufficient balance (local check)
    if sender_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance in offline wallet"
        )
    
    # Extract receiver's public key from QR data
    receiver_qr_data = payload.receiver_qr_data
    if not receiver_qr_data.get("public_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code: missing public key"
        )
    
    # Generate nonce for replay attack prevention
    nonce = CryptoManager.generate_nonce()
    
    # Create transaction data for signing
    transaction_data = {
        "sender_wallet_id": payload.sender_wallet_id,
        "receiver_public_key": receiver_qr_data["public_key"],
        "receiver_user_id": receiver_qr_data.get("user_id"),
        "receiver_wallet_id": receiver_qr_data.get("wallet_id"),
        "amount": str(payload.amount),
        "currency": payload.currency,
        "nonce": nonce,
        "timestamp": payload.created_at_device.isoformat()
    }
    
    return {
        "transaction_data": transaction_data,
        "message": "Sign this transaction data with your private key",
        "nonce": nonce
    }


@router.post("/sign-and-store", status_code=status.HTTP_201_CREATED)
def sign_and_store_offline_transaction(
    transaction_data: dict,
    signature: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Store a signed offline transaction locally (simulates mobile local storage).
    In production, this would be stored on the mobile device's local database.
    This endpoint is for demonstration - the actual signing happens on the device.
    """
    # Validate sender's wallet
    sender_wallet_id = transaction_data.get("sender_wallet_id")
    sender_wallet = db.query(Wallet).filter(
        Wallet.id == sender_wallet_id,
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline"
    ).first()
    
    if not sender_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender's wallet not found"
        )
    
    # Verify signature
    if not sender_wallet.public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender's wallet does not have a public key"
        )
    
    is_valid = CryptoManager.verify_signature(
        transaction_data,
        signature,
        sender_wallet.public_key
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transaction signature"
        )
    
    # Create receipt
    receipt = CryptoManager.create_transaction_receipt(
        sender_wallet_id=transaction_data["sender_wallet_id"],
        receiver_public_key=transaction_data["receiver_public_key"],
        amount=float(transaction_data["amount"]),
        currency=transaction_data["currency"],
        nonce=transaction_data["nonce"],
        signature=signature,
        timestamp=transaction_data["timestamp"]
    )
    
    # Update local wallet balance (simulate local ledger update)
    amount = Decimal(transaction_data["amount"])
    sender_wallet.balance -= amount
    db.add(sender_wallet)
    db.commit()
    
    return {
        "message": "Transaction signed and stored locally",
        "receipt": receipt,
        "local_balance": float(sender_wallet.balance),
        "warning": "Keep this receipt as proof. Sync when online to complete transaction."
    }


@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_offline_transactions(
    payload: OfflineTransactionSync,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync offline transactions from mobile device to server.
    This is called when the user comes online.
    Validates all transactions and updates the global ledger.
    """
    synced_transactions = []
    failed_transactions = []
    
    for tx_data in payload.transactions:
        try:
            # Extract transaction details
            transaction_data = tx_data.get("transaction_data", {})
            signature = tx_data.get("signature")
            receipt = tx_data.get("receipt", {})
            
            # Validate sender's wallet
            sender_wallet_id = transaction_data.get("sender_wallet_id")
            sender_wallet = db.query(Wallet).filter(
                Wallet.id == sender_wallet_id,
                Wallet.user_id == current_user.id,
                Wallet.wallet_type == "offline"
            ).first()
            
            if not sender_wallet:
                failed_transactions.append({
                    "transaction": transaction_data,
                    "error": "Sender's wallet not found"
                })
                continue
            
            # Verify signature
            is_valid = CryptoManager.verify_signature(
                transaction_data,
                signature,
                sender_wallet.public_key
            )
            
            if not is_valid:
                failed_transactions.append({
                    "transaction": transaction_data,
                    "error": "Invalid signature"
                })
                continue
            
            # Check for duplicate nonce (replay attack prevention)
            nonce = transaction_data.get("nonce")
            existing_tx = db.query(OfflineTransaction).filter(
                OfflineTransaction.nonce == nonce
            ).first()
            
            if existing_tx:
                failed_transactions.append({
                    "transaction": transaction_data,
                    "error": "Duplicate transaction (replay attack detected)"
                })
                continue
            
            # Create offline transaction record
            offline_tx = OfflineTransaction(
                sender_wallet_id=sender_wallet_id,
                receiver_public_key=transaction_data["receiver_public_key"],
                amount=Decimal(transaction_data["amount"]),
                currency=transaction_data["currency"],
                transaction_signature=signature,
                nonce=nonce,
                receipt_hash=receipt.get("receipt_hash", ""),
                receipt_data=json.dumps(receipt),
                status="synced",
                created_at_device=datetime.fromisoformat(transaction_data["timestamp"]),
                synced_at=datetime.utcnow(),
                device_fingerprint=tx_data.get("device_fingerprint")
            )
            
            db.add(offline_tx)
            synced_transactions.append({
                "nonce": nonce,
                "amount": transaction_data["amount"],
                "status": "synced"
            })
            
        except Exception as e:
            failed_transactions.append({
                "transaction": tx_data,
                "error": str(e)
            })
    
    # Commit all synced transactions
    db.commit()
    
    return {
        "message": f"Synced {len(synced_transactions)} transactions",
        "synced": synced_transactions,
        "failed": failed_transactions,
        "total_synced": len(synced_transactions),
        "total_failed": len(failed_transactions)
    }


@router.post("/verify-receipt", status_code=status.HTTP_200_OK)
def verify_transaction_receipt(
    payload: ReceiptVerification,
    db: Session = Depends(get_db)
):
    """
    Verify a transaction receipt (for receiver to validate payment).
    This can be done offline by the receiver.
    """
    receipt_data = payload.receipt_data
    signature = payload.signature
    sender_public_key = payload.sender_public_key
    
    # Reconstruct transaction data from receipt
    transaction_data = {
        "sender_wallet_id": receipt_data.get("sender_wallet_id"),
        "receiver_public_key": receipt_data.get("receiver_public_key"),
        "amount": receipt_data.get("amount"),
        "currency": receipt_data.get("currency"),
        "nonce": receipt_data.get("nonce"),
        "timestamp": receipt_data.get("timestamp")
    }
    
    # Verify signature
    is_valid = CryptoManager.verify_signature(
        transaction_data,
        signature,
        sender_public_key
    )
    
    # Verify receipt hash
    receipt_hash_calculated = CryptoManager.hash_receipt(receipt_data)
    receipt_hash_provided = receipt_data.get("receipt_hash")
    
    hash_valid = receipt_hash_calculated == receipt_hash_provided
    
    return {
        "valid": is_valid and hash_valid,
        "signature_valid": is_valid,
        "hash_valid": hash_valid,
        "transaction_data": transaction_data,
        "message": "Receipt is valid" if (is_valid and hash_valid) else "Receipt verification failed"
    }


@router.get("/", response_model=List[OfflineTransactionRead])
def list_offline_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str = None,
    limit: int = 50
):
    """Get offline transactions for the authenticated user."""
    # Get user's wallets
    user_wallet_ids = [w.id for w in db.query(Wallet).filter(
        Wallet.user_id == current_user.id,
        Wallet.wallet_type == "offline"
    ).all()]
    
    query = db.query(OfflineTransaction).filter(
        OfflineTransaction.sender_wallet_id.in_(user_wallet_ids)
    )
    
    if status_filter:
        query = query.filter(OfflineTransaction.status == status_filter)
    
    transactions = query.order_by(
        OfflineTransaction.created_at.desc()
    ).limit(limit).all()
    
    return transactions


@router.post("/{transaction_id}/confirm", status_code=status.HTTP_200_OK)
def confirm_offline_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm an offline transaction and transfer funds to receiver's current account.
    This simulates the final settlement on the global ledger.
    """
    # Get transaction
    transaction = db.query(OfflineTransaction).filter(
        OfflineTransaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Validate sender's wallet belongs to current user
    sender_wallet = db.query(Wallet).filter(
        Wallet.id == transaction.sender_wallet_id,
        Wallet.user_id == current_user.id
    ).first()
    
    if not sender_wallet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized to confirm this transaction"
        )
    
    if transaction.status != "synced":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction cannot be confirmed. Current status: {transaction.status}"
        )
    
    # Find receiver's wallet by public key
    receiver_wallet = db.query(Wallet).filter(
        Wallet.public_key == transaction.receiver_public_key,
        Wallet.wallet_type == "offline"
    ).first()
    
    if not receiver_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver's wallet not found"
        )
    
    # Find receiver's current wallet for final settlement
    receiver_current_wallet = db.query(Wallet).filter(
        Wallet.user_id == receiver_wallet.user_id,
        Wallet.wallet_type == "current",
        Wallet.currency == transaction.currency
    ).first()
    
    if not receiver_current_wallet:
        # Create current wallet if doesn't exist
        receiver_current_wallet = Wallet(
            user_id=receiver_wallet.user_id,
            wallet_type="current",
            currency=transaction.currency,
            balance=0
        )
        db.add(receiver_current_wallet)
    
    # Transfer funds to receiver's current account
    receiver_current_wallet.balance += transaction.amount
    
    # Update transaction status
    transaction.status = "confirmed"
    transaction.confirmed_at = datetime.utcnow()
    
    db.add(receiver_current_wallet)
    db.add(transaction)
    db.commit()
    
    return {
        "message": "Transaction confirmed and settled",
        "transaction_id": transaction.id,
        "amount": float(transaction.amount),
        "receiver_balance": float(receiver_current_wallet.balance),
        "status": "confirmed"
    }
