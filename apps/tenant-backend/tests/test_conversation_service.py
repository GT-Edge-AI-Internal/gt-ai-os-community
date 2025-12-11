"""
Unit tests for Conversation Service and Agent Manager
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from faker import Faker

from app.services.conversation_service import ConversationService
from app.services.assistant_manager import AssistantManager
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.agent import Agent

fake = Faker()


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_resource_client():
    """Mock Resource Cluster client"""
    client = Mock()
    client.execute_inference = AsyncMock()
    client._stream_inference = AsyncMock()
    client.generate_capability_token = Mock(return_value="mock.jwt.token")
    return client


@pytest.fixture
def mock_assistant_manager():
    """Mock Agent Manager"""
    manager = Mock(spec=AssistantManager)
    manager.get_assistant_config = AsyncMock()
    return manager


@pytest.fixture
def conversation_service(mock_db_session, mock_resource_client, mock_assistant_manager):
    """Create ConversationService with mocked dependencies"""
    service = ConversationService(mock_db_session)
    service.resource_client = mock_resource_client
    service.assistant_manager = mock_assistant_manager
    return service


@pytest.fixture
def sample_assistant_config():
    """Sample agent configuration"""
    return {
        "name": "Research Agent",
        "prompt": "You are a research agent specialized in data analysis.",
        "resource_preferences": {
            "primary_llm": "llama-3.1-70b-versatile",
            "temperature": 0.7,
            "max_tokens": 4000
        },
        "capabilities": ["llm", "rag", "web_search"]
    }


@pytest.fixture
def sample_conversation():
    """Sample conversation object"""
    conversation = Mock(spec=Conversation)
    conversation.id = 1
    conversation.title = "Test Conversation"
    conversation.agent_id = "agent-123"
    conversation.model_id = "llama-3.1-70b-versatile"
    conversation.system_prompt = "You are a helpful AI agent."
    conversation.message_count = 2
    conversation.total_tokens = 150
    conversation.created_by = "user@example.com"
    conversation.created_at = datetime.utcnow() - timedelta(hours=1)
    conversation.updated_at = datetime.utcnow()
    conversation.messages = []
    return conversation


@pytest.fixture
def sample_message():
    """Sample message object"""
    message = Mock(spec=Message)
    message.id = 1
    message.conversation_id = 1
    message.role = "user"
    message.content = "Hello, how are you?"
    message.model_used = None
    message.tokens_used = 5
    message.created_at = datetime.utcnow()
    return message


class TestConversationService:
    """Test the ConversationService class"""
    
    @pytest.mark.asyncio
    async def test_create_conversation_success(self, conversation_service, mock_db_session, mock_assistant_manager, sample_assistant_config):
        """Test successful conversation creation"""
        # Mock agent config retrieval
        mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
        
        # Mock database operations
        created_conversation = Mock(spec=Conversation)
        created_conversation.id = 1
        created_conversation.title = "Conversation with Research Agent"
        created_conversation.agent_id = "agent-123"
        created_conversation.model_id = "llama-3.1-70b-versatile"
        created_conversation.created_at = datetime.utcnow()
        
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 1))
        
        result = await conversation_service.create_conversation(
            agent_id="agent-123",
            title="Test Conversation",
            user_identifier="user@example.com"
        )
        
        # Verify agent config was retrieved
        mock_assistant_manager.get_assistant_config.assert_called_once_with(
            "agent-123",
            "user@example.com"
        )
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "id" in result
        assert "title" in result
        assert "agent_id" in result
        assert "created_at" in result
    
    @pytest.mark.asyncio
    async def test_create_conversation_assistant_not_found(self, conversation_service, mock_assistant_manager):
        """Test conversation creation when agent not found"""
        # Mock agent not found
        mock_assistant_manager.get_assistant_config.return_value = None
        
        with pytest.raises(ValueError, match="Agent .* not found"):
            await conversation_service.create_conversation(
                agent_id="nonexistent",
                title="Test Conversation",
                user_identifier="user@example.com"
            )
    
    @pytest.mark.asyncio
    async def test_create_conversation_database_error(self, conversation_service, mock_db_session, mock_assistant_manager, sample_assistant_config):
        """Test conversation creation with database error"""
        mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
        mock_db_session.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await conversation_service.create_conversation(
                agent_id="agent-123",
                title="Test Conversation",
                user_identifier="user@example.com"
            )
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_conversations_success(self, conversation_service, mock_db_session, sample_conversation):
        """Test successful conversation listing"""
        # Mock database query results
        mock_result = Mock()
        mock_result.scalars.return_value.all.side_effect = [
            [sample_conversation],  # Total count query
            [sample_conversation]   # Paginated query
        ]
        mock_db_session.execute.return_value = mock_result
        
        result = await conversation_service.list_conversations(
            user_identifier="user@example.com",
            limit=20,
            offset=0
        )
        
        assert result["total"] == 1
        assert len(result["conversations"]) == 1
        assert result["conversations"][0]["id"] == 1
        assert result["conversations"][0]["title"] == "Test Conversation"
        assert result["limit"] == 20
        assert result["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_list_conversations_with_assistant_filter(self, conversation_service, mock_db_session, sample_conversation):
        """Test conversation listing with agent filter"""
        mock_result = Mock()
        mock_result.scalars.return_value.all.side_effect = [
            [sample_conversation],  # Total count
            [sample_conversation]   # Filtered results
        ]
        mock_db_session.execute.return_value = mock_result
        
        result = await conversation_service.list_conversations(
            user_identifier="user@example.com",
            agent_id="agent-123",
            limit=10,
            offset=5
        )
        
        assert result["total"] == 1
        assert len(result["conversations"]) == 1
        assert result["limit"] == 10
        assert result["offset"] == 5
    
    @pytest.mark.asyncio
    async def test_get_conversation_success(self, conversation_service, mock_db_session, sample_conversation):
        """Test successful conversation retrieval"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_conversation
        mock_db_session.execute.return_value = mock_result
        
        result = await conversation_service.get_conversation(
            conversation_id=1,
            user_identifier="user@example.com",
            include_messages=False
        )
        
        assert result["id"] == 1
        assert result["title"] == "Test Conversation"
        assert result["agent_id"] == "agent-123"
        assert result["message_count"] == 2
        assert result["total_tokens"] == 150
        assert "messages" not in result  # Not included
    
    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(self, conversation_service, mock_db_session, sample_conversation, sample_message):
        """Test conversation retrieval with messages included"""
        sample_conversation.messages = [sample_message]
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_conversation
        mock_db_session.execute.return_value = mock_result
        
        result = await conversation_service.get_conversation(
            conversation_id=1,
            user_identifier="user@example.com",
            include_messages=True
        )
        
        assert result["id"] == 1
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["id"] == 1
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == "Hello, how are you?"
    
    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, conversation_service, mock_db_session):
        """Test conversation retrieval when not found"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Conversation .* not found"):
            await conversation_service.get_conversation(
                conversation_id=999,
                user_identifier="user@example.com"
            )
    
    @pytest.mark.asyncio
    async def test_send_message_non_streaming_success(self, conversation_service, mock_db_session, mock_resource_client, mock_assistant_manager, sample_conversation, sample_assistant_config):
        """Test successful non-streaming message sending"""
        # Mock conversation retrieval
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=sample_conversation), \
             patch.object(conversation_service, '_get_conversation_context', return_value=[]):
            
            # Mock agent config
            mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
            
            # Mock LLM response
            mock_response = {
                "content": "Hello! I'm doing well, thank you for asking.",
                "model": "llama-3.1-70b-versatile",
                "usage": {"total_tokens": 25}
            }
            mock_resource_client.execute_inference.return_value = mock_response
            
            result = await conversation_service.send_message(
                conversation_id=1,
                content="Hello, how are you?",
                user_identifier="user@example.com",
                stream=False
            )
            
            # Verify resource client was called
            mock_resource_client.execute_inference.assert_called_once()
            
            # Verify database operations (2 messages added)
            assert mock_db_session.add.call_count == 2
            mock_db_session.commit.assert_called_once()
            
            # Verify response
            assert result["content"] == "Hello! I'm doing well, thank you for asking."
            assert result["tokens_used"] == 25
            assert result["model_used"] == "llama-3.1-70b-versatile"
            
            # Verify conversation stats updated
            assert sample_conversation.message_count == 4  # was 2, added 2
            assert sample_conversation.total_tokens == 175  # was 150, added 25
    
    @pytest.mark.asyncio
    async def test_send_message_streaming_mode(self, conversation_service, mock_db_session, mock_assistant_manager, sample_conversation, sample_assistant_config):
        """Test message sending in streaming mode"""
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=sample_conversation):
            mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
            
            result = await conversation_service.send_message(
                conversation_id=1,
                content="Tell me a story",
                user_identifier="user@example.com",
                stream=True
            )
            
            # Verify streaming response
            assert result["stream"] is True
            assert "stream_endpoint" in result
            assert "message_id" in result
            assert "/stream" in result["stream_endpoint"]
    
    @pytest.mark.asyncio
    async def test_stream_message_response(self, conversation_service, mock_db_session, mock_resource_client, mock_assistant_manager, sample_conversation, sample_assistant_config):
        """Test streaming message response"""
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=sample_conversation), \
             patch.object(conversation_service, '_get_conversation_context', return_value=[]):
            
            mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
            
            # Mock streaming response
            async def mock_stream():
                for chunk in ["Hello", " there!", " How", " can", " I", " help?"]:
                    yield chunk
            
            mock_resource_client._stream_inference.return_value = mock_stream()
            
            # Collect streaming results
            chunks = []
            async for chunk in conversation_service.stream_message_response(
                conversation_id=1,
                message_content="Hello",
                user_identifier="user@example.com"
            ):
                chunks.append(chunk)
            
            # Verify streaming worked
            assert len(chunks) == 6
            assert "".join(chunks) == "Hello there! How can I help?"
            
            # Verify database operations
            assert mock_db_session.add.call_count == 2  # User message + agent message
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, conversation_service, mock_db_session, sample_conversation):
        """Test successful conversation deletion"""
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=sample_conversation):
            result = await conversation_service.delete_conversation(
                conversation_id=1,
                user_identifier="user@example.com"
            )
            
            assert result is True
            mock_db_session.delete.assert_called_once_with(sample_conversation)
            mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_conversation_database_error(self, conversation_service, mock_db_session, sample_conversation):
        """Test conversation deletion with database error"""
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=sample_conversation):
            mock_db_session.delete.side_effect = Exception("Delete failed")
            
            with pytest.raises(Exception, match="Delete failed"):
                await conversation_service.delete_conversation(
                    conversation_id=1,
                    user_identifier="user@example.com"
                )
            
            mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_conversation_for_user_success(self, conversation_service, mock_db_session, sample_conversation):
        """Test internal method for getting conversation with user check"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_conversation
        mock_db_session.execute.return_value = mock_result
        
        result = await conversation_service._get_conversation_for_user(1, "user@example.com")
        
        assert result == sample_conversation
    
    @pytest.mark.asyncio
    async def test_get_conversation_for_user_not_found(self, conversation_service, mock_db_session):
        """Test internal method when conversation not found or not owned by user"""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValueError, match="Conversation .* not found"):
            await conversation_service._get_conversation_for_user(999, "user@example.com")
    
    @pytest.mark.asyncio
    async def test_get_conversation_context(self, conversation_service, mock_db_session, sample_message):
        """Test conversation context retrieval"""
        # Create multiple messages for context
        messages = []
        for i in range(5):
            msg = Mock(spec=Message)
            msg.role = "user" if i % 2 == 0 else "agent"
            msg.content = f"Message {i}"
            msg.created_at = datetime.utcnow() - timedelta(minutes=5-i)
            messages.append(msg)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = messages
        mock_db_session.execute.return_value = mock_result
        
        context = await conversation_service._get_conversation_context(1, limit=5)
        
        # Verify context format and order (should be chronological)
        assert len(context) == 5
        assert context[0]["content"] == "Message 4"  # Oldest after reverse
        assert context[-1]["content"] == "Message 0"  # Newest after reverse
        
        # Verify all have role and content
        for msg in context:
            assert "role" in msg
            assert "content" in msg


