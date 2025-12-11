"""
Unit tests for GT 2.0 Agent System

Tests the file-based agent management system including:
- Agent creation from templates
- File-based configuration storage
- Agent cloning and modification
- Statistics and management operations
"""

import os
import pytest
import asyncio
import tempfile
import shutil
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import init_database, get_db_session, close_database
from app.services.assistant_manager import AssistantManager
from app.models.agent import Agent


@pytest.fixture
async def test_db() -> AsyncGenerator[None, None]:
    """Setup test database"""
    # Set test environment
    os.environ["ENVIRONMENT"] = "test"
    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test-key-for-unit-tests-only")
    os.environ["TENANT_ID"] = "test-tenant"
    os.environ["TENANT_DOMAIN"] = "test"
    
    await init_database()
    yield
    await close_database()


@pytest.fixture
async def assistant_manager(test_db) -> AsyncGenerator[AssistantManager, None]:
    """Get AssistantManager for testing"""
    async with get_db_session() as db:
        yield AssistantManager(db)


class TestAssistantCreation:
    """Test agent creation functionality"""
    
    @pytest.mark.asyncio
    async def test_create_from_template(self, assistant_manager: AssistantManager):
        """Test creating agent from template"""
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant",
            {"name": "Test Research Agent"},
            "test@example.com"
        )
        
        assert assistant_uuid is not None
        assert len(assistant_uuid) == 36  # UUID format
        
        # Verify agent was created
        config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
        assert config["name"] == "Test Research Agent"
        assert config["template_id"] == "research_assistant"
        assert len(config["capabilities"]) > 0
        assert len(config["prompt"]) > 0
    
    @pytest.mark.asyncio
    async def test_create_custom_assistant(self, assistant_manager: AssistantManager):
        """Test creating custom agent"""
        assistant_uuid = await assistant_manager.create_custom_assistant(
            {
                "name": "Custom Agent",
                "description": "My custom AI agent",
                "prompt": "You are a helpful custom agent.",
                "capabilities": [{"resource": "llm:groq", "actions": ["inference"]}]
            },
            "test@example.com"
        )
        
        assert assistant_uuid is not None
        
        # Verify agent was created
        config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
        assert config["name"] == "Custom Agent"
        assert config["template_id"] is None
        assert config["prompt"] == "You are a helpful custom agent."
    
    @pytest.mark.asyncio 
    async def test_invalid_template(self, assistant_manager: AssistantManager):
        """Test creating agent with invalid template"""
        # Should still work but use default configuration
        assistant_uuid = await assistant_manager.create_from_template(
            "nonexistent_template",
            {"name": "Test Agent"},
            "test@example.com"
        )
        
        assert assistant_uuid is not None
        config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
        assert config["name"] == "Test Agent"


class TestAssistantManagement:
    """Test agent management operations"""
    
    @pytest.mark.asyncio
    async def test_list_user_assistants(self, assistant_manager: AssistantManager):
        """Test listing user agents"""
        # Create multiple agents
        assistant1 = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Agent 1"}, "user1@example.com"
        )
        assistant2 = await assistant_manager.create_from_template(
            "coding_assistant", {"name": "Agent 2"}, "user1@example.com"
        )
        assistant3 = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Agent 3"}, "user2@example.com"
        )
        
        # List agents for user1
        user1_assistants = await assistant_manager.list_user_assistants("user1@example.com")
        assert len(user1_assistants) == 2
        
        names = [a["name"] for a in user1_assistants]
        assert "Agent 1" in names
        assert "Agent 2" in names
        assert "Agent 3" not in names
        
        # List agents for user2
        user2_assistants = await assistant_manager.list_user_assistants("user2@example.com")
        assert len(user2_assistants) == 1
        assert user2_assistants[0]["name"] == "Agent 3"
    
    @pytest.mark.asyncio
    async def test_update_configuration(self, assistant_manager: AssistantManager):
        """Test updating agent configuration"""
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Test Agent"}, "test@example.com"
        )
        
        # Update configuration
        updates = {
            "name": "Updated Agent",
            "description": "Updated description",
            "prompt": "You are an updated agent.",
            "config": {"temperature": 0.8}
        }
        
        success = await assistant_manager.update_configuration(
            assistant_uuid, updates, "test@example.com"
        )
        assert success is True
        
        # Verify updates
        config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
        assert config["name"] == "Updated Agent"
        assert config["description"] == "Updated description"
        assert config["prompt"] == "You are an updated agent."
        assert config["config"]["temperature"] == 0.8
    
    @pytest.mark.asyncio
    async def test_clone_assistant(self, assistant_manager: AssistantManager):
        """Test cloning agent"""
        # Create source agent
        source_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Source Agent"}, "test@example.com"
        )
        
        # Clone agent with modifications
        cloned_uuid = await assistant_manager.clone_assistant(
            source_uuid,
            "Cloned Agent", 
            "test@example.com",
            {"config": {"temperature": 0.9}, "prompt": "You are a cloned agent."}
        )
        
        assert cloned_uuid != source_uuid
        
        # Verify clone
        cloned_config = await assistant_manager.get_assistant_config(cloned_uuid, "test@example.com")
        assert cloned_config["name"] == "Cloned Agent"
        assert cloned_config["prompt"] == "You are a cloned agent."
        assert cloned_config["config"]["temperature"] == 0.9
        
        # Verify source unchanged
        source_config = await assistant_manager.get_assistant_config(source_uuid, "test@example.com")
        assert source_config["name"] == "Source Agent"
    
    @pytest.mark.asyncio
    async def test_archive_assistant(self, assistant_manager: AssistantManager):
        """Test archiving agent"""
        # Use unique name to avoid conflicts with other tests
        unique_name = "Archive Test Agent"
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": unique_name}, "archive_test@example.com"
        )
        
        # Verify agent exists before archiving
        assistants_before = await assistant_manager.list_user_assistants("archive_test@example.com")
        names_before = [a["name"] for a in assistants_before]
        assert unique_name in names_before
        
        # Archive agent
        success = await assistant_manager.archive_assistant(assistant_uuid, "archive_test@example.com")
        assert success is True
        
        # Verify agent is no longer listed as active
        assistants_after = await assistant_manager.list_user_assistants("archive_test@example.com")
        names_after = [a["name"] for a in assistants_after]
        assert unique_name not in names_after


