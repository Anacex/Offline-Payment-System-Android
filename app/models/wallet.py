from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .base import Base

class Wallet(Base):
    """
    Represents both current (online) and offline wallets for users.
    Each user can have multiple wallets but typically one of each type.
    """
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    wallet_type = Column(String(20), nullable=False)  # 'current' or 'offline'
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="PKR")
    
    # Cryptographic keys for offline wallet (stored encrypted in production)
    public_key = Column(Text, nullable=True)  # RSA public key (PEM format)
    private_key_encrypted = Column(Text, nullable=True)  # Encrypted RSA private key
    
    # Bank account information (for demo purposes)
    bank_account_number = Column(String(64), nullable=False)  # User's bank account number (required)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="wallets")
    
    def __repr__(self):
        return f"<Wallet(id={self.id}, user_id={self.user_id}, type={self.wallet_type}, balance={self.balance})>"


class OfflineTransaction(Base):
    """
    Stores offline transactions that are created locally and synced to server.
    These transactions are pending until the sender comes online.
    """
    __tablename__ = "offline_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Transaction details
    sender_wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False, index=True)
    receiver_public_key = Column(Text, nullable=False)  # Receiver's public key from QR code
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="PKR")
    
    # Cryptographic proof
    transaction_signature = Column(Text, nullable=False)  # Digital signature of transaction
    nonce = Column(String(64), unique=True, nullable=False, index=True)  # Prevents replay attacks
    
    # Receipt data
    receipt_hash = Column(String(128), nullable=False)  # SHA-256 hash of receipt
    receipt_data = Column(Text, nullable=False)  # JSON receipt data
    
    # Status tracking
    status = Column(String(20), nullable=False, default="pending")  # pending, synced, confirmed, failed
    created_at_device = Column(DateTime, nullable=False)  # When created on device
    synced_at = Column(DateTime, nullable=True)  # When synced to server
    confirmed_at = Column(DateTime, nullable=True)  # When confirmed on blockchain/ledger
    
    # Metadata
    device_fingerprint = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sender_wallet = relationship("Wallet", foreign_keys=[sender_wallet_id])
    
    def __repr__(self):
        return f"<OfflineTransaction(id={self.id}, amount={self.amount}, status={self.status})>"


class WalletTransfer(Base):
    """
    Tracks transfers between current and offline wallets (preloading).
    """
    __tablename__ = "wallet_transfers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    from_wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False)
    to_wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="PKR")
    status = Column(String(20), nullable=False, default="completed")  # completed, failed, pending
    reference = Column(String(64), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    from_wallet = relationship("Wallet", foreign_keys=[from_wallet_id])
    to_wallet = relationship("Wallet", foreign_keys=[to_wallet_id])
    
    def __repr__(self):
        return f"<WalletTransfer(id={self.id}, amount={self.amount}, status={self.status})>"
