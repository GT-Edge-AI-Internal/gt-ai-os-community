"""
Team Access Control Service for GT 2.0 Tenant Backend

Implements team-based access control with file-based simplicity.
Follows GT 2.0's principle of "Zero Complexity Addition"
- Simple role-based permissions stored in files
- Fast access checks using SQLite indexes
- Perfect tenant isolation maintained
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import logging

from app.models.team import Team, TeamRole, OrganizationSettings
from app.models.agent import Agent
from app.models.document import RAGDataset

logger = logging.getLogger(__name__)


class TeamAccessService:
    """Elegant team-based access control following GT 2.0 philosophy"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._role_cache = {}  # Cache role permissions in memory
    
    async def check_team_access(
        self, 
        user_email: str, 
        resource: Any, 
        action: str,
        user_teams: Optional[List[int]] = None
    ) -> bool:
        """Check if user has access to perform action on resource
        
        GT 2.0 Design: Simple, fast access checks without complex hierarchies
        """
        try:
            # Step 1: Check resource ownership (fastest check)
            if hasattr(resource, 'created_by') and resource.created_by == user_email:
                return True  # Owners always have full access
            
            # Step 2: Check visibility-based access
            if hasattr(resource, 'visibility'):
                # Organization-wide resources
                if resource.visibility == "organization":
                    return self._check_organization_action(action)
                
                # Team resources
                if resource.visibility == "team" and resource.tenant_id:
                    if not user_teams:
                        user_teams = await self.get_user_teams(user_email)
                    
                    if resource.tenant_id in user_teams:
                        return await self._check_team_action(
                            user_email, 
                            resource.tenant_id, 
                            action
                        )
                
                # Explicitly shared resources
                if hasattr(resource, 'shared_with') and resource.shared_with:
                    if user_email in resource.shared_with:
                        return self._check_shared_action(action)
            
            # Step 3: Default deny for private resources not owned by user
            return False
            
        except Exception as e:
            logger.error(f"Error checking team access: {e}")
            return False  # Fail closed on errors
    
    async def get_user_teams(self, user_email: str) -> List[int]:
        """Get all teams the user belongs to
        
        GT 2.0: Simple file-based membership check
        """
        try:
            # Query all active teams
            result = await self.db.execute(
                select(Team).where(Team.is_active == True)
            )
            teams = result.scalars().all()
            
            user_team_ids = []
            for team in teams:
                if team.is_member(user_email):
                    user_team_ids.append(team.id)
            
            return user_team_ids
            
        except Exception as e:
            logger.error(f"Error getting user teams: {e}")
            return []
    
    async def get_user_role_in_team(self, user_email: str, team_id: int) -> Optional[str]:
        """Get user's role in a specific team"""
        try:
            result = await self.db.execute(
                select(Team).where(Team.id == team_id)
            )
            team = result.scalar_one_or_none()
            
            if team:
                return team.get_member_role(user_email)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user role: {e}")
            return None
    
    async def get_team_resources(
        self, 
        team_id: int, 
        resource_type: str,
        user_email: str
    ) -> List[Any]:
        """Get all resources accessible to a team
        
        GT 2.0: Simple visibility-based filtering
        """
        try:
            if resource_type == "agent":
                # Get team and organization agents
                result = await self.db.execute(
                    select(Agent).where(
                        and_(
                            Agent.is_active == True,
                            or_(
                                and_(
                                    Agent.visibility == "team",
                                    Agent.tenant_id == team_id
                                ),
                                Agent.visibility == "organization"
                            )
                        )
                    )
                )
                return result.scalars().all()
            
            elif resource_type == "dataset":
                # Get team and organization datasets
                result = await self.db.execute(
                    select(RAGDataset).where(
                        and_(
                            RAGDataset.status == "active",
                            or_(
                                and_(
                                    RAGDataset.visibility == "team",
                                    RAGDataset.tenant_id == team_id
                                ),
                                RAGDataset.visibility == "organization"
                            )
                        )
                    )
                )
                return result.scalars().all()
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting team resources: {e}")
            return []
    
    async def share_with_team(
        self, 
        resource: Any, 
        team_id: int,
        sharer_email: str
    ) -> bool:
        """Share a resource with a team
        
        GT 2.0: Simple visibility update, no complex permissions
        """
        try:
            # Verify sharer owns the resource or has sharing permission
            if not self._can_share_resource(resource, sharer_email):
                return False
            
            # Update resource visibility
            resource.visibility = "team"
            resource.tenant_id = team_id
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error sharing with team: {e}")
            await self.db.rollback()
            return False
    
    async def share_with_users(
        self, 
        resource: Any,
        user_emails: List[str],
        sharer_email: str
    ) -> bool:
        """Share a resource with specific users
        
        GT 2.0: Simple list-based sharing
        """
        try:
            # Verify sharer owns the resource
            if not self._can_share_resource(resource, sharer_email):
                return False
            
            # Update shared_with list
            current_shared = resource.shared_with or []
            new_shared = list(set(current_shared + user_emails))
            resource.shared_with = new_shared
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error sharing with users: {e}")
            await self.db.rollback()
            return False
    
    async def create_team(
        self,
        name: str,
        description: str,
        team_type: str,
        creator_email: str
    ) -> Optional[Team]:
        """Create a new team
        
        GT 2.0: File-based team with simple SQLite reference
        """
        try:
            # Check if user can create teams
            org_settings = await self._get_organization_settings()
            if not org_settings.allow_team_creation:
                logger.warning(f"Team creation disabled for organization")
                return None
            
            # Check user's team limit
            user_teams = await self.get_user_teams(creator_email)
            if len(user_teams) >= org_settings.max_teams_per_user:
                logger.warning(f"User {creator_email} reached team limit")
                return None
            
            # Create team
            team = Team(
                name=name,
                description=description,
                team_type=team_type,
                created_by=creator_email
            )
            
            # Initialize with placeholder paths
            team.config_file_path = "placeholder"
            team.members_file_path = "placeholder"
            
            # Save to get ID
            self.db.add(team)
            await self.db.flush()
            
            # Initialize proper file paths
            team.initialize_file_paths()
            
            # Add creator as owner
            team.add_member(creator_email, "owner", {"joined_as": "creator"})
            
            # Save initial config
            config = {
                "name": name,
                "description": description,
                "team_type": team_type,
                "created_by": creator_email,
                "settings": {}
            }
            team.save_config_to_file(config)
            
            await self.db.commit()
            await self.db.refresh(team)
            
            logger.info(f"Created team {team.id} by {creator_email}")
            return team
            
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            await self.db.rollback()
            return None
    
    # Private helper methods
    
    def _check_organization_action(self, action: str) -> bool:
        """Check if action is allowed for organization resources"""
        # Organization resources are viewable by all
        if action in ["view", "use", "read"]:
            return True
        # Only owners can modify
        return False
    
    async def _check_team_action(
        self, 
        user_email: str, 
        team_id: int, 
        action: str
    ) -> bool:
        """Check if user can perform action on team resource"""
        role = await self.get_user_role_in_team(user_email, team_id)
        if not role:
            return False
        
        # Get role permissions
        permissions = await self._get_role_permissions(role)
        
        # Map action to permission
        action_permission_map = {
            "view": "can_view_resources",
            "read": "can_view_resources",
            "use": "can_view_resources",
            "create": "can_create_resources",
            "edit": "can_edit_team_resources",
            "update": "can_edit_team_resources",
            "delete": "can_delete_team_resources",
            "manage_members": "can_manage_members",
            "manage_team": "can_manage_team",
        }
        
        permission_needed = action_permission_map.get(action, None)
        if permission_needed:
            return permissions.get(permission_needed, False)
        
        return False
    
    def _check_shared_action(self, action: str) -> bool:
        """Check if action is allowed for shared resources"""
        # Shared resources can be viewed and used
        if action in ["view", "use", "read"]:
            return True
        return False
    
    def _can_share_resource(self, resource: Any, user_email: str) -> bool:
        """Check if user can share a resource"""
        # Owners can always share
        if hasattr(resource, 'created_by') and resource.created_by == user_email:
            return True
        
        # Team leads can share team resources
        # (Would need to check team role here in full implementation)
        
        return False
    
    async def _get_role_permissions(self, role_name: str) -> Dict[str, bool]:
        """Get permissions for a role (with caching)"""
        if role_name in self._role_cache:
            return self._role_cache[role_name]
        
        result = await self.db.execute(
            select(TeamRole).where(TeamRole.name == role_name)
        )
        role = result.scalar_one_or_none()
        
        if role:
            permissions = {
                "can_view_resources": role.can_view_resources,
                "can_create_resources": role.can_create_resources,
                "can_edit_team_resources": role.can_edit_team_resources,
                "can_delete_team_resources": role.can_delete_team_resources,
                "can_manage_members": role.can_manage_members,
                "can_manage_team": role.can_manage_team,
            }
            self._role_cache[role_name] = permissions
            return permissions
        
        # Default to viewer permissions
        return {
            "can_view_resources": True,
            "can_create_resources": False,
            "can_edit_team_resources": False,
            "can_delete_team_resources": False,
            "can_manage_members": False,
            "can_manage_team": False,
        }
    
    async def _get_organization_settings(self) -> OrganizationSettings:
        """Get organization settings (create default if not exists)"""
        result = await self.db.execute(
            select(OrganizationSettings).limit(1)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Create default settings
            settings = OrganizationSettings(
                organization_name="Default Organization",
                organization_domain="example.com"
            )
            settings.config_file_path = "placeholder"
            self.db.add(settings)
            await self.db.flush()
            
            settings.initialize_file_paths()
            settings.save_config_to_file({
                "initialized": True,
                "default_config": True
            })
            
            await self.db.commit()
            await self.db.refresh(settings)
        
        return settings