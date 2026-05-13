import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        request_id = request.headers.get("X-Request-ID", "")
        
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
        )
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=process_time,
            request_id=request_id,
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
