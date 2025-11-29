# middleware_logging.py
from fastapi import Request
from starlette.responses import Response
from log_to_supabase import log_event
import time
import traceback

async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    try:
        log_event("info", "Request received", {
            "method": request.method,
            "path": str(request.url.path),
            "client": request.client.host if request.client else None,
        })

        response: Response = await call_next(request)

        duration_ms = int((time.time() - start) * 1000)
        
        # Log response - use error level for 4xx/5xx status codes
        log_level = "error" if response.status_code >= 400 else "info"
        log_event(log_level, "Response sent", {
            "status": response.status_code,
            "path": str(request.url.path),
            "method": request.method,
            "duration_ms": duration_ms
        })
        return response

    except Exception as exc:
        tb = traceback.format_exc()
        log_event("error", "Unhandled exception", {
            "path": str(request.url.path),
            "method": request.method,
            "error": str(exc),
            "traceback": tb
        })
        raise

