from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from app.models.base import Base
from datetime import datetime

class Transaction(Base):
    __tablename__  = "transactions"
    id= Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"))
    to_user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    token = Column(String, unique = True, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    status = Column(String, default="pending") #'pending' 'settled' 'failed'
    timestamp = Column(DateTime, default= datetime.utcnow)