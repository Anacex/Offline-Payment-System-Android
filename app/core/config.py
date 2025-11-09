import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://offlinepay_user:offlinepay123@localhost:5432/offlinepay"

    # Security
    SECRET_KEY: str = "09af8c7e3d4b2a1f6e5c8d9a0b3f4e2c1d8a9b0c3f4e5d6a7b8c9d0e1f2a3b4c"
    ALGORITHM: str = "HS256"

    # Token Expiration
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Application
    APP_NAME: str = "Offline Payment System"
    DEBUG: bool = True  # Set False in production

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 30

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
