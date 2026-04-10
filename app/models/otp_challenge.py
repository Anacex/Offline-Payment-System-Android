"""Persistent OTP challenges (used when Redis is not configured)."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, Index

from app.core.db import Base


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("ix_otp_challenges_purpose_subject_active", "purpose", "subject", "consumed"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nonce = Column(String(64), unique=True, nullable=False, index=True)
    purpose = Column(String(32), nullable=False, index=True)
    subject = Column(String(512), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    metadata_json = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    consumed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
