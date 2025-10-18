import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/offlinepay")

settings = Settings()