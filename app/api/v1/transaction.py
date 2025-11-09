
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.db import get_db
from app.core.auth import get_current_user
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TxCreate, TxRead
from typing import List

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"], dependencies=[Depends(get_current_user)])

@router.get("/", response_model=List[TxRead])
def list_transactions(db: Session = Depends(get_db)):
    return db.query(Transaction).all()

@router.post("/", response_model=TxRead, status_code=201)
def create_transaction(payload: TxCreate, db: Session = Depends(get_db)):
    if not db.get(User, payload.sender_id) or not db.get(User, payload.receiver_id):
        raise HTTPException(status_code=400, detail="Invalid sender_id or receiver_id")

    exists = db.execute(select(Transaction).where(Transaction.reference == payload.reference)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Duplicate reference")

    tx = Transaction(**payload.model_dict())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