class TestAssistantStatistics:
    """Test agent statistics and analytics"""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, assistant_manager: AssistantManager):
        """Test getting agent statistics"""
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Stats Agent"}, "test@example.com"
        )
        
        stats = await assistant_manager.get_assistant_statistics(assistant_uuid, "test@example.com")
        
        assert stats["assistant_uuid"] == assistant_uuid
        assert stats["name"] == "Stats Agent"
        assert stats["conversation_count"] == 0
        assert stats["total_messages"] == 0
        assert stats["total_tokens_used"] == 0
        assert stats["total_cost_cents"] == 0
        assert stats["created_at"] is not None


class TestAssistantSecurity:
    """Test security and isolation features"""
    
    @pytest.mark.asyncio
    async def test_user_isolation(self, assistant_manager: AssistantManager):
        """Test that users can only access their own agents"""
        # Create agent for user1
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "User1 Agent"}, "user1@example.com"
        )
        
        # Try to access as user2 - should fail
        with pytest.raises(ValueError, match="Agent not found"):
            await assistant_manager.get_assistant_config(assistant_uuid, "user2@example.com")
        
        # Try to update as user2 - should fail
        with pytest.raises(ValueError, match="Agent not found"):
            await assistant_manager.update_configuration(
                assistant_uuid, {"name": "Hacked"}, "user2@example.com"
            )


class TestFileBasedStorage:
    """Test file-based storage system"""
    
    @pytest.mark.asyncio
    async def test_file_structure_creation(self, assistant_manager: AssistantManager):
        """Test that proper file structure is created"""
        assistant_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "File Test Agent"}, "test@example.com"
        )
        
        config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
        
        # Check that files exist
        base_path = f"/tmp/gt2-data/test/agents/{assistant_uuid}"
        assert os.path.exists(f"{base_path}/config.json")
        assert os.path.exists(f"{base_path}/prompt.md")
        assert os.path.exists(f"{base_path}/capabilities.json")
        
        # Check directory structure
        assert os.path.exists(f"{base_path}/memory")
        assert os.path.exists(f"{base_path}/memory/conversations")
        assert os.path.exists(f"{base_path}/memory/context")
        assert os.path.exists(f"{base_path}/resources")


class TestTemplateSystem:
    """Test built-in template system"""
    
    @pytest.mark.asyncio
    async def test_all_builtin_templates(self, assistant_manager: AssistantManager):
        """Test all built-in templates"""
        templates = [
            "research_assistant",
            "coding_assistant", 
            "cyber_analyst",
            "educational_tutor"
        ]
        
        for template_id in templates:
            assistant_uuid = await assistant_manager.create_from_template(
                template_id,
                {"name": f"Test {template_id}"},
                "test@example.com"
            )
            
            config = await assistant_manager.get_assistant_config(assistant_uuid, "test@example.com")
            assert config["template_id"] == template_id
            assert config["name"] == f"Test {template_id}"
            assert len(config["capabilities"]) > 0
            assert len(config["prompt"]) > 0
    
    @pytest.mark.asyncio
    async def test_template_specific_configurations(self, assistant_manager: AssistantManager):
        """Test template-specific configurations"""
        # Research agent should have research-oriented capabilities
        research_uuid = await assistant_manager.create_from_template(
            "research_assistant", {"name": "Research Test"}, "test@example.com"
        )
        research_config = await assistant_manager.get_assistant_config(research_uuid, "test@example.com")
        
        # Should have semantic search capability
        capabilities = research_config["capabilities"]
        has_rag = any("rag:semantic_search" in str(cap) for cap in capabilities)
        assert has_rag
        
        # Coding agent should have development-oriented capabilities
        coding_uuid = await assistant_manager.create_from_template(
            "coding_assistant", {"name": "Coding Test"}, "test@example.com"
        )
        coding_config = await assistant_manager.get_assistant_config(coding_uuid, "test@example.com")
        
        # Should have github integration capability
        capabilities = coding_config["capabilities"]
        has_github = any("github_integration" in str(cap) for cap in capabilities)
        assert has_github


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])