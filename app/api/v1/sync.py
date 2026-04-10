from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.db import get_db
from app.models.transaction import Transaction

router = APIRouter(prefix="/sync")


class TransactionIn(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float
    token: str
    sequence_number: int


def reconcile_transactions(transactions: List[TransactionIn], db: Session):
    results = []
    for tx in transactions:
        existing = db.query(Transaction).filter(Transaction.reference == tx.token).first()
        if existing:
            results.append({"token": tx.token, "status": "failed", "reason": "double spend"})
        else:
            new_tx = Transaction(
                sender_id=tx.from_user_id,
                receiver_id=tx.to_user_id,
                amount=Decimal(str(tx.amount)),
                currency="PKR",
                reference=tx.token,
                status="settled",
            )
            db.add(new_tx)
            results.append({"token": tx.token, "status": "settled"})
    db.commit()
    return results


@router.post("/")
def sync_transactions(transactions: List[TransactionIn], db: Session = Depends(get_db)):
    return {"results": reconcile_transactions(transactions, db)}