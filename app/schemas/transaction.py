
from pydantic import BaseModel, Field, condecimal
from typing import Literal
from datetime import datetime

class TxBase(BaseModel):
    sender_id: int
    receiver_id: int
    amount: condecimal(max_digits=12, decimal_places=2) = Field(..., gt=0)
    currency: Literal["PKR", "USD", "AED", "SAR"] = "PKR"
    reference: str = Field(..., min_length=6, max_length=64)

class TxCreate(TxBase):
    pass

class TxRead(TxBase):
    id: int
    status: Literal["pending", "confirmed", "reconciled", "failed"]
    timestamp: datetime

    class Config:
        from_attributes = True
