"""Request ID middleware — injects a unique request_id into each request for traceability."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import uuid


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
