"""
WebSocket Integration Service for GT 2.0 Tenant Backend

Bridges the conversation service with WebSocket real-time streaming.
Provides AI response streaming and event-driven message broadcasting.

GT 2.0 Architecture Principles:
- Zero downtime: Non-blocking AI response streaming
- Perfect tenant isolation: All streaming scoped to tenant
- Self-contained: No external dependencies
- Event-driven: Integrates with event automation system
"""

import asyncio
import logging
import json
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.conversation_service import ConversationService
from app.services.event_service import EventService, EventType
from app.services.agent_service import AgentService
from app.websocket import get_websocket_manager, ChatMessage

logger = logging.getLogger(__name__)


class WebSocketService:
    """
    Service for WebSocket-integrated AI conversation streaming.
    
    Combines conversation service with real-time WebSocket delivery.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_service = ConversationService(db)
        self.event_service = EventService(db)
        # Agent service will be initialized per request with tenant context
        self.websocket_manager = get_websocket_manager()
    
    async def stream_ai_response(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
        tenant_id: str,
        connection_id: str
    ) -> None:
        """
        Stream AI response to WebSocket connection with real-time updates.
        
        Args:
            conversation_id: Target conversation
            user_message: User's message content
            user_id: User identifier
            tenant_id: Tenant for isolation
            connection_id: WebSocket connection to stream to
        """
        try:
            # Send streaming start notification
            await self.websocket_manager.send_to_connection(connection_id, {
                "type": "ai_response_start",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Add user message to conversation
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
                user_id=user_id
            )
            
            # Emit message sent event
            await self.event_service.emit_event(
                event_type=EventType.MESSAGE_SENT,
                user_id=user_id,
                tenant_id=tenant_id,
                data={
                    "conversation_id": conversation_id,
                    "message_type": "user",
                    "content_length": len(user_message),
                    "streaming": True
                }
            )
            
            # Get conversation context for AI response
            conversation = await self.conversation_service.get_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                include_messages=True
            )
            
            if not conversation:
                raise ValueError("Conversation not found")
            
            # Stream AI response
            full_response = ""
            message_id = str(uuid.uuid4())
            
            # Get AI response generator
            async for chunk in self._generate_ai_response_stream(conversation, user_message):
                full_response += chunk
                
                # Send chunk to WebSocket
                await self.websocket_manager.send_to_connection(connection_id, {
                    "type": "ai_response_chunk",
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "content": chunk,
                    "full_content_so_far": full_response,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Broadcast to other conversation participants
                await self.websocket_manager.broadcast_to_conversation(
                    conversation_id,
                    {
                        "type": "ai_typing",
                        "conversation_id": conversation_id,
                        "content_preview": full_response[-50:] if len(full_response) > 50 else full_response
                    },
                    exclude_connection=connection_id
                )
            
            # Save complete AI response
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="agent",
                content=full_response,
                user_id=user_id,
                message_id=message_id
            )
            
            # Send completion notification
            await self.websocket_manager.send_to_connection(connection_id, {
                "type": "ai_response_complete",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "full_content": full_response,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Broadcast completion to conversation participants
            await self.websocket_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "new_ai_message",
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "content": full_response,
                    "timestamp": datetime.utcnow().isoformat()
                },
                exclude_connection=connection_id
            )
            
            # Emit AI response event
            await self.event_service.emit_event(
                event_type=EventType.MESSAGE_SENT,
                user_id=user_id,
                tenant_id=tenant_id,
                data={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "message_type": "agent",
                    "content_length": len(full_response),
                    "streaming_completed": True
                }
            )
            
            logger.info(f"AI response streaming completed for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error streaming AI response: {e}")
            
            # Send error notification
            await self.websocket_manager.send_to_connection(connection_id, {
                "type": "ai_response_error",
                "conversation_id": conversation_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            raise
    
    async def _generate_ai_response_stream(
        self,
        conversation: Dict[str, Any],
        user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate AI response stream chunks.
        
        This is a placeholder implementation. In production, this would
        integrate with the actual LLM service for streaming responses.
        
        Args:
            conversation: Conversation context
            user_message: User's message
            
        Yields:
            Response text chunks
        """
        # Get agent configuration
        agent_id = conversation.get("agent_id")
        if agent_id:
            # Initialize AgentService with tenant context
            agent_service = AgentService(tenant_id, user_id)
            agent_config = await agent_service.get_agent(agent_id)
            assistant_config = agent_config if agent_config else {}
        else:
            assistant_config = {}
        
        # Build conversation context
        messages = conversation.get("messages", [])
        context = []
        
        # Add system prompt if available
        system_prompt = assistant_config.get("prompt", "You are a helpful AI agent.")
        context.append({"role": "system", "content": system_prompt})
        
        # Add recent conversation history (last 10 messages)
        for msg in messages[-10:]:
            context.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        context.append({"role": "user", "content": user_message})
        
        # Simulate AI response streaming (replace with real LLM integration)
        # This demonstrates the streaming pattern that would be used with actual AI services
        response_text = await self._generate_mock_response(user_message, context)
        
        # Stream response in chunks
        chunk_size = 5  # Characters per chunk for demo
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            
            # Add realistic delay for streaming effect
            await asyncio.sleep(0.05)
            
            yield chunk
    
    async def _generate_mock_response(
        self,
        user_message: str,
        context: list
    ) -> str:
        """
        Generate mock AI response for development.
        
        In production, this would be replaced with actual LLM API calls.
        
        Args:
            user_message: User's message
            context: Conversation context
            
        Returns:
            Generated response text
        """
        # Simple mock response based on user input
        if "hello" in user_message.lower():
            return "Hello! I'm your AI agent. How can I help you today?"
        elif "help" in user_message.lower():
            return "I'm here to help! You can ask me questions, request information, or have a conversation. What would you like to know?"
        elif "weather" in user_message.lower():
            return "I don't have access to real-time weather data, but I'd be happy to help you find weather information or discuss weather patterns in general."
        elif "time" in user_message.lower():
            return f"The current time is approximately {datetime.utcnow().strftime('%H:%M UTC')}. Is there anything else I can help you with?"
        else:
            return f"Thank you for your message: '{user_message}'. I understand you're looking for assistance. Could you provide more details about what you'd like help with?"
    
    async def handle_typing_indicator(
        self,
        conversation_id: str,
        user_id: str,
        is_typing: bool,
        connection_id: str
    ) -> None:
        """
        Handle and broadcast typing indicators.
        
        Args:
            conversation_id: Target conversation
            user_id: User who is typing
            is_typing: Whether user is currently typing
            connection_id: Connection that sent the indicator
        """
        try:
            # Broadcast typing indicator to other conversation participants
            await self.websocket_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "user_typing",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "is_typing": is_typing,
                    "timestamp": datetime.utcnow().isoformat()
                },
                exclude_connection=connection_id
            )
            
            logger.debug(f"Typing indicator broadcast: {user_id} {'started' if is_typing else 'stopped'} typing")
            
        except Exception as e:
            logger.error(f"Error handling typing indicator: {e}")
    
    async def send_system_notification(
        self,
        user_id: str,
        tenant_id: str,
        notification: Dict[str, Any]
    ) -> None:
        """
        Send system notification to all user connections.
        
        Args:
            user_id: Target user
            tenant_id: Tenant for isolation
            notification: Notification data
        """
        try:
            message = {
                "type": "system_notification",
                "notification": notification,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.websocket_manager.send_to_user(
                user_id=user_id,
                tenant_id=tenant_id,
                message=message
            )
            
            logger.info(f"System notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending system notification: {e}")
    
    async def broadcast_conversation_update(
        self,
        conversation_id: str,
        update_type: str,
        update_data: Dict[str, Any]
    ) -> None:
        """
        Broadcast conversation update to all participants.
        
        Args:
            conversation_id: Target conversation
            update_type: Type of update (title_changed, participant_added, etc.)
            update_data: Update details
        """
        try:
            message = {
                "type": "conversation_update",
                "conversation_id": conversation_id,
                "update_type": update_type,
                "update_data": update_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.websocket_manager.broadcast_to_conversation(
                conversation_id,
                message
            )
            
            logger.info(f"Conversation update broadcast: {update_type} for {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting conversation update: {e}")
    
    async def get_connection_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get WebSocket connection statistics for tenant.
        
        Args:
            tenant_id: Tenant to get stats for
            
        Returns:
            Connection statistics
        """
        try:
            all_stats = self.websocket_manager.get_connection_stats()
            
            return {
                "tenant_connections": all_stats["connections_by_tenant"].get(tenant_id, 0),
                "active_conversations": len([
                    conv_id for conv_id, connections in self.websocket_manager.conversation_connections.items()
                    if any(
                        self.websocket_manager.connections.get(conn_id, {}).tenant_id == tenant_id
                        for conn_id in connections
                    )
                ])
            }
            
        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            return {"tenant_connections": 0, "active_conversations": 0}


# Factory function for dependency injection
async def get_websocket_service(db: AsyncSession = None) -> WebSocketService:
    """Get WebSocket service instance"""
    if db is None:
        async with get_db_session() as session:
            return WebSocketService(session)
    return WebSocketService(db)