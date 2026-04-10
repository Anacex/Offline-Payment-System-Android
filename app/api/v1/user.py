# app/api/v1/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.deps import admin_required
from app.models import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/", dependencies=[Depends(admin_required)])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "offline_balance": u.offline_balance} for u in users]

@router.post("/", dependencies=[Depends(admin_required)], status_code=201)
def create_user(payload: dict, db: Session = Depends(get_db)):
    # Admin created user / merchant / business etc.
    u = User(
        name=payload.get("name"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        password_hash=security.get_password_hash(payload.get("password") or secrets.token_urlsafe(10)),
        is_email_verified=True  # admin-created
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "email": u.email}
