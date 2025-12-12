"""
WebSocket Connection Manager for GT 2.0 Tenant Backend

Handles real-time chat connections with:
- Perfect tenant isolation
- Zero downtime compliance
- Secure authentication
- Event-driven message broadcasting
- Resource cleanup on disconnect

GT 2.0 Security Principles:
- All connections are user and tenant scoped
- No cross-tenant message leaking
- Automatic cleanup on disconnect
- Rate limiting and connection limits
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import verify_jwt_token
from app.services.conversation_service import ConversationService
from app.services.event_service import EventService, EventType

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """WebSocket connection metadata"""
    websocket: WebSocket
    user_id: str
    tenant_id: str
    conversation_id: Optional[str]
    connected_at: datetime
    last_activity: datetime
    connection_id: str
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }


@dataclass
class ChatMessage:
    """Chat message structure"""
    message_id: str
    conversation_id: str
    user_id: str
    tenant_id: str
    role: str  # 'user', 'agent', 'system'
    content: str
    timestamp: datetime
    message_type: str = "chat"  # 'chat', 'typing', 'status'
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type,
            "metadata": self.metadata or {}
        }


class WebSocketManager:
    """
    WebSocket connection manager with perfect tenant isolation.
    
    GT 2.0 Architecture Principles:
    - Zero downtime: Graceful connection management
    - Perfect tenant isolation: No cross-tenant message leaking
    - Self-contained: No external dependencies
    - Stateless: Connection state only in memory
    """
    
    def __init__(self):
        # Connection storage with tenant isolation
        self.connections: Dict[str, WebSocketConnection] = {}
        self.tenant_connections: Dict[str, Set[str]] = {}  # tenant_id -> connection_ids
        self.conversation_connections: Dict[str, Set[str]] = {}  # conversation_id -> connection_ids
        
        # Rate limiting and connection limits
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.max_connections_per_user = 5
        self.max_connections_per_tenant = 100
        self.message_rate_limit = 60  # messages per minute
        self.user_message_counts: Dict[str, List[float]] = {}  # user_id -> timestamps
        
        # Background cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        # Note: cleanup task will be started when first connection is made
        
        logger.info("WebSocket Manager initialized with tenant isolation")
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
    
    async def _cleanup_stale_connections(self):
        """Background task to cleanup stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._remove_stale_connections()
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def _remove_stale_connections(self):
        """Remove connections that haven't been active for 30 minutes"""
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        stale_connections = []
        
        for connection_id, connection in self.connections.items():
            if connection.last_activity < stale_cutoff:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            await self._remove_connection(connection_id)
            logger.info(f"Removed stale connection: {connection_id}")
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket instance
            user_id: Authenticated user ID
            tenant_id: Tenant ID for isolation
            conversation_id: Optional conversation to join
            
        Returns:
            Connection ID
            
        Raises:
            ConnectionError: If connection limits exceeded
        """
        try:
            # Check connection limits
            await self._check_connection_limits(user_id, tenant_id)
            
            # Accept WebSocket connection
            await websocket.accept()
            
            # Create connection record
            connection_id = str(uuid.uuid4())
            connection = WebSocketConnection(
                websocket=websocket,
                user_id=user_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                connected_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                connection_id=connection_id
            )
            
            # Store connection with tenant isolation
            self.connections[connection_id] = connection
            
            # Index by tenant
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(connection_id)
            
            # Index by user
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            # Index by conversation if specified
            if conversation_id:
                if conversation_id not in self.conversation_connections:
                    self.conversation_connections[conversation_id] = set()
                self.conversation_connections[conversation_id].add(connection_id)

            # Start cleanup task if this is the first connection
            if len(self.connections) == 1:
                self._start_cleanup_task()
            
            logger.info(f"WebSocket connected: {connection.to_dict()}")
            
            # Send connection confirmation
            await self.send_to_connection(connection_id, {
                "type": "connection_established",
                "connection_id": connection_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return connection_id
            
        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {e}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except:
                pass
            raise
    
    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = "Normal closure"):
        """
        Gracefully disconnect a WebSocket connection.
        
        Args:
            connection_id: Connection to disconnect
            code: WebSocket close code
            reason: Disconnect reason
        """
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return
            
            logger.info(f"Disconnecting WebSocket: {connection_id} - {reason}")
            
            # Send disconnect notification to conversation participants
            if connection.conversation_id:
                await self.broadcast_to_conversation(
                    connection.conversation_id,
                    {
                        "type": "user_disconnected",
                        "user_id": connection.user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    exclude_connection=connection_id
                )
            
            # Close WebSocket
            try:
                await connection.websocket.close(code=code, reason=reason)
            except:
                pass  # Connection may already be closed
            
            # Remove from indexes
            await self._remove_connection(connection_id)
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket {connection_id}: {e}")
    
    async def _remove_connection(self, connection_id: str):
        """Remove connection from all indexes"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        # Remove from main storage
        del self.connections[connection_id]
        
        # Remove from tenant index
        tenant_connections = self.tenant_connections.get(connection.tenant_id, set())
        tenant_connections.discard(connection_id)
        if not tenant_connections:
            del self.tenant_connections[connection.tenant_id]
        
        # Remove from user index
        user_connections = self.user_connections.get(connection.user_id, set())
        user_connections.discard(connection_id)
        if not user_connections:
            del self.user_connections[connection.user_id]
        
        # Remove from conversation index
        if connection.conversation_id:
            conv_connections = self.conversation_connections.get(connection.conversation_id, set())
            conv_connections.discard(connection_id)
            if not conv_connections:
                del self.conversation_connections[connection.conversation_id]
    
    async def _check_connection_limits(self, user_id: str, tenant_id: str):
        """Check if connection limits would be exceeded"""
        # Check user connection limit
        user_connection_count = len(self.user_connections.get(user_id, set()))
        if user_connection_count >= self.max_connections_per_user:
            raise ConnectionError(f"User connection limit exceeded: {self.max_connections_per_user}")
        
        # Check tenant connection limit
        tenant_connection_count = len(self.tenant_connections.get(tenant_id, set()))
        if tenant_connection_count >= self.max_connections_per_tenant:
            raise ConnectionError(f"Tenant connection limit exceeded: {self.max_connections_per_tenant}")
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to specific connection.
        
        Args:
            connection_id: Target connection
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return False
            
            # Update activity timestamp
            connection.update_activity()
            
            # Send message
            await connection.websocket.send_text(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to connection {connection_id}: {e}")
            # Remove broken connection
            await self._remove_connection(connection_id)
            return False
    
    async def send_to_user(
        self,
        user_id: str,
        tenant_id: str,
        message: Dict[str, Any],
        exclude_connection: Optional[str] = None
    ):
        """
        Send message to all connections for a specific user within tenant.
        
        Args:
            user_id: Target user
            tenant_id: Tenant for isolation
            message: Message to send
            exclude_connection: Connection to exclude from broadcast
        """
        user_connections = self.user_connections.get(user_id, set())
        
        for connection_id in user_connections.copy():
            if connection_id == exclude_connection:
                continue
                
            connection = self.connections.get(connection_id)
            if not connection or connection.tenant_id != tenant_id:
                continue
            
            success = await self.send_to_connection(connection_id, message)
            if not success:
                user_connections.discard(connection_id)
    
    async def broadcast_to_conversation(
        self,
        conversation_id: str,
        message: Dict[str, Any],
        exclude_connection: Optional[str] = None
    ):
        """
        Broadcast message to all participants in a conversation.
        
        Args:
            conversation_id: Target conversation
            message: Message to broadcast
            exclude_connection: Connection to exclude from broadcast
        """
        conv_connections = self.conversation_connections.get(conversation_id, set())
        
        for connection_id in conv_connections.copy():
            if connection_id == exclude_connection:
                continue
            
            success = await self.send_to_connection(connection_id, message)
            if not success:
                conv_connections.discard(connection_id)
    
    async def broadcast_to_tenant(
        self,
        tenant_id: str,
        message: Dict[str, Any],
        exclude_connection: Optional[str] = None
    ):
        """
        Broadcast message to all connections in a tenant.

        Args:
            tenant_id: Target tenant
            message: Message to broadcast
            exclude_connection: Connection to exclude from broadcast
        """
        tenant_connections = self.tenant_connections.get(tenant_id, set())

        for connection_id in tenant_connections.copy():
            if connection_id == exclude_connection:
                continue

            success = await self.send_to_connection(connection_id, message)
            if not success:
                tenant_connections.discard(connection_id)

    # Agentic Phase Event Methods
    async def emit_phase_start(
        self,
        conversation_id: str,
        phase: str,
        metadata: Dict[str, Any] = None
    ):
        """Emit phase start event to conversation participants"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "phase_start",
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": metadata or {}
        })

    async def emit_phase_transition(
        self,
        conversation_id: str,
        from_phase: str,
        to_phase: str,
        metadata: Dict[str, Any] = None
    ):
        """Emit phase transition event"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "phase_transition",
            "phase": to_phase,
            "from_phase": from_phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": metadata or {}
        })

    async def emit_tool_execution(
        self,
        conversation_id: str,
        tool_execution: Dict[str, Any]
    ):
        """Emit tool execution event"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "tool_execution",
            "toolExecution": tool_execution,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def emit_subagent_status(
        self,
        conversation_id: str,
        subagent_status: Dict[str, Any]
    ):
        """Emit subagent status event"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "subagent_status",
            "subagentStatus": subagent_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def emit_source_retrieval(
        self,
        conversation_id: str,
        source_retrieval: Dict[str, Any]
    ):
        """Emit source retrieval event"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "source_retrieval",
            "sourceRetrieval": source_retrieval,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def emit_phase_complete(
        self,
        conversation_id: str,
        phase: str,
        duration_ms: float = None,
        metadata: Dict[str, Any] = None
    ):
        """Emit phase completion event"""
        await self.broadcast_to_conversation(conversation_id, {
            "type": "phase_complete",
            "phase": phase,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": metadata or {}
        })
    
    async def handle_message(
        self,
        connection_id: str,
        message_data: Dict[str, Any]
    ) -> bool:
        """
        Handle incoming WebSocket message with rate limiting.
        
        Args:
            connection_id: Source connection
            message_data: Parsed message data
            
        Returns:
            True if handled successfully, False otherwise
        """
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return False
            
            # Check rate limiting
            if not await self._check_rate_limit(connection.user_id):
                await self.send_to_connection(connection_id, {
                    "type": "error",
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED"
                })
                return False
            
            # Update activity
            connection.update_activity()
            
            # Route message based on type
            message_type = message_data.get("type", "unknown")
            
            if message_type == "chat_message":
                return await self._handle_chat_message(connection, message_data)
            elif message_type == "typing_indicator":
                return await self._handle_typing_indicator(connection, message_data)
            elif message_type == "join_conversation":
                return await self._handle_join_conversation(connection, message_data)
            elif message_type == "leave_conversation":
                return await self._handle_leave_conversation(connection, message_data)
            elif message_type == "ping":
                return await self._handle_ping(connection, message_data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            return False
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        now = time.time()
        minute_ago = now - 60
        
        # Get user's message timestamps
        if user_id not in self.user_message_counts:
            self.user_message_counts[user_id] = []
        
        user_messages = self.user_message_counts[user_id]
        
        # Remove old timestamps
        user_messages[:] = [ts for ts in user_messages if ts > minute_ago]
        
        # Check limit
        if len(user_messages) >= self.message_rate_limit:
            return False
        
        # Add current timestamp
        user_messages.append(now)
        return True
    
    async def _handle_chat_message(
        self,
        connection: WebSocketConnection,
        message_data: Dict[str, Any]
    ) -> bool:
        """Handle chat message with AI response streaming"""
        try:
            if not connection.conversation_id:
                return False
            
            content = message_data.get("content", "").strip()
            if not content:
                return False
            
            # Create chat message
            chat_message = ChatMessage(
                message_id=str(uuid.uuid4()),
                conversation_id=connection.conversation_id,
                user_id=connection.user_id,
                tenant_id=connection.tenant_id,
                role="user",
                content=content,
                timestamp=datetime.now(timezone.utc),
                message_type="chat",
                metadata=message_data.get("metadata", {})
            )
            
            # Broadcast user message to conversation participants
            await self.broadcast_to_conversation(
                connection.conversation_id,
                {
                    "type": "new_message",
                    "message": chat_message.to_dict()
                }
            )
            
            # Check if this should trigger AI response
            trigger_ai = message_data.get("trigger_ai", True)
            if trigger_ai:
                # Start AI response streaming in background
                asyncio.create_task(self._handle_ai_response_streaming(
                    connection=connection,
                    user_message=content
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            return False
    
    async def _handle_ai_response_streaming(
        self,
        connection: WebSocketConnection,
        user_message: str
    ) -> None:
        """Handle AI response streaming"""
        try:
            # Import here to avoid circular imports
            from app.services.websocket_service import WebSocketService
            
            async with get_db_session() as db:
                websocket_service = WebSocketService(db)
                
                await websocket_service.stream_ai_response(
                    conversation_id=connection.conversation_id,
                    user_message=user_message,
                    user_id=connection.user_id,
                    tenant_id=connection.tenant_id,
                    connection_id=connection.connection_id
                )
                
        except Exception as e:
            logger.error(f"Error in AI response streaming: {e}")
            
            # Send error message to user
            await self.send_to_connection(connection.connection_id, {
                "type": "ai_response_error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def _handle_typing_indicator(
        self,
        connection: WebSocketConnection,
        message_data: Dict[str, Any]
    ) -> bool:
        """Handle typing indicator"""
        try:
            if not connection.conversation_id:
                return False
            
            is_typing = message_data.get("is_typing", False)
            
            # Broadcast typing indicator to other participants
            await self.broadcast_to_conversation(
                connection.conversation_id,
                {
                    "type": "typing_indicator",
                    "user_id": connection.user_id,
                    "is_typing": is_typing,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                exclude_connection=connection.connection_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling typing indicator: {e}")
            return False
    
    async def _handle_join_conversation(
        self,
        connection: WebSocketConnection,
        message_data: Dict[str, Any]
    ) -> bool:
        """Handle joining a conversation"""
        try:
            conversation_id = message_data.get("conversation_id")
            if not conversation_id:
                return False
            
            # Remove from current conversation if any
            if connection.conversation_id:
                await self._handle_leave_conversation(connection, {})
            
            # Join new conversation
            connection.conversation_id = conversation_id
            
            # Add to conversation index
            if conversation_id not in self.conversation_connections:
                self.conversation_connections[conversation_id] = set()
            self.conversation_connections[conversation_id].add(connection.connection_id)
            
            # Notify other participants
            await self.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "user_joined",
                    "user_id": connection.user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                exclude_connection=connection.connection_id
            )
            
            # Confirm join to user
            await self.send_to_connection(connection.connection_id, {
                "type": "conversation_joined",
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error joining conversation: {e}")
            return False
    
    async def _handle_leave_conversation(
        self,
        connection: WebSocketConnection,
        message_data: Dict[str, Any]
    ) -> bool:
        """Handle leaving a conversation"""
        try:
            if not connection.conversation_id:
                return False
            
            conversation_id = connection.conversation_id
            
            # Remove from conversation index
            conv_connections = self.conversation_connections.get(conversation_id, set())
            conv_connections.discard(connection.connection_id)
            if not conv_connections:
                del self.conversation_connections[conversation_id]
            
            # Notify other participants
            await self.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "user_left",
                    "user_id": connection.user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Clear conversation from connection
            connection.conversation_id = None
            
            return True
            
        except Exception as e:
            logger.error(f"Error leaving conversation: {e}")
            return False
    
    async def _handle_ping(
        self,
        connection: WebSocketConnection,
        message_data: Dict[str, Any]
    ) -> bool:
        """Handle ping message"""
        try:
            await self.send_to_connection(connection.connection_id, {
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return True
            
        except Exception as e:
            logger.error(f"Error handling ping: {e}")
            return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_connections": len(self.connections),
            "connections_by_tenant": {
                tenant_id: len(connections) 
                for tenant_id, connections in self.tenant_connections.items()
            },
            "active_conversations": len(self.conversation_connections),
            "connections_by_user": {
                user_id: len(connections)
                for user_id, connections in self.user_connections.items()
            }
        }


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


# Agentic helper functions for easy access
async def emit_agentic_phase(conversation_id: str, phase: str, metadata: Dict[str, Any] = None):
    """Helper function to emit agentic phase events"""
    await websocket_manager.emit_phase_start(conversation_id, phase, metadata)


async def emit_tool_update(conversation_id: str, tool_id: str, name: str, status: str, **kwargs):
    """Helper function to emit tool execution updates"""
    tool_execution = {
        "id": tool_id,
        "name": name,
        "status": status,
        "startTime": kwargs.get("start_time"),
        "endTime": kwargs.get("end_time"),
        "progress": kwargs.get("progress"),
        "arguments": kwargs.get("arguments"),
        "result": kwargs.get("result"),
        "error": kwargs.get("error")
    }
    # Filter out None values
    tool_execution = {k: v for k, v in tool_execution.items() if v is not None}
    await websocket_manager.emit_tool_execution(conversation_id, tool_execution)


async def emit_subagent_update(conversation_id: str, subagent_id: str, type_name: str, task: str, status: str, **kwargs):
    """Helper function to emit subagent status updates"""
    subagent_status = {
        "id": subagent_id,
        "type": type_name,
        "task": task,
        "status": status,
        "startTime": kwargs.get("start_time"),
        "endTime": kwargs.get("end_time"),
        "progress": kwargs.get("progress"),
        "dependsOn": kwargs.get("depends_on"),
        "result": kwargs.get("result"),
        "error": kwargs.get("error")
    }
    # Filter out None values
    subagent_status = {k: v for k, v in subagent_status.items() if v is not None}
    await websocket_manager.emit_subagent_status(conversation_id, subagent_status)


async def emit_source_update(conversation_id: str, source_id: str, source_type: str, query: str, status: str, **kwargs):
    """Helper function to emit source retrieval updates"""
    source_retrieval = {
        "id": source_id,
        "type": source_type,
        "query": query,
        "status": status,
        "results": kwargs.get("results")
    }
    # Filter out None values
    source_retrieval = {k: v for k, v in source_retrieval.items() if v is not None}
    await websocket_manager.emit_source_retrieval(conversation_id, source_retrieval)


# Utility functions for dependency injection
def get_websocket_manager() -> WebSocketManager:
    """Get WebSocket manager instance"""
    return websocket_manager


def authenticate_websocket_connection(token: str) -> tuple[str, str]:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        token: JWT token

    Returns:
        Tuple of (user_id, tenant_id)

    Raises:
        ValueError: If authentication fails
    """
    try:
        payload = verify_jwt_token(token)  # This is synchronous, not async

        if not payload:
            raise ValueError("Token verification failed")

        user_id = payload.get("sub")

        # Get tenant_id from current_tenant or fall back to tenant_id in root
        current_tenant = payload.get("current_tenant", {})
        tenant_id = current_tenant.get("id") or current_tenant.get("domain") or payload.get("tenant_id")

        if not user_id or not tenant_id:
            raise ValueError(f"Invalid token payload: user_id={user_id}, tenant_id={tenant_id}")

        return user_id, tenant_id

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        raise ValueError("Authentication failed")


