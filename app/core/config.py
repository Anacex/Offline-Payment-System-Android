from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://offlinepay_user:offlinepay123@localhost:5432/offlinepay"

    # Security
    SECRET_KEY: str = "09af8c7e3d4b2a1f6e5c8d9a0b3f4e2c1d8a9b0c3f4e5d6a7b8c9d0e1f2a3b4c"
    ALGORITHM: str = "HS256"

    OTP_PEPPER: str = Field(
        default="",
        description="Dedicated secret mixed into OTP hashes. If empty, falls back to SECRET_KEY-derived pepper.",
    )
    REDIS_URL: str = Field(
        default="",
        description="If set, OTP challenges are stored in Redis; otherwise PostgreSQL (otp_challenges).",
    )

    PLAY_INTEGRITY_SERVICE_ACCOUNT_JSON: str = Field(
        default="",
        description="Path to GCP service account JSON with Play Integrity API access.",
    )
    PLAY_INTEGRITY_PACKAGE_NAME: str = Field(
        default="com.offlinepayment",
        description="Android package name for decodeIntegrityToken.",
    )

    WALLET_AT_REST_FERNET_KEY: str = Field(
        default="",
        description="Fernet key (44-char url-safe base64) for sealing server-stored wallet PEM.",
    )
    AWS_KMS_CIPHERTEXT_BLOB_BASE64: str = Field(
        default="",
        description="Optional: standard Base64 KMS ciphertext for 32-byte Fernet key material.",
    )
    AWS_REGION: str = Field(default="us-east-1", description="AWS region for KMS decrypt.")

    # Token Expiration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Application
    APP_NAME: str = "Offline Payment System"
    DEBUG: bool = Field(
        default=True,
        description="If false: no otp_demo in API responses; OTP plaintext only in logs when true.",
    )

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 30

    # Database SSL toggle (true for managed DBs like Supabase; false for local)
    REQUIRE_SSL: bool = True

    # Pydantic Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Helper property to return parsed list for CORS
    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
