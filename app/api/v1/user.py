from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.db import SessionLocal
from pydantic import BaseModel

router =APIRouter(prefix="/users")

class UserIn(BaseModel):
    name:str
    email:str
    role: str= "payer"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def create_user(user_in: UserIn, db=Depends(get_db)):
    new_user = User(**user_in.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/")
def get_users(db=Depends(get_db)):
    return db.query(User).all()