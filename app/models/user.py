# app/models/user.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    email = Column(String(256), unique=True, index=True, nullable=False)
    phone = Column(String(32), nullable=True)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    mfa_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Suspension (e.g. ledger integrity failure on sync); cleared only via DB/admin.
    account_blocked = Column(Boolean, default=False, nullable=False)
    fraud_review_pending = Column(Boolean, default=False, nullable=False)
    account_blocked_reason = Column(Text, nullable=True)
    account_blocked_at = Column(DateTime, nullable=True)

    # wallet/account fields (simple placeholders) - DEPRECATED: Use Wallet model instead
    offline_balance = Column(Integer, default=0, nullable=False)

    # relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
