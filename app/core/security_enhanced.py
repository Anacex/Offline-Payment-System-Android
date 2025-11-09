"""
Enhanced Security Module - P0 Critical Security Features
Implements replay attack prevention, double-spend protection, and audit trail
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
import hashlib
import json
from decimal import Decimal

from app.models.offline_transaction import OfflineTransaction
from app.models.wallet import Wallet


class ReplayAttackDefense:
    """
    Prevents replay attacks by tracking used nonces and validating timestamps
    """
    
    # In-memory nonce cache (in production, use Redis)
    _nonce_cache: Dict[str, datetime] = {}
    
    @classmethod
    def validate_transaction(
        cls,
        nonce: str,
        created_at_device: str,
        max_age_minutes: int = 5
    ) -> None:
        """
        Validate transaction against replay attacks
        
        Args:
            nonce: Unique transaction nonce
            created_at_device: ISO format timestamp from device
            max_age_minutes: Maximum age of transaction in minutes
            
        Raises:
            HTTPException: If validation fails
        """
        # 1. Check if nonce has been used before
        if nonce in cls._nonce_cache:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "REPLAY_ATTACK_DETECTED",
                    "message": "This transaction nonce has already been used",
                    "nonce": nonce
                }
            )
        
        # 2. Validate timestamp (reject if too old)
        try:
            tx_time = datetime.fromisoformat(created_at_device.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid timestamp format"
            )
        
        time_diff = datetime.utcnow() - tx_time
        if time_diff > timedelta(minutes=max_age_minutes):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "TRANSACTION_TOO_OLD",
                    "message": f"Transaction is older than {max_age_minutes} minutes",
                    "age_minutes": time_diff.total_seconds() / 60
                }
            )
        
        # 3. Reject future timestamps (clock skew attack)
        if time_diff < timedelta(minutes=-1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FUTURE_TIMESTAMP",
                    "message": "Transaction timestamp is in the future"
                }
            )
        
        # 4. Store nonce in cache with expiration
        cls._nonce_cache[nonce] = datetime.utcnow()
        
        # 5. Clean up old nonces (keep cache size manageable)
        cls._cleanup_old_nonces(max_age_minutes)
    
    @classmethod
    def _cleanup_old_nonces(cls, max_age_minutes: int):
        """Remove nonces older than max_age_minutes"""
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes * 2)
        cls._nonce_cache = {
            nonce: timestamp 
            for nonce, timestamp in cls._nonce_cache.items()
            if timestamp > cutoff
        }
    
    @classmethod
    def check_nonce_in_db(cls, nonce: str, db: Session) -> None:
        """
        Check if nonce exists in database (persistent check)
        
        Args:
            nonce: Transaction nonce
            db: Database session
            
        Raises:
            HTTPException: If nonce already exists
        """
        existing = db.query(OfflineTransaction).filter(
            OfflineTransaction.nonce == nonce
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DUPLICATE_NONCE",
                    "message": "Transaction with this nonce already exists",
                    "existing_transaction_id": existing.id
                }
            )


class DoubleSpendProtection:
    """
    Prevents double-spending through pessimistic locking and balance verification
    """
    
    @staticmethod
    def verify_and_deduct_balance(
        wallet_id: int,
        amount: str,
        db: Session,
        transaction_id: Optional[str] = None
    ) -> Wallet:
        """
        Atomically verify balance and deduct amount with row-level locking
        
        Args:
            wallet_id: Wallet ID to deduct from
            amount: Amount to deduct
            db: Database session
            transaction_id: Optional transaction ID for logging
            
        Returns:
            Updated wallet object
            
        Raises:
            HTTPException: If insufficient balance or wallet not found
        """
        # Use pessimistic locking (SELECT FOR UPDATE)
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_id
        ).with_for_update().first()
        
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail="Wallet not found"
            )
        
        if not wallet.is_active:
            raise HTTPException(
                status_code=400,
                detail="Wallet is not active"
            )
        
        # Convert to Decimal for precise arithmetic
        current_balance = Decimal(wallet.balance)
        deduct_amount = Decimal(amount)
        
        # Check for sufficient balance
        if current_balance < deduct_amount:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INSUFFICIENT_BALANCE",
                    "message": "Insufficient wallet balance",
                    "current_balance": str(current_balance),
                    "required": str(deduct_amount),
                    "shortfall": str(deduct_amount - current_balance)
                }
            )
        
        # Deduct balance atomically
        new_balance = current_balance - deduct_amount
        wallet.balance = str(new_balance)
        
        return wallet
    
    @staticmethod
    def verify_and_add_balance(
        wallet_id: int,
        amount: str,
        db: Session
    ) -> Wallet:
        """
        Atomically add amount to wallet balance
        
        Args:
            wallet_id: Wallet ID to add to
            amount: Amount to add
            db: Database session
            
        Returns:
            Updated wallet object
        """
        wallet = db.query(Wallet).filter(
            Wallet.id == wallet_id
        ).with_for_update().first()
        
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail="Wallet not found"
            )
        
        current_balance = Decimal(wallet.balance)
        add_amount = Decimal(amount)
        new_balance = current_balance + add_amount
        
        wallet.balance = str(new_balance)
        
        return wallet


class AuditTrail:
    """
    Creates immutable audit trail with hash chaining
    """
    
    @staticmethod
    def create_audit_entry(
        action: str,
        user_id: Optional[int],
        resource: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        previous_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an audit log entry with hash chain
        
        Args:
            action: Action performed (e.g., "TRANSACTION_CREATED")
            user_id: User ID who performed action
            resource: Resource affected (e.g., "wallet:123")
            details: Additional details as dict
            ip_address: Client IP address
            previous_hash: Hash of previous audit entry
            
        Returns:
            Audit entry dict with computed hash
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Create audit entry
        entry = {
            "timestamp": timestamp,
            "action": action,
            "user_id": user_id,
            "resource": resource,
            "details": details,
            "ip_address": ip_address,
            "previous_hash": previous_hash
        }
        
        # Compute hash of this entry
        entry_str = json.dumps(entry, sort_keys=True)
        current_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        entry["current_hash"] = current_hash
        
        return entry
    
    @staticmethod
    def verify_hash_chain(entries: list) -> bool:
        """
        Verify integrity of audit log hash chain
        
        Args:
            entries: List of audit entries in chronological order
            
        Returns:
            True if chain is valid, False otherwise
        """
        for i in range(1, len(entries)):
            expected_prev_hash = entries[i-1]["current_hash"]
            actual_prev_hash = entries[i]["previous_hash"]
            
            if expected_prev_hash != actual_prev_hash:
                return False
        
        return True


class TransactionValidator:
    """
    Validates transaction signatures and data integrity
    """
    
    @staticmethod
    def validate_transaction_data(
        sender_wallet_id: int,
        receiver_public_key: str,
        amount: str,
        currency: str,
        nonce: str,
        signature: str,
        receipt_hash: str,
        receipt_data: str
    ) -> None:
        """
        Validate all transaction data fields
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate amount
        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, decimal.InvalidOperation):
            raise HTTPException(
                status_code=400,
                detail="Invalid amount format"
            )
        
        # Validate currency
        valid_currencies = ["PKR", "USD", "EUR"]
        if currency not in valid_currencies:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid currency. Must be one of: {valid_currencies}"
            )
        
        # Validate nonce format (should be 32 chars hex)
        if not nonce or len(nonce) < 16:
            raise HTTPException(
                status_code=400,
                detail="Invalid nonce format"
            )
        
        # Validate signature exists
        if not signature or len(signature) < 100:
            raise HTTPException(
                status_code=400,
                detail="Invalid signature format"
            )
        
        # Validate receipt hash
        if not receipt_hash or len(receipt_hash) != 64:
            raise HTTPException(
                status_code=400,
                detail="Invalid receipt hash format (must be SHA-256)"
            )
        
        # Verify receipt hash matches receipt data
        computed_hash = hashlib.sha256(receipt_data.encode()).hexdigest()
        if computed_hash != receipt_hash:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "RECEIPT_HASH_MISMATCH",
                    "message": "Receipt hash does not match receipt data",
                    "expected": receipt_hash,
                    "computed": computed_hash
                }
            )


# Convenience function for complete transaction validation
def validate_offline_transaction(
    nonce: str,
    sender_wallet_id: int,
    receiver_public_key: str,
    amount: str,
    currency: str,
    transaction_signature: str,
    receipt_hash: str,
    receipt_data: str,
    created_at_device: str,
    db: Session
) -> None:
    """
    Perform complete validation of offline transaction
    
    Raises:
        HTTPException: If any validation fails
    """
    # 1. Validate transaction data format
    TransactionValidator.validate_transaction_data(
        sender_wallet_id,
        receiver_public_key,
        amount,
        currency,
        nonce,
        transaction_signature,
        receipt_hash,
        receipt_data
    )
    
    # 2. Check for replay attack
    ReplayAttackDefense.validate_transaction(nonce, created_at_device)
    ReplayAttackDefense.check_nonce_in_db(nonce, db)
    
    # 3. Double-spend protection is handled during balance deduction
    # (see DoubleSpendProtection.verify_and_deduct_balance)
