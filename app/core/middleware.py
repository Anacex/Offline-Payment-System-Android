"""
Custom middleware for security and monitoring.
"""
from app.core.config import settings
import time
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.logging_config import app_logger, security_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request
        app_logger.info(
            f"Request: {request.method} {request.url.path} - IP: {client_ip}"
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        app_logger.info(
            f"Response: {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Duration: {duration:.3f}s"
        )
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Common security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # ✅ Development mode: allow Swagger UI & FastAPI docs assets
        if settings.DEBUG:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        else:
            # ✅ Strict CSP for production
            response.headers["Content-Security-Policy"] = "default-src 'self';"

        return response


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit information to headers."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add rate limit headers (if rate limiting is enabled)
        response.headers["X-RateLimit-Limit"] = "30"
        response.headers["X-RateLimit-Remaining"] = "25"  # This should be dynamic
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Middleware to restrict access to specific IPs (optional for production).
    Disabled by default - enable for admin endpoints only.
    """
    
    def __init__(self, app: ASGIApp, whitelist: list[str] = None):
        super().__init__(app)
        self.whitelist = whitelist or []
    
    async def dispatch(self, request: Request, call_next):
        # Skip if whitelist is empty
        if not self.whitelist:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        
        # Check if IP is whitelisted
        if client_ip not in self.whitelist:
            security_logger.log_suspicious_activity(
                "IP not whitelisted",
                f"Attempted access from {client_ip}",
                client_ip
            )
            return Response(
                content=json.dumps({"detail": "Access denied"}),
                status_code=403,
                media_type="application/json"
            )
        
        return await call_next(request)
