"""
WebSocket module for GT 2.0 real-time chat functionality.

Provides secure, tenant-isolated WebSocket connections for:
- Real-time chat messaging
- Typing indicators
- Connection management
- Event broadcasting
"""

from .manager import (
    WebSocketManager,
    WebSocketConnection,
    ChatMessage,
    websocket_manager,
    get_websocket_manager,
    authenticate_websocket_connection
)

__all__ = [
    "WebSocketManager",
    "WebSocketConnection", 
    "ChatMessage",
    "websocket_manager",
    "get_websocket_manager",
    "authenticate_websocket_connection"
]