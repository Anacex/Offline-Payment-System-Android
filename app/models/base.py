# Import Base from core.db to ensure single source of truth
from app.core.db import Base

__all__ = ["Base"]
