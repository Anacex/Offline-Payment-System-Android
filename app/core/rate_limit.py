"""
Rate limiting middleware for API protection.
Prevents abuse and DDoS attacks.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from app.core.config import settings

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"] if settings.RATE_LIMIT_ENABLED else []
)

def get_rate_limiter():
    """Get rate limiter instance."""
    return limiter

# Rate limit decorators for different endpoint types
def rate_limit_auth():
    """Rate limit for authentication endpoints (stricter)."""
    return limiter.limit("5/minute")

def rate_limit_api():
    """Rate limit for general API endpoints."""
    return limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")

def rate_limit_transaction():
    """Rate limit for transaction endpoints (moderate)."""
    return limiter.limit("10/minute")
