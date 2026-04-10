
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from .base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="PKR")
    status = Column(String(20), nullable=False, default="pending")
    reference = Column(String(64), unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

    __table_args__ = (Index("ix_transactions_sender_receiver_time", "sender_id", "receiver_id", "timestamp"),)
