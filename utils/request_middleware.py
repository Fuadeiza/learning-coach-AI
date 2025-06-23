import time
import asyncio
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import log_request_start, log_request_end, log_error, log_periodic_stats


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests with timing and cache statistics"""
    
    def __init__(self, app, log_periodic_stats_interval: int = 300):  # 5 minutes
        super().__init__(app)
        self.log_periodic_stats_interval = log_periodic_stats_interval
        self.last_stats_log = time.time()
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health checks and static files
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Extract user info if available
        user_id = None
        try:
            # Try to get user from auth header (simplified)
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # In a real implementation, you'd decode the JWT here
                user_id = "authenticated_user"  # Placeholder
        except Exception:
            pass
        
        # Log request start
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        request_info = log_request_start(request, endpoint, user_id)
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log request end
            log_request_end(request_info, duration_ms, response.status_code)
            
            # Log periodic stats if interval has passed
            current_time = time.time()
            if current_time - self.last_stats_log > self.log_periodic_stats_interval:
                log_periodic_stats()
                self.last_stats_log = current_time
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration_ms = (time.time() - start_time) * 1000
            
            # Log the error
            log_error(e, endpoint, user_id, {
                "duration_ms": duration_ms,
                "request_path": str(request.url.path),
                "request_method": request.method
            })
            
            # Log request end with error status
            log_request_end(request_info, duration_ms, 500)
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": str(e)}
            )


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to track performance metrics"""
    
    def __init__(self, app, slow_request_threshold_ms: float = 1000):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Log slow requests
        if duration_ms > self.slow_request_threshold_ms:
            from utils.logging import cache_logger
            cache_logger.logger.warning(
                f"🐌 SLOW REQUEST | {request.method} {request.url.path} | "
                f"Duration: {duration_ms:.2f}ms | Threshold: {self.slow_request_threshold_ms}ms"
            )
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response 