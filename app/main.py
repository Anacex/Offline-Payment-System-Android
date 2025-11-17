from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.user import router as user_router
from app.api.v1.transaction import router as tx_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.offline_transaction import router as offline_tx_router
from app.api.v1.sync import router as sync_router

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitHeaderMiddleware
)
from app.core.logging_config import app_logger

# Initialize FastAPI app
app = FastAPI(
    title="Offline Payment System API",
    version="1.0.0",
    description="Secure offline payment system with asymmetric cryptography",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)

@app.get("/")
def root():
    return {"service": "offline-payment-system", "version": "1.0.0"}

# Public
app.include_router(health_router)
app.include_router(auth_router)

# Protected
app.include_router(user_router)
app.include_router(tx_router)
app.include_router(wallet_router)
app.include_router(offline_tx_router)
app.include_router(sync_router)

from app.db_init import Base, engine
from sqlalchemy.orm import Session

@app.on_event("startup")
def startup_event():
    """Initialize application on startup."""
    app_logger.info("=" * 50)
    app_logger.info("Starting Offline Payment System API v1.0.0")
    app_logger.info("=" * 50)
    app_logger.info("Auto-creating DB tables if not exists...")
    Base.metadata.create_all(bind=engine)
    app_logger.info("Database tables ready")
    app_logger.info(f"Debug mode: {settings.DEBUG}")
    app_logger.info(f"Rate limiting: {'Enabled' if settings.RATE_LIMIT_ENABLED else 'Disabled'}")
    app_logger.info("Application startup complete")
    app_logger.info("=" * 50)

@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on application shutdown."""
    app_logger.info("Shutting down Offline Payment System API")
    app_logger.info("Goodbye!")
