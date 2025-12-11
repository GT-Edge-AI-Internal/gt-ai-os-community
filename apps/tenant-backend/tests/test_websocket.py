"""
Tests for WebSocket endpoints in GT 2.0 Tenant Backend
"""

import pytest
import json
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from app.main import app
from app.core.config import get_settings

settings = get_settings()


def create_test_token(user_id: str = "test_user", expired: bool = False) -> str:
    """Create test JWT token"""
    exp = datetime.utcnow() - timedelta(hours=1) if expired else datetime.utcnow() + timedelta(hours=1)
    payload = {
        "sub": user_id,
        "exp": exp
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class TestWebSocketEndpoints:
    """Test WebSocket endpoints"""
    
    def test_websocket_without_auth(self):
        """Test WebSocket connection without authentication fails"""
        client = TestClient(app)
        
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws"):
                pass  # Should fail without token
    
    def test_websocket_with_expired_token(self):
        """Test WebSocket connection with expired token fails"""
        client = TestClient(app)
        token = create_test_token(expired=True)
        
        with client.websocket_connect(f"/api/v1/ws?token={token}") as websocket:
            # Should be closed immediately
            assert websocket.closed
    
    @patch('app.api.websocket.get_db_session')
    def test_websocket_basic_connection(self, mock_db):
        """Test basic WebSocket connection with valid token"""
        client = TestClient(app)
        token = create_test_token()
        
        with client.websocket_connect(f"/api/v1/ws?token={token}") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "connection"
            assert data["status"] == "connected"
            assert "client_id" in data
            assert data["user_id"] == "test_user"
            
            # Test ping-pong
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response
            
            # Test status request
            websocket.send_json({"type": "status"})
            response = websocket.receive_json()
            assert response["type"] == "status"
            assert response["connected"] is True
    
    @patch('app.api.websocket.get_db_session')
    @patch('app.api.websocket.ConversationService')
    @patch('app.api.websocket.AssistantManager')
    def test_chat_websocket_connection(self, mock_assistant, mock_service, mock_db):
        """Test conversation-specific WebSocket connection"""
        client = TestClient(app)
        token = create_test_token()
        conversation_id = 1
        
        # Mock conversation service
        mock_service_instance = Mock()
        mock_service_instance.get_conversation = AsyncMock(return_value={
            "id": conversation_id,
            "agent_id": "test_assistant",
            "title": "Test Conversation"
        })
        mock_service.return_value = mock_service_instance
        
        # Mock database session
        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock()
        mock_db.return_value = mock_db_session
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "connection"
            assert data["status"] == "connected"
            assert data["conversation_id"] == conversation_id
            assert data["agent_id"] == "test_assistant"
            assert data["title"] == "Test Conversation"
    
    @patch('app.api.websocket.get_db_session')
    @patch('app.api.websocket.ConversationService')
    def test_chat_websocket_message_streaming(self, mock_service, mock_db):
        """Test message streaming through WebSocket"""
        client = TestClient(app)
        token = create_test_token()
        conversation_id = 1
        
        # Mock conversation service
        mock_service_instance = Mock()
        mock_service_instance.get_conversation = AsyncMock(return_value={
            "id": conversation_id,
            "agent_id": "test_assistant",
            "title": "Test Conversation"
        })
        
        # Mock streaming response
        async def mock_stream():
            chunks = ["Hello", " from", " AI", " agent"]
            for chunk in chunks:
                yield chunk
        
        mock_service_instance.stream_message_response = mock_stream
        mock_service.return_value = mock_service_instance
        
        # Mock database session
        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock()
        mock_db.return_value = mock_db_session
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as websocket:
            # Skip connection confirmation
            websocket.receive_json()
            
            # Send a message
            websocket.send_json({
                "type": "message",
                "content": "Hello AI"
            })
            
            # Should receive acknowledgment
            ack = websocket.receive_json()
            assert ack["type"] == "message_received"
            
            # Should receive stream start
            start = websocket.receive_json()
            assert start["type"] == "stream_start"
            assert start["role"] == "agent"
            
            # Should receive stream chunks
            chunks_received = []
            for _ in range(4):  # Expecting 4 chunks
                chunk = websocket.receive_json()
                assert chunk["type"] == "stream_chunk"
                assert chunk["role"] == "agent"
                chunks_received.append(chunk["content"])
            
            # Should receive completion
            complete = websocket.receive_json()
            assert complete["type"] == "stream_complete"
            assert complete["role"] == "agent"
            assert complete["full_content"] == "Hello from AI agent"
    
    @patch('app.api.websocket.get_db_session')
    @patch('app.api.websocket.ConversationService')
    def test_chat_websocket_typing_indicator(self, mock_service, mock_db):
        """Test typing indicator broadcasting"""
        client = TestClient(app)
        token = create_test_token("user1")
        conversation_id = 1
        
        # Mock conversation service
        mock_service_instance = Mock()
        mock_service_instance.get_conversation = AsyncMock(return_value={
            "id": conversation_id,
            "agent_id": "test_assistant",
            "title": "Test Conversation"
        })
        mock_service.return_value = mock_service_instance
        
        # Mock database session
        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock()
        mock_db.return_value = mock_db_session
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as websocket:
            # Skip connection confirmation
            websocket.receive_json()
            
            # Send typing indicator
            websocket.send_json({"type": "typing"})
            
            # In a real scenario, other clients would receive the broadcast
            # Here we're just testing that it doesn't error
    
    @patch('app.api.websocket.get_db_session')
    @patch('app.api.websocket.ConversationService')
    def test_chat_websocket_get_messages(self, mock_service, mock_db):
        """Test fetching messages through WebSocket"""
        client = TestClient(app)
        token = create_test_token()
        conversation_id = 1
        
        # Mock conversation service
        mock_service_instance = Mock()
        mock_service_instance.get_conversation = AsyncMock(side_effect=[
            # First call for connection
            {
                "id": conversation_id,
                "agent_id": "test_assistant",
                "title": "Test Conversation"
            },
            # Second call for getting messages
            {
                "id": conversation_id,
                "messages": [
                    {"id": 1, "role": "user", "content": "Hello"},
                    {"id": 2, "role": "agent", "content": "Hi there!"}
                ]
            }
        ])
        mock_service.return_value = mock_service_instance
        
        # Mock database session
        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock()
        mock_db.return_value = mock_db_session
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as websocket:
            # Skip connection confirmation
            websocket.receive_json()
            
            # Request messages
            websocket.send_json({
                "type": "get_messages",
                "limit": 10
            })
            
            # Should receive messages
            response = websocket.receive_json()
            assert response["type"] == "messages"
            assert len(response["messages"]) == 2
            assert response["messages"][0]["content"] == "Hello"
            assert response["messages"][1]["content"] == "Hi there!"
    
    def test_chat_websocket_invalid_conversation(self):
        """Test WebSocket connection to non-existent conversation"""
        client = TestClient(app)
        token = create_test_token()
        conversation_id = 999  # Non-existent
        
        with patch('app.api.websocket.get_db_session') as mock_db:
            with patch('app.api.websocket.ConversationService') as mock_service:
                # Mock conversation not found
                mock_service_instance = Mock()
                mock_service_instance.get_conversation = AsyncMock(return_value=None)
                mock_service.return_value = mock_service_instance
                
                # Mock database session
                mock_db_session = AsyncMock()
                mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
                mock_db_session.__aexit__ = AsyncMock()
                mock_db.return_value = mock_db_session
                
                with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as websocket:
                    # Should be closed due to access denied
                    assert websocket.closed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])