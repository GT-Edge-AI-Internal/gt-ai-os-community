"""
Composite ASGI Router for GT 2.0 Tenant Backend

Handles routing between FastAPI and Socket.IO applications to prevent
ASGI protocol conflicts while maintaining both WebSocket systems.

Architecture:
- `/socket.io/*` → Socket.IO ASGIApp (agentic real-time features)
- All other paths → FastAPI app (REST API, native WebSocket)
"""

import logging
from typing import Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class CompositeASGIRouter:
    """
    ASGI router that handles both FastAPI and Socket.IO applications
    without protocol conflicts.
    """

    def __init__(self, fastapi_app, socketio_app):
        """
        Initialize composite router with both applications.

        Args:
            fastapi_app: FastAPI application instance
            socketio_app: Socket.IO ASGIApp instance
        """
        self.fastapi_app = fastapi_app
        self.socketio_app = socketio_app
        logger.info("Composite ASGI router initialized for FastAPI + Socket.IO")

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """
        ASGI application entry point that routes requests based on path.

        Args:
            scope: ASGI scope containing request information
            receive: ASGI receive callable
            send: ASGI send callable
        """
        try:
            # Extract path from scope
            path = scope.get("path", "")

            # Route based on path pattern
            if self._is_socketio_path(path):
                # Only log Socket.IO routing at DEBUG level for non-operational paths
                if self._should_log_route(path):
                    logger.debug(f"Routing to Socket.IO: {path}")
                await self.socketio_app(scope, receive, send)
            else:
                # Only log FastAPI routing at DEBUG level for non-operational paths
                if self._should_log_route(path):
                    logger.debug(f"Routing to FastAPI: {path}")
                await self.fastapi_app(scope, receive, send)

        except Exception as e:
            logger.error(f"Error in ASGI routing: {e}")
            # Fallback to FastAPI for error handling
            try:
                await self.fastapi_app(scope, receive, send)
            except Exception as fallback_error:
                logger.error(f"Fallback routing also failed: {fallback_error}")
                # Last resort: send basic error response
                await self._send_error_response(scope, send)

    def _is_socketio_path(self, path: str) -> bool:
        """
        Determine if path should be routed to Socket.IO.

        Args:
            path: Request path

        Returns:
            True if path should go to Socket.IO, False for FastAPI
        """
        socketio_patterns = [
            "/socket.io/",
            "/socket.io"
        ]

        # Check if path starts with any Socket.IO pattern
        for pattern in socketio_patterns:
            if path.startswith(pattern):
                return True

        return False

    def _should_log_route(self, path: str) -> bool:
        """
        Determine if this path should be logged during routing.

        Operational endpoints like health checks and metrics are excluded
        to reduce log noise during normal operation.

        Args:
            path: Request path

        Returns:
            True if path should be logged, False for operational endpoints
        """
        operational_endpoints = [
            "/health",
            "/ready",
            "/metrics",
            "/api/v1/health"
        ]

        # Don't log operational endpoints
        if any(path.startswith(endpoint) for endpoint in operational_endpoints):
            return False

        return True

    async def _send_error_response(self, scope: Dict[str, Any], send: Callable) -> None:
        """
        Send basic error response when both applications fail.

        Args:
            scope: ASGI scope
            send: ASGI send callable
        """
        try:
            if scope["type"] == "http":
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", b"27"]
                    ]
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "ASGI routing failed"}'
                })
            elif scope["type"] == "websocket":
                await send({
                    "type": "websocket.close",
                    "code": 1011,
                    "reason": "ASGI routing failed"
                })
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")


def create_composite_asgi_app(fastapi_app, socketio_app):
    """
    Factory function to create composite ASGI application.

    Args:
        fastapi_app: FastAPI application instance
        socketio_app: Socket.IO ASGIApp instance

    Returns:
        CompositeASGIRouter instance
    """
    return CompositeASGIRouter(fastapi_app, socketio_app)