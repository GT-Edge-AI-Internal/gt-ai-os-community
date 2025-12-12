"""
Access Controller Service for GT 2.0

Manages resource access control with capability-based security.
Ensures perfect tenant isolation and proper permission cascading.
"""

import os
import stat
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
from pathlib import Path

from app.models.access_group import (
    AccessGroup, TenantStructure, User, Resource,
    ResourceCreate, ResourceUpdate, ResourceResponse
)
from app.core.security import verify_capability_token
from app.core.database import get_db_session


logger = logging.getLogger(__name__)


class AccessController:
    """
    Centralized access control service
    Manages permissions for all resources with tenant isolation
    """
    
    def __init__(self, tenant_domain: str):
        self.tenant_domain = tenant_domain
        self.base_path = Path(f"/data/{tenant_domain}")
        self._ensure_tenant_directory()
    
    def _ensure_tenant_directory(self):
        """
        Ensure tenant directory exists with proper permissions
        OS User: gt-{tenant_domain}-{pod_id}
        Permissions: 700 (owner only)
        """
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)
            # Set strict permissions - owner only
            os.chmod(self.base_path, stat.S_IRWXU)  # 700
            logger.info(f"Created tenant directory: {self.base_path} with 700 permissions")
    
    async def check_permission(
        self, 
        user_id: str, 
        resource: Resource, 
        action: str = "read"
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has permission for action on resource
        
        Args:
            user_id: User requesting access
            resource: Resource being accessed
            action: read, write, delete, share
            
        Returns:
            Tuple of (allowed, reason)
        """
        # Verify tenant isolation
        if resource.tenant_domain != self.tenant_domain:
            logger.warning(f"Cross-tenant access attempt: {user_id} -> {resource.id}")
            return False, "Cross-tenant access denied"
        
        # Owner has all permissions
        if resource.owner_id == user_id:
            return True, "Owner access granted"
        
        # Check action-specific permissions
        if action == "read":
            return self._check_read_permission(user_id, resource)
        elif action == "write":
            return self._check_write_permission(user_id, resource)
        elif action == "delete":
            return False, "Only owner can delete"
        elif action == "share":
            return False, "Only owner can share"
        else:
            return False, f"Unknown action: {action}"
    
    def _check_read_permission(self, user_id: str, resource: Resource) -> Tuple[bool, str]:
        """Check read permission based on access group"""
        if resource.access_group == AccessGroup.ORGANIZATION:
            return True, "Organization-wide read access"
        elif resource.access_group == AccessGroup.TEAM:
            if user_id in resource.team_members:
                return True, "Team member read access"
            return False, "Not a team member"
        else:  # INDIVIDUAL
            return False, "Private resource"
    
    def _check_write_permission(self, user_id: str, resource: Resource) -> Tuple[bool, str]:
        """Check write permission - only owner can write"""
        return False, "Only owner can modify"
    
    async def create_resource(
        self,
        user_id: str,
        resource_data: ResourceCreate,
        capability_token: str
    ) -> Resource:
        """
        Create a new resource with proper access control
        
        Args:
            user_id: User creating the resource
            resource_data: Resource creation data
            capability_token: JWT capability token
            
        Returns:
            Created resource
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Create resource
        resource = Resource(
            id=self._generate_resource_id(),
            name=resource_data.name,
            resource_type=resource_data.resource_type,
            owner_id=user_id,
            tenant_domain=self.tenant_domain,
            access_group=resource_data.access_group,
            team_members=resource_data.team_members or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=resource_data.metadata or {},
            file_path=None
        )
        
        # Create file-based storage if needed
        if self._requires_file_storage(resource.resource_type):
            resource.file_path = await self._create_resource_file(resource)
        
        # Audit log
        logger.info(f"Resource created: {resource.id} by {user_id} in {self.tenant_domain}")
        
        return resource
    
    async def update_resource_access(
        self,
        user_id: str,
        resource_id: str,
        new_access_group: AccessGroup,
        team_members: Optional[List[str]] = None
    ) -> Resource:
        """
        Update resource access group
        
        Args:
            user_id: User requesting update
            resource_id: Resource to update
            new_access_group: New access level
            team_members: Team members if team access
            
        Returns:
            Updated resource
        """
        # Load resource
        resource = await self._load_resource(resource_id)
        
        # Check permission
        allowed, reason = await self.check_permission(user_id, resource, "share")
        if not allowed:
            raise PermissionError(f"Access denied: {reason}")
        
        # Update access
        old_group = resource.access_group
        resource.update_access_group(new_access_group, team_members)
        
        # Update file permissions if needed
        if resource.file_path:
            await self._update_file_permissions(resource)
        
        # Audit log
        logger.info(
            f"Access updated: {resource_id} from {old_group} to {new_access_group} "
            f"by {user_id}"
        )
        
        return resource
    
    async def list_accessible_resources(
        self,
        user_id: str,
        resource_type: Optional[str] = None
    ) -> List[Resource]:
        """
        List all resources accessible to user
        
        Args:
            user_id: User requesting list
            resource_type: Filter by type
            
        Returns:
            List of accessible resources
        """
        accessible = []
        
        # Get all resources in tenant
        all_resources = await self._list_tenant_resources(resource_type)
        
        for resource in all_resources:
            allowed, _ = await self.check_permission(user_id, resource, "read")
            if allowed:
                accessible.append(resource)
        
        return accessible
    
    async def get_resource_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get resource statistics for user
        
        Args:
            user_id: User to get stats for
            
        Returns:
            Statistics dictionary
        """
        all_resources = await self._list_tenant_resources()
        
        owned = [r for r in all_resources if r.owner_id == user_id]
        accessible = await self.list_accessible_resources(user_id)
        
        stats = {
            "owned_count": len(owned),
            "accessible_count": len(accessible),
            "by_type": {},
            "by_access_group": {
                AccessGroup.INDIVIDUAL: 0,
                AccessGroup.TEAM: 0,
                AccessGroup.ORGANIZATION: 0
            }
        }
        
        for resource in owned:
            # Count by type
            if resource.resource_type not in stats["by_type"]:
                stats["by_type"][resource.resource_type] = 0
            stats["by_type"][resource.resource_type] += 1
            
            # Count by access group
            stats["by_access_group"][resource.access_group] += 1
        
        return stats
    
    def _generate_resource_id(self) -> str:
        """Generate unique resource ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _requires_file_storage(self, resource_type: str) -> bool:
        """Check if resource type requires file storage"""
        file_based_types = [
            "agent", "dataset", "document", "workflow", 
            "notebook", "model", "configuration"
        ]
        return resource_type in file_based_types
    
    async def _create_resource_file(self, resource: Resource) -> str:
        """
        Create file for resource with proper permissions
        
        Args:
            resource: Resource to create file for
            
        Returns:
            File path
        """
        # Determine path based on resource type
        type_dir = self.base_path / resource.resource_type / resource.id
        type_dir.mkdir(parents=True, exist_ok=True)
        
        # Create main file
        file_path = type_dir / "data.json"
        file_path.touch()
        
        # Set strict permissions - 700 for directory, 600 for file
        os.chmod(type_dir, stat.S_IRWXU)  # 700
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        
        logger.info(f"Created resource file: {file_path} with secure permissions")
        
        return str(file_path)
    
    async def _update_file_permissions(self, resource: Resource):
        """Update file permissions (always 700/600 for security)"""
        if not resource.file_path or not Path(resource.file_path).exists():
            return
        
        # Permissions don't change based on access group
        # All files remain 700/600 for OS-level security
        # Access control is handled at application level
        pass
    
    async def _load_resource(self, resource_id: str) -> Resource:
        """Load resource from storage"""
        try:
            # Search for resource in all resource type directories
            for resource_type_dir in self.base_path.iterdir():
                if not resource_type_dir.is_dir():
                    continue
                
                resource_file = resource_type_dir / "data.json"
                if resource_file.exists():
                    try:
                        import json
                        with open(resource_file, 'r') as f:
                            resources_data = json.load(f)
                        
                        if not isinstance(resources_data, list):
                            resources_data = [resources_data]
                        
                        for resource_data in resources_data:
                            if resource_data.get('id') == resource_id:
                                return Resource(
                                    id=resource_data['id'],
                                    name=resource_data['name'],
                                    resource_type=resource_data['resource_type'],
                                    owner_id=resource_data['owner_id'],
                                    tenant_domain=resource_data['tenant_domain'],
                                    access_group=AccessGroup(resource_data['access_group']),
                                    team_members=resource_data.get('team_members', []),
                                    created_at=datetime.fromisoformat(resource_data['created_at']),
                                    updated_at=datetime.fromisoformat(resource_data['updated_at']),
                                    metadata=resource_data.get('metadata', {}),
                                    file_path=resource_data.get('file_path')
                                )
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"Failed to parse resource file {resource_file}: {e}")
                        continue
            
            raise ValueError(f"Resource {resource_id} not found")
            
        except Exception as e:
            logger.error(f"Failed to load resource {resource_id}: {e}")
            raise
    
    async def _list_tenant_resources(
        self, 
        resource_type: Optional[str] = None
    ) -> List[Resource]:
        """List all resources in tenant"""
        try:
            import json
            resources = []
            
            # If specific resource type requested, search only that directory
            search_dirs = [self.base_path / resource_type] if resource_type else list(self.base_path.iterdir())
            
            for resource_type_dir in search_dirs:
                if not resource_type_dir.exists() or not resource_type_dir.is_dir():
                    continue
                
                resource_file = resource_type_dir / "data.json"
                if resource_file.exists():
                    try:
                        with open(resource_file, 'r') as f:
                            resources_data = json.load(f)
                        
                        if not isinstance(resources_data, list):
                            resources_data = [resources_data]
                        
                        for resource_data in resources_data:
                            try:
                                resource = Resource(
                                    id=resource_data['id'],
                                    name=resource_data['name'],
                                    resource_type=resource_data['resource_type'],
                                    owner_id=resource_data['owner_id'],
                                    tenant_domain=resource_data['tenant_domain'],
                                    access_group=AccessGroup(resource_data['access_group']),
                                    team_members=resource_data.get('team_members', []),
                                    created_at=datetime.fromisoformat(resource_data['created_at']),
                                    updated_at=datetime.fromisoformat(resource_data['updated_at']),
                                    metadata=resource_data.get('metadata', {}),
                                    file_path=resource_data.get('file_path')
                                )
                                resources.append(resource)
                            except (KeyError, ValueError) as e:
                                logger.warning(f"Failed to parse resource data: {e}")
                                continue
                                
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning(f"Failed to read resource file {resource_file}: {e}")
                        continue
            
            return resources
            
        except Exception as e:
            logger.error(f"Failed to list tenant resources: {e}")
            raise


class AccessControlMiddleware:
    """
    Middleware for enforcing access control on API requests
    """
    
    def __init__(self, tenant_domain: str):
        self.controller = AccessController(tenant_domain)
    
    async def verify_request(
        self,
        user_id: str,
        resource_id: str,
        action: str,
        capability_token: str
    ) -> bool:
        """
        Verify request has proper permissions
        
        Args:
            user_id: User making request
            resource_id: Resource being accessed
            action: Action being performed
            capability_token: JWT capability token
            
        Returns:
            True if allowed, raises PermissionError if not
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data:
            raise PermissionError("Invalid capability token")
        
        # Verify tenant match
        if token_data.get("tenant_id") != self.controller.tenant_domain:
            raise PermissionError("Tenant mismatch in capability token")
        
        # Load resource and check permission
        resource = await self.controller._load_resource(resource_id)
        allowed, reason = await self.controller.check_permission(
            user_id, resource, action
        )
        
        if not allowed:
            logger.warning(
                f"Access denied: {user_id} -> {resource_id} ({action}): {reason}"
            )
            raise PermissionError(f"Access denied: {reason}")
        
        return True