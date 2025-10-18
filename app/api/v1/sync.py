from fastapi import APIRouter, Depends
from typing import List
from app.models.transaction import Transaction
from app.db import SessionLocal
from pydantic import BaseModel

router = APIRouter(prefix="/sync")

class TransactionIn(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float
    token: str
    sequence_number: int

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def reconcile_transactions(transactions: List[TransactionIn], db):
    results=[]
    for tx in transactions:
        existing = db.query(Transaction).filter_by(token=tx.token).first()
        if existing: # double spend or duplicate
            results.append({"token": tx.token, "status": "failed", "reason": "double spend"})
        else:
            new_tx = Transaction(**tx.dict(),status="settled")
            db.add(new_tx)
            results.append({"token": tx.token, "status": "settled"})
    #db.commit()
    return results

@router.post("/")
def sync_transactions(transactions: List[TransactionIn], db=Depends(get_db)):
    return {"results": reconcile_transactions(transactions, db)}