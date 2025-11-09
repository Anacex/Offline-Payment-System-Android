
from pydantic import BaseModel, EmailStr, Field
from typing import Literal

class SignupRequest(BaseModel):
    name: str = Field(..., max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: str | None = None
    role: Literal["payer", "payee"] = "payer"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
