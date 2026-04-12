"""
Offline transaction endpoints for the offline payment system.
Handles offline transaction creation, signing, syncing, and verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.core.db import get_db
from app.core.auth import get_current_user
from app.core.crypto import CryptoManager
from app.models.user import User
from app.models.wallet import Wallet, OfflineTransaction, OfflineReceiverSync, DeviceLedgerHead
from app.schemas.wallet import (
    OfflineTransactionCreate, OfflineTransactionRead,
    OfflineTransactionSync, ReceiptVerification
)

router = APIRouter(
    prefix="/api/v1/offline-transactions",
    tags=["offline-transactions"],
)


# Must match Android [com.offlinepayment.security.OfflineLedgerChain.GENESIS_PREV_HASH].
GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def _ledger_entry_hash_hex(prev_hex: str, integrity_canonical_json: str) -> str:
    h = hashlib.sha256()
    h.update(f"{prev_hex}|{integrity_canonical_json}".encode("utf-8"))
    return h.hexdigest()


def _is_hex64(h: str) -> bool:
    if not isinstance(h, str) or len(h) != 64:
        return False
    try:
        int(h, 16)
        return True
    except ValueError:
        return False


def _device_fp_key(tx_data: dict) -> str:
    v = tx_data.get("device_fingerprint")
    return (v or "").strip() if isinstance(v, str) else ""


def _ledger_payload_status(tx_data: dict) -> str:
    """none = no chain fields; partial = inconsistent; full = all four present."""
    prev = tx_data.get("ledger_prev_hash")
    entry = tx_data.get("ledger_entry_hash")
    seq = tx_data.get("ledger_sequence")
    canon = tx_data.get("integrity_canonical_json")
    present = [
        prev is not None and str(prev).strip() != "",
        entry is not None and str(entry).strip() != "",
        seq is not None,
        canon is not None and str(canon).strip() != "",
    ]
    if not any(present):
        return "none"
    if all(present):
        return "full"
    return "partial"


def _verify_ledger_chain(
    tx_data: dict,
    db: Session,
    user_id: int,
) -> Optional[str]:
    """
    Validates hash-chained ledger payload for this sync row.
    Returns None if OK or chain not used; otherwise a machine-readable error token.
    """
    st = _ledger_payload_status(tx_data)
    if st == "none":
        return None
    if st == "partial":
        return "LEDGER_INTEGRITY_INCOMPLETE_FIELDS"

    prev = str(tx_data.get("ledger_prev_hash")).strip()
    entry = str(tx_data.get("ledger_entry_hash")).strip()
    canon = str(tx_data.get("integrity_canonical_json"))
    try:
        seq = int(tx_data.get("ledger_sequence"))
    except (TypeError, ValueError):
        return "LEDGER_INTEGRITY_INVALID_SEQUENCE"
    if seq < 1:
        return "LEDGER_INTEGRITY_INVALID_SEQUENCE"

    if not _is_hex64(prev) or not _is_hex64(entry):
        return "LEDGER_INTEGRITY_INVALID_HASH_FORMAT"

    fp_key = _device_fp_key(tx_data)

    exp_prev, exp_seq = _get_expected_ledger_state(db, user_id, fp_key)
    if prev != exp_prev:
        return "LEDGER_INTEGRITY_PREV_MISMATCH"
    if seq != exp_seq:
        return "LEDGER_INTEGRITY_SEQUENCE_MISMATCH"

    computed = _ledger_entry_hash_hex(prev, canon)
    if computed.lower() != entry.lower():
        return "LEDGER_INTEGRITY_HASH_MISMATCH"

    return None


def _get_expected_ledger_state(db: Session, user_id: int, device_fp: str) -> Tuple[str, int]:
    key = (device_fp or "").strip()
    row = (
        db.query(DeviceLedgerHead)
        .filter(
            DeviceLedgerHead.user_id == user_id,
            DeviceLedgerHead.device_fingerprint == key,
        )
        .first()
    )
    if row:
        return (row.last_entry_hash, int(row.last_sequence) + 1)
    return (GENESIS_PREV_HASH, 1)


def _persist_ledger_head(db: Session, user_id: int, device_fp: str, entry_hash: str, sequence: int) -> None:
    key = (device_fp or "").strip()
    row = (
        db.query(DeviceLedgerHead)
        .filter(
            DeviceLedgerHead.user_id == user_id,
            DeviceLedgerHead.device_fingerprint == key,
        )
        .first()
    )
    if not row:
        db.add(
            DeviceLedgerHead(
                user_id=user_id,
                device_fingerprint=key,
                last_entry_hash=entry_hash,
                last_sequence=sequence,
            )
        )
    else:
        row.last_entry_hash = entry_hash
        row.last_sequence = sequence


def _sync_one_receiver_row(
    tx_data: dict,
    current_user: User,
    db: Session,
    results: list,
) -> None:
    """
    Receiver attestation: RSA signature + hash chain. Does not change wallet balances
    (sender sync is authoritative for balances).
    """
    transaction_data = tx_data.get("transaction_data", {})
    signature = (tx_data.get("signature") or "").strip()
    receipt = tx_data.get("receipt") or {}
    if not isinstance(receipt, dict):
        receipt = {}
    transaction_reference = transaction_data.get("nonce") or tx_data.get("txId") or tx_data.get("transaction_id")

    required_fields = [
        "receiver_wallet_id",
        "amount",
        "currency",
        "nonce",
        "timestamp",
        "payer_id",
        "payee_id",
        "tx_id",
    ]
    missing = [f for f in required_fields if transaction_data.get(f) in (None, "")]
    if missing:
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": f"Missing required fields: {', '.join(missing)}",
            }
        )
        return

    nonce = str(transaction_data.get("nonce")).strip()
    existing = (
        db.query(OfflineReceiverSync)
        .filter(
            OfflineReceiverSync.user_id == current_user.id,
            OfflineReceiverSync.payment_nonce == nonce,
        )
        .first()
    )
    if existing:
        results.append(
            {
                "transaction_id": existing.id,
                "reference": transaction_reference,
                "result": "synced",
                "error_reason": None,
            }
        )
        return

    if _is_placeholder_signature(signature):
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": "Invalid or missing transaction signature",
            }
        )
        return

    try:
        rwid = int(transaction_data["receiver_wallet_id"])
    except (TypeError, ValueError):
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": "Invalid receiver_wallet_id",
            }
        )
        return

    recv_wallet = (
        db.query(Wallet)
        .filter(
            Wallet.id == rwid,
            Wallet.user_id == current_user.id,
            Wallet.wallet_type == "offline",
        )
        .first()
    )
    if not recv_wallet or not recv_wallet.public_key:
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": "Receiver wallet not found or has no public key",
            }
        )
        return

    tx_for_verify = {
        "amount": str(transaction_data["amount"]),
        "currency": str(transaction_data["currency"]),
        "direction": "RECEIVED",
        "nonce": str(transaction_data["nonce"]),
        "payee_id": str(transaction_data["payee_id"]),
        "payer_id": str(transaction_data["payer_id"]),
        "receiver_wallet_id": rwid,
        "timestamp": str(transaction_data["timestamp"]),
        "tx_id": str(transaction_data["tx_id"]),
    }
    if not CryptoManager.verify_signature(tx_for_verify, signature, recv_wallet.public_key):
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": "Signature verification failed",
            }
        )
        return

    ledger_err = _verify_ledger_chain(tx_data, db, current_user.id)
    if ledger_err:
        _flag_user_for_ledger_fraud(db, current_user.id, ledger_err)
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": ledger_err,
            }
        )
        return

    try:
        amount = Decimal(str(transaction_data["amount"]))
        if amount <= 0:
            results.append(
                {
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": "Amount must be greater than 0",
                }
            )
            return
    except (InvalidOperation, ValueError, TypeError):
        results.append(
            {
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": "Invalid amount format",
            }
        )
        return

    ts_raw = str(transaction_data.get("timestamp", "")).strip()
    try:
        created_dev = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        created_dev = datetime.utcnow()

    row = OfflineReceiverSync(
        user_id=current_user.id,
        receiver_wallet_id=rwid,
        amount=amount,
        currency=str(transaction_data["currency"]),
        payment_nonce=nonce,
        tx_id=str(transaction_data["tx_id"]).strip(),
        payer_id=str(transaction_data["payer_id"]).strip(),
        payee_id=str(transaction_data["payee_id"]).strip(),
        transaction_signature=signature,
        receipt_hash=str(receipt.get("receipt_hash", "") or ""),
        receipt_data=json.dumps(receipt) if receipt else "{}",
        device_fingerprint=tx_data.get("device_fingerprint"),
        created_at_device=created_dev,
    )
    db.add(row)
    db.flush()

    if _ledger_payload_status(tx_data) == "full":
        _persist_ledger_head(
            db,
            current_user.id,
            _device_fp_key(tx_data),
            str(tx_data.get("ledger_entry_hash")).strip(),
            int(tx_data.get("ledger_sequence")),
        )
        db.flush()

    results.append(
        {
            "transaction_id": row.id,
            "reference": transaction_reference,
            "result": "synced",
            "error_reason": None,
        }
    )


def _flag_user_for_ledger_fraud(db: Session, user_id: int, ledger_error_code: str) -> None:
    """Suspend account and queue for human review when chained-ledger sync fails."""
    user = db.get(User, user_id)
    if not user:
        return
    user.account_blocked = True
    user.fraud_review_pending = True
    user.account_blocked_reason = (
        f"Device ledger integrity check failed during sync ({ledger_error_code}). "
        "Queued for manual agent review."
    )
    user.account_blocked_at = datetime.utcnow()
    db.add(user)


def _is_placeholder_signature(signature: str) -> bool:
    """Reject MVP / unsigned client payloads (FYP-2 requires RSA-PSS)."""
    if not signature or not str(signature).strip():
        return True
    s = str(signature).strip()
    upper = s.upper()
    if "PLACEHOLDER" in upper or "UNSIGNED" in upper:
        return True
    if s in ("placeholder_signature", "unsigned-placeholder"):
        return True
    return False


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
        # Format amount with two decimal places for consistent serialization
        "amount": format(payload.amount, ".2f"),
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
    
    Performs lightweight validation and updates wallet balances.
    Returns detailed results for each transaction (synced or failed).
    """
    results = []
    
    for tx_data in payload.transactions:
        transaction_id = None
        transaction_reference = None
        result_status = "failed"
        error_reason = None
        
        try:
            # Extract transaction details
            transaction_data = tx_data.get("transaction_data", {})
            signature = (tx_data.get("signature") or "").strip()
            receipt = tx_data.get("receipt", {})

            direction = str(transaction_data.get("direction") or "").strip().upper()
            if direction == "RECEIVED":
                _sync_one_receiver_row(tx_data, current_user, db, results)
                continue

            # Get transaction reference (nonce or txId)
            transaction_reference = transaction_data.get("nonce") or tx_data.get("txId") or tx_data.get("transaction_id")
            
            # Validation 1: Required fields present
            required_fields = ["sender_wallet_id", "receiver_public_key", "amount", "currency", "nonce"]
            missing_fields = [field for field in required_fields if not transaction_data.get(field)]
            if missing_fields:
                error_reason = f"Missing required fields: {', '.join(missing_fields)}"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue
            
            # Validation 3: Nonce is unique (per sender; globally unique in DB)
            nonce = transaction_data.get("nonce")
            existing_tx = db.query(OfflineTransaction).filter(
                OfflineTransaction.nonce == nonce
            ).first()
            
            if existing_tx:
                error_reason = "Duplicate transaction for this sender (nonce already exists)"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue
            
            if _is_placeholder_signature(signature):
                error_reason = "Invalid or missing transaction signature"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue

            # Validation 4: Sender wallet exists
            sender_wallet_id = transaction_data.get("sender_wallet_id")
            sender_wallet = db.query(Wallet).filter(
                Wallet.id == sender_wallet_id,
                Wallet.user_id == current_user.id,
                Wallet.wallet_type == "offline"
            ).first()
            
            if not sender_wallet:
                error_reason = "Sender wallet not found or does not belong to user"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue

            if not sender_wallet.public_key:
                error_reason = "Sender wallet has no registered public key"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue

            tx_for_verify = {
                "amount": str(transaction_data["amount"]),
                "currency": str(transaction_data["currency"]),
                "nonce": str(transaction_data["nonce"]),
                "receiver_public_key": str(transaction_data["receiver_public_key"]),
                "sender_wallet_id": int(transaction_data["sender_wallet_id"]),
                "timestamp": str(transaction_data["timestamp"]),
            }
            if not CryptoManager.verify_signature(tx_for_verify, signature, sender_wallet.public_key):
                error_reason = "Signature verification failed"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue

            ledger_err = _verify_ledger_chain(tx_data, db, current_user.id)
            if ledger_err:
                _flag_user_for_ledger_fraud(db, current_user.id, ledger_err)
                error_reason = ledger_err
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason,
                })
                continue

            # Validation 5a: Sender has sufficient balance
            try:
                current_balance = Decimal(str(sender_wallet.balance))
            except Exception:
                error_reason = "Invalid sender balance"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue
            
            # Validation 5: Amount > 0
            try:
                amount = Decimal(str(transaction_data["amount"]))
                if amount <= 0:
                    error_reason = "Amount must be greater than 0"
                    results.append({
                        "transaction_id": None,
                        "reference": transaction_reference,
                        "result": "failed",
                        "error_reason": error_reason
                    })
                    continue
            except (ValueError, TypeError, InvalidOperation):
                error_reason = "Invalid amount format"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue
            
            # Validation 6: Balance check (after amount parsed)
            if current_balance < amount:
                error_reason = "Insufficient balance in sender wallet"
                results.append({
                    "transaction_id": None,
                    "reference": transaction_reference,
                    "result": "failed",
                    "error_reason": error_reason
                })
                continue
            
            # All validations passed - create transaction record
            offline_tx = OfflineTransaction(
                sender_wallet_id=sender_wallet_id,
                receiver_public_key=transaction_data["receiver_public_key"],
                amount=amount,
                currency=transaction_data["currency"],
                transaction_signature=signature,
                nonce=nonce,
                receipt_hash=receipt.get("receipt_hash", ""),
                receipt_data=json.dumps(receipt) if receipt else "{}",
                status="synced",
                created_at_device=datetime.fromisoformat(transaction_data.get("timestamp", datetime.utcnow().isoformat())),
                synced_at=datetime.utcnow(),
                device_fingerprint=tx_data.get("device_fingerprint")
            )
            
            db.add(offline_tx)
            db.flush()  # Flush to get the transaction ID
            
            transaction_id = offline_tx.id

            if _ledger_payload_status(tx_data) == "full":
                _persist_ledger_head(
                    db,
                    current_user.id,
                    _device_fp_key(tx_data),
                    str(tx_data.get("ledger_entry_hash")).strip(),
                    int(tx_data.get("ledger_sequence")),
                )
                db.flush()
            
            # Update sender wallet balance (deduct amount)
            sender_wallet.balance = Decimal(str(sender_wallet.balance)) - amount
            db.add(sender_wallet)
            
            # Update receiver wallet balance (add amount)
            # Find receiver's wallet by public key
            receiver_wallet = db.query(Wallet).filter(
                Wallet.public_key == transaction_data["receiver_public_key"],
                Wallet.wallet_type == "offline"
            ).first()
            
            if receiver_wallet:
                receiver_wallet.balance = Decimal(str(receiver_wallet.balance)) + amount
                db.add(receiver_wallet)
            
            # Success - transaction synced
            result_status = "synced"
            results.append({
                "transaction_id": transaction_id,
                "reference": transaction_reference,
                "result": "synced",
                "error_reason": None
            })
            
        except Exception as e:
            # Catch any unexpected errors
            error_reason = f"Server error: {str(e)}"
            results.append({
                "transaction_id": None,
                "reference": transaction_reference,
                "result": "failed",
                "error_reason": error_reason
            })
    
    # Commit all changes
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # If commit fails, mark all as failed
        for result in results:
            if result["result"] == "synced":
                result["result"] = "failed"
                result["error_reason"] = f"Database commit failed: {str(e)}"
    
    return {
        "message": f"Processed {len(results)} transactions",
        "results": results,
        "total_synced": sum(1 for r in results if r["result"] == "synced"),
        "total_failed": sum(1 for r in results if r["result"] == "failed")
    }


@router.post("/offline-sync", status_code=status.HTTP_200_OK)
def sync_offline_transactions_alias(
    payload: OfflineTransactionSync,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Alias endpoint for cleaner semantics.
    Forwards to /api/v1/offline-transactions/sync with identical logic.
    """
    return sync_offline_transactions(payload=payload, current_user=current_user, db=db)


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