# Socket.IO Integration for GT 2.0 Agentic Frontend
import socketio
from typing import Dict, Any

# Create Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",  # Allow all origins for development
    logger=True,
    engineio_logger=True
)

# Create ASGI app for Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=None)


@sio.event
async def connect(sid, environ, auth):
    """Handle Socket.IO client connection"""
    logger.info(f"🔌 Socket.IO connection attempt - sid: {sid}")
    logger.info(f"🔌 Auth object: {auth}")

    try:
        # Extract authentication from query parameters or auth object
        query_string = environ.get('QUERY_STRING', '')
        token = None
        conversation_id = None

        logger.info(f"🔌 Query string: {query_string}")

        # Parse query string for auth parameters
        if query_string:
            from urllib.parse import parse_qs
            params = parse_qs(query_string)
            token = params.get('token', [None])[0]
            conversation_id = params.get('conversation_id', [None])[0]
            logger.info(f"🔌 Token from query: {'EXISTS' if token else 'NONE'}")

        # If no token in query, check auth object
        if not token and auth:
            token = auth.get('token')
            logger.info(f"🔌 Token from auth object: {'EXISTS' if token else 'NONE'}")

        # Authenticate the connection
        if not token:
            logger.error("❌ Socket.IO connection rejected: No token provided")
            return False

        logger.info(f"🔑 Authenticating token: {token[:20]}...")
        user_id, tenant_id = authenticate_websocket_connection(token)  # Not async
        logger.info(f"✅ Authentication successful - user: {user_id}, tenant: {tenant_id}")

        # Store connection metadata
        await sio.save_session(sid, {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'conversation_id': conversation_id,
            'authenticated': True
        })

        # Join conversation room if specified
        if conversation_id:
            await sio.enter_room(sid, f"conversation_{conversation_id}")
            logger.info(f"Socket.IO client {sid} joined conversation room: {conversation_id}")

        # Join tenant room for tenant-wide broadcasts
        await sio.enter_room(sid, f"tenant_{tenant_id}")

        logger.info(f"✅ Socket.IO client connected: {sid} (user: {user_id}, tenant: {tenant_id})")

        # Send connection confirmation
        await sio.emit('connected', {
            'status': 'connected',
            'user_id': user_id,
            'tenant_id': tenant_id,
            'conversation_id': conversation_id
        }, room=sid)

        return True

    except Exception as e:
        logger.error(f"❌ Socket.IO connection failed: {e}", exc_info=True)
        return False


