"""
Access Group Models for GT 2.0 Resource Cluster

Simplified models for resource access control.
These are lighter versions focused on MCP resource management.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class AccessGroup(str, Enum):
    """Resource access levels"""
    INDIVIDUAL = "individual"  # Private to owner
    TEAM = "team"              # Shared with specific users
    ORGANIZATION = "organization"  # Read-only for all tenant users


@dataclass
class Resource:
    """Base resource model for MCP services"""
    id: str
    name: str
    resource_type: str
    owner_id: str
    tenant_domain: str
    access_group: AccessGroup
    team_members: List[str]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "resource_type": self.resource_type,
            "owner_id": self.owner_id,
            "tenant_domain": self.tenant_domain,
            "access_group": self.access_group.value,
            "team_members": self.team_members,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
    
    def can_access(self, user_id: str, tenant_domain: str) -> bool:
        """Check if user can access this resource"""
        # Check tenant isolation
        if self.tenant_domain != tenant_domain:
            return False
        
        # Owner always has access
        if self.owner_id == user_id:
            return True
        
        # Check access group permissions
        if self.access_group == AccessGroup.INDIVIDUAL:
            return False
        elif self.access_group == AccessGroup.TEAM:
            return user_id in self.team_members
        elif self.access_group == AccessGroup.ORGANIZATION:
            return True  # All tenant users have read access
        
        return False