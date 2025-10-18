from sqlalchemy import Column, Integer, String, Float
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    id=Column(Integer, primary_key=True, index=True)
    name=Column(String, nullable=False)
    email=Column(String, unique=True, index=True, nullable=False)
    balance=Column(Float, default=0.0)
    role = Column(String, default="payer") #'payer' or 'payee' or 'admin'