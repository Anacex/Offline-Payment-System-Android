from pydantic import BaseModel, Field, condecimal
from typing import Optional, Literal
from datetime import datetime


class WalletBase(BaseModel):
    wallet_type: Literal["current", "offline"]
    currency: Literal["PKR", "USD", "AED", "SAR"] = "PKR"


class WalletCreate(WalletBase):
    """Schema for creating a new wallet."""
    pass


class WalletRead(WalletBase):
    """Schema for reading wallet data."""
    id: int
    user_id: int
    balance: condecimal(max_digits=12, decimal_places=2)
    public_key: Optional[str] = None  # Only for offline wallets
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WalletTransferCreate(BaseModel):
    """Schema for transferring money between wallets (preloading offline wallet)."""
    from_wallet_id: int
    to_wallet_id: int
    amount: condecimal(max_digits=12, decimal_places=2) = Field(..., gt=0)
    currency: Literal["PKR", "USD", "AED", "SAR"] = "PKR"


class WalletTransferRead(BaseModel):
    """Schema for reading wallet transfer data."""
    id: int
    user_id: int
    from_wallet_id: int
    to_wallet_id: int
    amount: condecimal(max_digits=12, decimal_places=2)
    currency: str
    status: Literal["completed", "failed", "pending"]
    reference: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


class QRCodeRequest(BaseModel):
    """Schema for requesting QR code generation."""
    wallet_id: int


class QRCodeResponse(BaseModel):
    """Schema for QR code response."""
    qr_data: dict
    qr_image_base64: str  # Base64 encoded PNG image


class OfflineTransactionCreate(BaseModel):
    """Schema for creating offline transaction (from mobile app)."""
    sender_wallet_id: int
    receiver_qr_data: dict  # QR code payload from receiver
    amount: condecimal(max_digits=12, decimal_places=2) = Field(..., gt=0)
    currency: Literal["PKR", "USD", "AED", "SAR"] = "PKR"
    device_fingerprint: Optional[str] = None
    created_at_device: datetime


class OfflineTransactionSign(BaseModel):
    """Schema for signing offline transaction (requires private key)."""
    transaction_data: dict
    sender_private_key: str  # In production, this should be handled securely


class OfflineTransactionRead(BaseModel):
    """Schema for reading offline transaction."""
    id: int
    sender_wallet_id: int
    receiver_public_key: str
    amount: condecimal(max_digits=12, decimal_places=2)
    currency: str
    transaction_signature: str
    nonce: str
    receipt_hash: str
    receipt_data: str
    status: Literal["pending", "synced", "confirmed", "failed"]
    created_at_device: datetime
    synced_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class OfflineTransactionSync(BaseModel):
    """Schema for syncing offline transactions from mobile to server."""
    transactions: list[dict]  # List of offline transaction data with signatures


class ReceiptVerification(BaseModel):
    """Schema for verifying transaction receipt."""
    receipt_data: dict
    signature: str
    sender_public_key: str
