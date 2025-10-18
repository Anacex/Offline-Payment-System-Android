from fastapi import APIRouter, Depends
from app.models.transaction import Transaction
from app.db import SessionLocal
from pydantic import BaseModel

router =APIRouter(prefix="/transactions")

class TransactionIn(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float
    token: str
    sequence_number: int

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
@router.post("/")
def create_transaction(tx_in: TransactionIn, db=Depends(get_db)):
    new_tx = Transaction(**tx_in.dict(), status="pending")
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx

@router.get("/")
def get_transactions(db=Depends(get_db)):
    return db.query(Transaction).all()