@sio.event
async def disconnect(sid):
    """Handle Socket.IO client disconnection"""
    try:
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        conversation_id = session.get('conversation_id')

        logger.info(f"Socket.IO client disconnected: {sid} (user: {user_id})")

    except Exception as e:
        logger.error(f"Error handling Socket.IO disconnect: {e}")


@sio.event
async def join_conversation(sid, data):
    """Allow client to join a different conversation room"""
    try:
        session = await sio.get_session(sid)
        if not session.get('authenticated'):
            return {'error': 'Not authenticated'}

        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return {'error': 'conversation_id required'}

        # Leave previous conversation room if any
        old_conversation_id = session.get('conversation_id')
        if old_conversation_id:
            await sio.leave_room(sid, f"conversation_{old_conversation_id}")

        # Join new conversation room
        await sio.enter_room(sid, f"conversation_{conversation_id}")

        # Update session
        session['conversation_id'] = conversation_id
        await sio.save_session(sid, session)

        logger.info(f"Socket.IO client {sid} switched to conversation: {conversation_id}")

        return {'success': True, 'conversation_id': conversation_id}

    except Exception as e:
        logger.error(f"Error joining conversation: {e}")
        return {'error': str(e)}


# Enhanced WebSocket Manager with Socket.IO Integration
class SocketIOWebSocketManager(WebSocketManager):
    """Extended WebSocket manager with Socket.IO support for agentic features"""

    async def emit_phase_start_socketio(self, conversation_id: str, phase: str, metadata: Dict[str, Any] = None):
        """Emit agentic phase start via Socket.IO"""
        try:
            room = f"conversation_{conversation_id}"
            event_data = {
                'phase': phase,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata or {}
            }

            await sio.emit('phase_start', event_data, room=room)
            logger.debug(f"Socket.IO phase_start emitted to {room}: {phase}")

        except Exception as e:
            logger.error(f"Failed to emit Socket.IO phase_start: {e}")

    async def emit_phase_transition_socketio(self, conversation_id: str, from_phase: str, to_phase: str, metadata: Dict[str, Any] = None):
        """Emit agentic phase transition via Socket.IO"""
        try:
            room = f"conversation_{conversation_id}"
            event_data = {
                'from_phase': from_phase,
                'phase': to_phase,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata or {}
            }

            await sio.emit('phase_transition', event_data, room=room)
            logger.debug(f"Socket.IO phase_transition emitted to {room}: {from_phase} → {to_phase}")

        except Exception as e:
            logger.error(f"Failed to emit Socket.IO phase_transition: {e}")

    async def emit_tool_execution_socketio(self, conversation_id: str, tool_execution: Dict[str, Any]):
        """Emit tool execution update via Socket.IO"""
        try:
            room = f"conversation_{conversation_id}"
            event_data = {
                'tool_execution': tool_execution,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await sio.emit('tool_execution', event_data, room=room)
            logger.debug(f"Socket.IO tool_execution emitted to {room}: {tool_execution.get('name')} - {tool_execution.get('status')}")

        except Exception as e:
            logger.error(f"Failed to emit Socket.IO tool_execution: {e}")

    async def emit_subagent_status_socketio(self, conversation_id: str, subagent_status: Dict[str, Any]):
        """Emit subagent status update via Socket.IO"""
        try:
            room = f"conversation_{conversation_id}"
            event_data = {
                'subagent_status': subagent_status,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await sio.emit('subagent_status', event_data, room=room)
            logger.debug(f"Socket.IO subagent_status emitted to {room}: {subagent_status.get('type')} - {subagent_status.get('status')}")

        except Exception as e:
            logger.error(f"Failed to emit Socket.IO subagent_status: {e}")

    async def emit_source_retrieval_socketio(self, conversation_id: str, source_retrieval: Dict[str, Any]):
        """Emit source retrieval update via Socket.IO"""
        try:
            room = f"conversation_{conversation_id}"
            event_data = {
                'source_retrieval': source_retrieval,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await sio.emit('source_retrieval', event_data, room=room)
            logger.debug(f"Socket.IO source_retrieval emitted to {room}: {source_retrieval.get('type')} - {source_retrieval.get('status')}")

        except Exception as e:
            logger.error(f"Failed to emit Socket.IO source_retrieval: {e}")


# Create enhanced manager instance
socketio_websocket_manager = SocketIOWebSocketManager()

# Update helper functions to use Socket.IO
async def emit_agentic_phase_socketio(conversation_id: str, phase: str, metadata: Dict[str, Any] = None):
    """Helper function to emit agentic phase events via Socket.IO"""
    await socketio_websocket_manager.emit_phase_start_socketio(conversation_id, phase, metadata)

async def emit_tool_update_socketio(conversation_id: str, tool_id: str, name: str, status: str, **kwargs):
    """Helper function to emit tool execution updates via Socket.IO"""
    tool_execution = {
        "id": tool_id,
        "name": name,
        "status": status,
        "startTime": kwargs.get("start_time"),
        "endTime": kwargs.get("end_time"),
        "progress": kwargs.get("progress"),
        "arguments": kwargs.get("arguments"),
        "result": kwargs.get("result"),
        "error": kwargs.get("error")
    }
    # Filter out None values
    tool_execution = {k: v for k, v in tool_execution.items() if v is not None}
    await socketio_websocket_manager.emit_tool_execution_socketio(conversation_id, tool_execution)

async def emit_subagent_update_socketio(conversation_id: str, subagent_id: str, type_name: str, task: str, status: str, **kwargs):
    """Helper function to emit subagent status updates via Socket.IO"""
    subagent_status = {
        "id": subagent_id,
        "type": type_name,
        "task": task,
        "status": status,
        "startTime": kwargs.get("start_time"),
        "endTime": kwargs.get("end_time"),
        "progress": kwargs.get("progress"),
        "dependsOn": kwargs.get("depends_on"),
        "result": kwargs.get("result"),
        "error": kwargs.get("error")
    }
    # Filter out None values
    subagent_status = {k: v for k, v in subagent_status.items() if v is not None}
    await socketio_websocket_manager.emit_subagent_status_socketio(conversation_id, subagent_status)

async def emit_source_update_socketio(conversation_id: str, source_id: str, source_type: str, query: str, status: str, **kwargs):
    """Helper function to emit source retrieval updates via Socket.IO"""
    source_retrieval = {
        "id": source_id,
        "type": source_type,
        "query": query,
        "status": status,
        "results": kwargs.get("results")
    }
    # Filter out None values
    source_retrieval = {k: v for k, v in source_retrieval.items() if v is not None}
    await socketio_websocket_manager.emit_source_retrieval_socketio(conversation_id, source_retrieval)


async def broadcast_conversation_update(conversation_id: str, event: str, data: Dict[str, Any]):
    """
    Helper function to broadcast conversation updates via Socket.IO

    Args:
        conversation_id: Target conversation ID
        event: Event name (e.g., 'conversation:message_added', 'conversation:read')
        data: Event data to broadcast
    """
    try:
        room = f"conversation_{conversation_id}"
        await sio.emit(event, data, room=room)
        logger.debug(f"Socket.IO {event} emitted to {room}")
    except Exception as e:
        logger.error(f"Failed to broadcast conversation update via Socket.IO: {e}")


async def broadcast_to_user(user_id: str, tenant_id: str, event: str, data: Dict[str, Any]):
    """
    Helper function to broadcast to all of a user's connections via Socket.IO

    Args:
        user_id: Target user ID
        tenant_id: User's tenant ID
        event: Event name
        data: Event data to broadcast
    """
    try:
        # Broadcast to user's tenant room (all their devices)
        room = f"tenant_{tenant_id}"
        await sio.emit(event, data, room=room)
        logger.debug(f"Socket.IO {event} emitted to user {user_id} in {room}")
    except Exception as e:
        logger.error(f"Failed to broadcast to user via Socket.IO: {e}")