"""
Assistant Builder Service for GT 2.0

Manages assistant creation, deployment, and lifecycle.
Integrates with template library and file-based storage.
"""

import os
import json
import stat
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import logging

from app.models.assistant_template import (
    AssistantTemplate, AssistantInstance, AssistantBuilder,
    AssistantType, PersonalityConfig, ResourcePreferences, MemorySettings,
    AssistantTemplateLibrary, BUILTIN_TEMPLATES
)
from app.models.access_group import AccessGroup
from app.core.security import verify_capability_token
from app.services.access_controller import AccessController


logger = logging.getLogger(__name__)


class AssistantBuilderService:
    """
    Service for building and managing assistants
    Handles both template-based and custom assistant creation
    """
    
    def __init__(self, tenant_domain: str, resource_cluster_url: str = "http://resource-cluster:8004"):
        self.tenant_domain = tenant_domain
        self.base_path = Path(f"/data/{tenant_domain}/assistants")
        self.template_library = AssistantTemplateLibrary(resource_cluster_url)
        self.access_controller = AccessController(tenant_domain)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure assistant directories exist with proper permissions"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base_path, stat.S_IRWXU)  # 700
        
        # Create subdirectories
        for subdir in ["templates", "instances", "shared"]:
            path = self.base_path / subdir
            path.mkdir(exist_ok=True)
            os.chmod(path, stat.S_IRWXU)  # 700
    
    async def create_from_template(
        self,
        template_id: str,
        user_id: str,
        instance_name: str,
        customizations: Optional[Dict[str, Any]] = None,
        capability_token: str = None
    ) -> AssistantInstance:
        """
        Create assistant instance from template
        
        Args:
            template_id: Template to use
            user_id: User creating the assistant
            instance_name: Name for the instance
            customizations: Optional customizations
            capability_token: JWT capability token
            
        Returns:
            Created assistant instance
        """
        # Verify capability token
        if capability_token:
            token_data = verify_capability_token(capability_token)
            if not token_data or token_data.get("tenant_id") != self.tenant_domain:
                raise PermissionError("Invalid capability token")
        
        # Deploy from template
        instance = await self.template_library.deploy_template(
            template_id=template_id,
            user_id=user_id,
            instance_name=instance_name,
            tenant_domain=self.tenant_domain,
            customizations=customizations
        )
        
        # Create file storage
        await self._create_assistant_files(instance)
        
        # Save to database (would be SQLite in production)
        await self._save_assistant(instance)
        
        logger.info(f"Created assistant {instance.id} from template {template_id} for {user_id}")
        
        return instance
    
    async def create_custom(
        self,
        builder_config: AssistantBuilder,
        user_id: str,
        capability_token: str = None
    ) -> AssistantInstance:
        """
        Create custom assistant from builder configuration
        
        Args:
            builder_config: Custom assistant configuration
            user_id: User creating the assistant
            capability_token: JWT capability token
            
        Returns:
            Created assistant instance
        """
        # Verify capability token
        if capability_token:
            token_data = verify_capability_token(capability_token)
            if not token_data or token_data.get("tenant_id") != self.tenant_domain:
                raise PermissionError("Invalid capability token")
            
            # Check if user has required capabilities
            user_capabilities = token_data.get("capabilities", [])
            for required_cap in builder_config.requested_capabilities:
                if not any(required_cap in cap.get("resource", "") for cap in user_capabilities):
                    raise PermissionError(f"Missing capability: {required_cap}")
        
        # Build instance
        instance = builder_config.build_instance(user_id, self.tenant_domain)
        
        # Create file storage
        await self._create_assistant_files(instance)
        
        # Save to database
        await self._save_assistant(instance)
        
        logger.info(f"Created custom assistant {instance.id} for {user_id}")
        
        return instance
    
    async def get_assistant(
        self, 
        assistant_id: str, 
        user_id: str
    ) -> Optional[AssistantInstance]:
        """
        Get assistant instance by ID
        
        Args:
            assistant_id: Assistant ID
            user_id: User requesting the assistant
            
        Returns:
            Assistant instance if found and accessible
        """
        # Load assistant
        instance = await self._load_assistant(assistant_id)
        if not instance:
            return None
        
        # Check access permission
        allowed, _ = await self.access_controller.check_permission(
            user_id, instance, "read"
        )
        if not allowed:
            return None
        
        return instance
    
    async def list_user_assistants(
        self,
        user_id: str,
        include_shared: bool = True
    ) -> List[AssistantInstance]:
        """
        List all assistants accessible to user
        
        Args:
            user_id: User to list assistants for
            include_shared: Include team/org shared assistants
            
        Returns:
            List of accessible assistants
        """
        assistants = []
        
        # Get owned assistants
        owned = await self._get_owned_assistants(user_id)
        assistants.extend(owned)
        
        # Get shared assistants if requested
        if include_shared:
            shared = await self._get_shared_assistants(user_id)
            assistants.extend(shared)
        
        return assistants
    
    async def update_assistant(
        self,
        assistant_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> AssistantInstance:
        """
        Update assistant configuration
        
        Args:
            assistant_id: Assistant to update
            user_id: User requesting update
            updates: Configuration updates
            
        Returns:
            Updated assistant instance
        """
        # Load assistant
        instance = await self._load_assistant(assistant_id)
        if not instance:
            raise ValueError(f"Assistant not found: {assistant_id}")
        
        # Check permission
        if instance.owner_id != user_id:
            raise PermissionError("Only owner can update assistant")
        
        # Apply updates
        if "personality" in updates:
            instance.personality_config = PersonalityConfig(**updates["personality"])
        if "resources" in updates:
            instance.resource_preferences = ResourcePreferences(**updates["resources"])
        if "memory" in updates:
            instance.memory_settings = MemorySettings(**updates["memory"])
        if "system_prompt" in updates:
            instance.system_prompt = updates["system_prompt"]
        
        instance.updated_at = datetime.utcnow()
        
        # Save changes
        await self._save_assistant(instance)
        await self._update_assistant_files(instance)
        
        logger.info(f"Updated assistant {assistant_id} by {user_id}")
        
        return instance
    
    async def share_assistant(
        self,
        assistant_id: str,
        user_id: str,
        access_group: AccessGroup,
        team_members: Optional[List[str]] = None
    ) -> AssistantInstance:
        """
        Share assistant with team or organization
        
        Args:
            assistant_id: Assistant to share
            user_id: User sharing (must be owner)
            access_group: New access level
            team_members: Team members if team access
            
        Returns:
            Updated assistant instance
        """
        # Load assistant
        instance = await self._load_assistant(assistant_id)
        if not instance:
            raise ValueError(f"Assistant not found: {assistant_id}")
        
        # Check ownership
        if instance.owner_id != user_id:
            raise PermissionError("Only owner can share assistant")
        
        # Update access
        instance.access_group = access_group
        if access_group == AccessGroup.TEAM:
            instance.team_members = team_members or []
        else:
            instance.team_members = []
        
        instance.updated_at = datetime.utcnow()
        
        # Save changes
        await self._save_assistant(instance)
        
        logger.info(f"Shared assistant {assistant_id} with {access_group.value} by {user_id}")
        
        return instance
    
    async def delete_assistant(
        self,
        assistant_id: str,
        user_id: str
    ) -> bool:
        """
        Delete assistant and its files
        
        Args:
            assistant_id: Assistant to delete
            user_id: User requesting deletion
            
        Returns:
            True if deleted
        """
        # Load assistant
        instance = await self._load_assistant(assistant_id)
        if not instance:
            return False
        
        # Check ownership
        if instance.owner_id != user_id:
            raise PermissionError("Only owner can delete assistant")
        
        # Delete files
        await self._delete_assistant_files(instance)
        
        # Delete from database
        await self._delete_assistant_record(assistant_id)
        
        logger.info(f"Deleted assistant {assistant_id} by {user_id}")
        
        return True
    
    async def get_assistant_statistics(
        self,
        assistant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get usage statistics for assistant
        
        Args:
            assistant_id: Assistant ID
            user_id: User requesting stats
            
        Returns:
            Statistics dictionary
        """
        # Load assistant
        instance = await self.get_assistant(assistant_id, user_id)
        if not instance:
            raise ValueError(f"Assistant not found or not accessible: {assistant_id}")
        
        return {
            "assistant_id": assistant_id,
            "name": instance.name,
            "created_at": instance.created_at.isoformat(),
            "last_used": instance.last_used.isoformat() if instance.last_used else None,
            "conversation_count": instance.conversation_count,
            "total_messages": instance.total_messages,
            "total_tokens_used": instance.total_tokens_used,
            "access_group": instance.access_group.value,
            "team_members_count": len(instance.team_members),
            "linked_datasets_count": len(instance.linked_datasets),
            "linked_tools_count": len(instance.linked_tools)
        }
    
    async def _create_assistant_files(self, instance: AssistantInstance):
        """Create file structure for assistant"""
        # Get file paths
        file_structure = instance.get_file_structure()
        
        # Create directories
        for key, path in file_structure.items():
            if key in ["memory", "resources"]:
                # These are directories
                Path(path).mkdir(parents=True, exist_ok=True)
                os.chmod(Path(path), stat.S_IRWXU)  # 700
            else:
                # These are files
                parent = Path(path).parent
                parent.mkdir(parents=True, exist_ok=True)
                os.chmod(parent, stat.S_IRWXU)  # 700
        
        # Save configuration
        config_path = Path(file_structure["config"])
        config_data = {
            "id": instance.id,
            "name": instance.name,
            "template_id": instance.template_id,
            "personality": instance.personality_config.model_dump(),
            "resources": instance.resource_preferences.model_dump(),
            "memory": instance.memory_settings.model_dump(),
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat()
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        
        # Save prompt
        prompt_path = Path(file_structure["prompt"])
        with open(prompt_path, 'w') as f:
            f.write(instance.system_prompt)
        os.chmod(prompt_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        
        # Save capabilities
        capabilities_path = Path(file_structure["capabilities"])
        with open(capabilities_path, 'w') as f:
            json.dump(instance.capabilities, f, indent=2)
        os.chmod(capabilities_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        
        # Update instance with file paths
        instance.config_file_path = str(config_path)
        instance.memory_file_path = str(Path(file_structure["memory"]))
    
    async def _update_assistant_files(self, instance: AssistantInstance):
        """Update assistant files with current configuration"""
        if instance.config_file_path:
            config_data = {
                "id": instance.id,
                "name": instance.name,
                "template_id": instance.template_id,
                "personality": instance.personality_config.model_dump(),
                "resources": instance.resource_preferences.model_dump(),
                "memory": instance.memory_settings.model_dump(),
                "created_at": instance.created_at.isoformat(),
                "updated_at": instance.updated_at.isoformat()
            }
            
            with open(instance.config_file_path, 'w') as f:
                json.dump(config_data, f, indent=2)
    
    async def _delete_assistant_files(self, instance: AssistantInstance):
        """Delete assistant file structure"""
        file_structure = instance.get_file_structure()
        base_dir = Path(file_structure["config"]).parent
        
        if base_dir.exists():
            import shutil
            shutil.rmtree(base_dir)
            logger.info(f"Deleted assistant files at {base_dir}")
    
    async def _save_assistant(self, instance: AssistantInstance):
        """Save assistant to database (SQLite in production)"""
        # This would save to SQLite database
        # For now, we'll save to a JSON file as placeholder
        db_file = self.base_path / "instances" / f"{instance.id}.json"
        with open(db_file, 'w') as f:
            json.dump(instance.model_dump(mode='json'), f, indent=2, default=str)
        os.chmod(db_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
    
    async def _load_assistant(self, assistant_id: str) -> Optional[AssistantInstance]:
        """Load assistant from database"""
        db_file = self.base_path / "instances" / f"{assistant_id}.json"
        if not db_file.exists():
            return None
        
        with open(db_file, 'r') as f:
            data = json.load(f)
        
        # Convert datetime strings back to datetime objects
        for field in ['created_at', 'updated_at', 'last_used']:
            if field in data and data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        return AssistantInstance(**data)
    
    async def _delete_assistant_record(self, assistant_id: str):
        """Delete assistant from database"""
        db_file = self.base_path / "instances" / f"{assistant_id}.json"
        if db_file.exists():
            db_file.unlink()
    
    async def _get_owned_assistants(self, user_id: str) -> List[AssistantInstance]:
        """Get assistants owned by user"""
        assistants = []
        instances_dir = self.base_path / "instances"
        
        if instances_dir.exists():
            for file in instances_dir.glob("*.json"):
                instance = await self._load_assistant(file.stem)
                if instance and instance.owner_id == user_id:
                    assistants.append(instance)
        
        return assistants
    
    async def _get_shared_assistants(self, user_id: str) -> List[AssistantInstance]:
        """Get assistants shared with user"""
        assistants = []
        instances_dir = self.base_path / "instances"
        
        if instances_dir.exists():
            for file in instances_dir.glob("*.json"):
                instance = await self._load_assistant(file.stem)
                if instance and instance.owner_id != user_id:
                    # Check if user has access
                    allowed, _ = await self.access_controller.check_permission(
                        user_id, instance, "read"
                    )
                    if allowed:
                        assistants.append(instance)
        
        return assistants