class TestConversationServiceIntegration:
    """Integration tests for ConversationService workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_conversation_workflow(self, conversation_service, mock_db_session, mock_resource_client, mock_assistant_manager, sample_assistant_config):
        """Test complete conversation workflow from creation to messaging"""
        # 1. Create conversation
        mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
        
        created_conversation = Mock(spec=Conversation)
        created_conversation.id = 1
        created_conversation.title = "Test Workflow"
        created_conversation.agent_id = "agent-123"
        created_conversation.model_id = "llama-3.1-70b-versatile"
        created_conversation.created_at = datetime.utcnow()
        created_conversation.message_count = 0
        created_conversation.total_tokens = 0
        created_conversation.updated_at = datetime.utcnow()
        
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 1))
        
        create_result = await conversation_service.create_conversation(
            agent_id="agent-123",
            title="Test Workflow",
            user_identifier="user@example.com"
        )
        
        assert create_result["id"] == 1
        assert create_result["title"] == "Test Workflow"
        
        # 2. Send message
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=created_conversation), \
             patch.object(conversation_service, '_get_conversation_context', return_value=[]):
            
            mock_response = {
                "content": "Hello! How can I help you today?",
                "model": "llama-3.1-70b-versatile",
                "usage": {"total_tokens": 30}
            }
            mock_resource_client.execute_inference.return_value = mock_response
            
            message_result = await conversation_service.send_message(
                conversation_id=1,
                content="Hello!",
                user_identifier="user@example.com",
                stream=False
            )
            
            assert message_result["content"] == "Hello! How can I help you today?"
            assert message_result["tokens_used"] == 30
        
        # 3. List conversations (should include our new one)
        mock_result = Mock()
        mock_result.scalars.return_value.all.side_effect = [
            [created_conversation],  # Count query
            [created_conversation]   # List query
        ]
        mock_db_session.execute.return_value = mock_result
        
        list_result = await conversation_service.list_conversations("user@example.com")
        
        assert list_result["total"] == 1
        assert len(list_result["conversations"]) == 1
        assert list_result["conversations"][0]["id"] == 1
        
        # 4. Get conversation details
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = created_conversation
        mock_db_session.execute.return_value = mock_result
        
        get_result = await conversation_service.get_conversation(
            conversation_id=1,
            user_identifier="user@example.com"
        )
        
        assert get_result["id"] == 1
        assert get_result["title"] == "Test Workflow"
        
        # 5. Delete conversation
        with patch.object(conversation_service, '_get_conversation_for_user', return_value=created_conversation):
            delete_result = await conversation_service.delete_conversation(
                conversation_id=1,
                user_identifier="user@example.com"
            )
            
            assert delete_result is True
    
    @pytest.mark.asyncio
    async def test_conversation_context_management(self, conversation_service, mock_db_session):
        """Test conversation context management with multiple messages"""
        # Create conversation history
        messages = []
        message_pairs = [
            ("user", "What is machine learning?"),
            ("agent", "Machine learning is a subset of AI..."),
            ("user", "Can you give me an example?"),
            ("agent", "Sure! An example is image recognition..."),
            ("user", "How does neural network training work?")
        ]
        
        for i, (role, content) in enumerate(message_pairs):
            msg = Mock(spec=Message)
            msg.role = role
            msg.content = content
            msg.created_at = datetime.utcnow() - timedelta(minutes=len(message_pairs)-i)
            messages.append(msg)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = messages
        mock_db_session.execute.return_value = mock_result
        
        # Get context with limit
        context = await conversation_service._get_conversation_context(1, limit=10)
        
        # Verify context maintains conversation flow
        assert len(context) == 5
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "What is machine learning?"
        assert context[1]["role"] == "agent"
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "How does neural network training work?"
        
        # Test limited context
        limited_context = await conversation_service._get_conversation_context(1, limit=3)
        assert len(limited_context) == 3
        # Should get the 3 most recent messages in chronological order
        assert limited_context[0]["content"] == "Can you give me an example?"
    
    @pytest.mark.asyncio
    async def test_error_handling_and_rollback(self, conversation_service, mock_db_session, mock_resource_client, mock_assistant_manager, sample_assistant_config):
        """Test error handling and database rollback"""
        # Test rollback on message sending failure
        with patch.object(conversation_service, '_get_conversation_for_user') as mock_get_conv, \
             patch.object(conversation_service, '_get_conversation_context', return_value=[]):
            
            sample_conversation = Mock(spec=Conversation)
            sample_conversation.agent_id = "agent-123"
            sample_conversation.message_count = 0
            sample_conversation.total_tokens = 0
            
            mock_get_conv.return_value = sample_conversation
            mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
            
            # Mock resource client failure
            mock_resource_client.execute_inference.side_effect = Exception("LLM inference failed")
            
            with pytest.raises(Exception, match="LLM inference failed"):
                await conversation_service.send_message(
                    conversation_id=1,
                    content="Test message",
                    user_identifier="user@example.com",
                    stream=False
                )
            
            # Verify rollback was called
            mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_streaming_with_context(self, conversation_service, mock_db_session, mock_resource_client, mock_assistant_manager, sample_assistant_config):
        """Test streaming response with conversation context"""
        with patch.object(conversation_service, '_get_conversation_for_user') as mock_get_conv, \
             patch.object(conversation_service, '_get_conversation_context') as mock_get_context:
            
            sample_conversation = Mock(spec=Conversation)
            sample_conversation.agent_id = "agent-123"
            sample_conversation.message_count = 2
            sample_conversation.total_tokens = 50
            
            mock_get_conv.return_value = sample_conversation
            mock_assistant_manager.get_assistant_config.return_value = sample_assistant_config
            
            # Mock conversation context
            mock_get_context.return_value = [
                {"role": "user", "content": "Hello"},
                {"role": "agent", "content": "Hi there!"}
            ]
            
            # Mock streaming
            async def mock_stream():
                for chunk in ["Based", " on", " our", " previous", " conversation..."]:
                    yield chunk
            
            mock_resource_client._stream_inference.return_value = mock_stream()
            
            # Test streaming
            chunks = []
            async for chunk in conversation_service.stream_message_response(
                conversation_id=1,
                message_content="Continue our discussion",
                user_identifier="user@example.com"
            ):
                chunks.append(chunk)
            
            assert len(chunks) == 5
            full_response = "".join(chunks)
            assert "Based on our previous conversation..." == full_response
            
            # Verify context was retrieved and used
            mock_get_context.assert_called_once_with(1)
            
            # Verify conversation stats were updated
            assert sample_conversation.message_count == 4  # was 2, added 2
            assert sample_conversation.total_tokens > 50   # Increased