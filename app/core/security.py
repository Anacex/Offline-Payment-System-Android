# app/core/security.py
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from pydantic_settings import BaseSettings

# === ENV / settings ===
class Settings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-to-secure-secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    EMAIL_OTP_EXPIRE_MINUTES: int = 10

settings = Settings()

# === password hashing ===
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # passlib bcrypt will manage salt
    return pwd_context.hash(password)

# === token helpers ===
def create_access_token(subject: str, device_fingerprint: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": str(subject), "exp": expire}
    if device_fingerprint:
        to_encode["df"] = device_fingerprint
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(subject: str, device_fingerprint: str, expires_delta: Optional[timedelta] = None) -> (str, datetime):
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode = {"sub": str(subject), "exp": expire, "df": device_fingerprint, "typ": "refresh"}
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expire

def decode_token(token: str):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
