"""
Collaboration Team Models for GT 2.0 Tenant Backend

Pydantic models for user collaboration teams (team sharing system).
This is separate from the tenant isolation 'tenants' table (formerly 'teams').

Database Schema:
- teams: User collaboration groups within a tenant
- team_memberships: Team members with two-tier permissions
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class TeamBase(BaseModel):
    """Base team model with common fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Team name")
    description: Optional[str] = Field(None, description="Team description")


class TeamCreate(TeamBase):
    """Model for creating a new team"""
    pass


class TeamUpdate(BaseModel):
    """Model for updating a team"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class TeamMember(BaseModel):
    """Team member with permissions"""
    id: str = Field(..., description="Membership UUID")
    team_id: str = Field(..., description="Team UUID")
    user_id: str = Field(..., description="User UUID")
    user_email: str = Field(..., description="User email")
    user_name: str = Field(..., description="User display name")
    team_permission: str = Field(..., description="Team-level permission: 'read', 'share', or 'manager'")
    resource_permissions: Dict[str, str] = Field(default_factory=dict, description="Resource-level permissions JSONB")
    is_owner: bool = Field(default=False, description="Whether this member is the team owner")
    is_observable: bool = Field(default=False, description="Member consents to activity observation")
    observable_consent_status: str = Field(default="none", description="Consent status: 'none', 'pending', 'approved', 'revoked'")
    observable_consent_at: Optional[str] = Field(None, description="When Observable status was approved")
    status: str = Field(default="accepted", description="Membership status: 'pending', 'accepted', or 'declined'")
    invited_at: Optional[str] = None
    responded_at: Optional[str] = None
    joined_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Team(TeamBase):
    """Complete team model with metadata"""
    id: str = Field(..., description="Team UUID")
    tenant_id: str = Field(..., description="Tenant UUID")
    owner_id: str = Field(..., description="Owner user UUID")
    owner_name: Optional[str] = Field(None, description="Owner display name")
    owner_email: Optional[str] = Field(None, description="Owner email")
    is_owner: bool = Field(..., description="Whether current user is the owner")
    can_manage: bool = Field(..., description="Whether current user can manage the team")
    user_permission: Optional[str] = Field(None, description="Current user's team permission: 'read' or 'share' (None if owner)")
    member_count: int = Field(0, description="Number of team members")
    shared_resource_count: int = Field(0, description="Number of shared resources (agents and datasets)")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TeamWithMembers(Team):
    """Team with full member list"""
    members: List[TeamMember] = Field(default_factory=list, description="List of team members")


class TeamListResponse(BaseModel):
    """Response model for listing teams"""
    data: List[Team]
    total: int

    model_config = ConfigDict(from_attributes=True)


class TeamResponse(BaseModel):
    """Response model for single team operation"""
    data: Team

    model_config = ConfigDict(from_attributes=True)


class TeamWithMembersResponse(BaseModel):
    """Response model for team with members"""
    data: TeamWithMembers

    model_config = ConfigDict(from_attributes=True)


# Team Membership Models

class AddMemberRequest(BaseModel):
    """Request model for adding a member to a team"""
    user_email: str = Field(..., description="Email of user to add")
    team_permission: str = Field("read", description="Team permission: 'read', 'share', or 'manager'")


class UpdateMemberPermissionRequest(BaseModel):
    """Request model for updating member permission"""
    team_permission: str = Field(..., description="New permission: 'read', 'share', or 'manager'")

    @field_validator('team_permission')
    @classmethod
    def validate_permission(cls, v: str) -> str:
        if v not in ["read", "share", "manager"]:
            raise ValueError(f"Invalid permission: {v}. Must be 'read', 'share', or 'manager'")
        return v


class MemberListResponse(BaseModel):
    """Response model for listing team members"""
    data: List[TeamMember]
    total: int

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    """Response model for single member operation"""
    data: TeamMember

    model_config = ConfigDict(from_attributes=True)


# Team Invitation Models

class TeamInvitation(BaseModel):
    """Pending team invitation"""
    id: str = Field(..., description="Invitation (membership) UUID")
    team_id: str = Field(..., description="Team UUID")
    team_name: str = Field(..., description="Team name")
    team_description: Optional[str] = Field(None, description="Team description")
    owner_name: str = Field(..., description="Team owner display name")
    owner_email: str = Field(..., description="Team owner email")
    team_permission: str = Field(..., description="Invited permission: 'read', 'share', or 'manager'")
    observable_requested: bool = Field(default=False, description="Whether Observable access was requested on invite")
    invited_at: str = Field(..., description="Invitation timestamp")

    model_config = ConfigDict(from_attributes=True)


class InvitationActionRequest(BaseModel):
    """Request to accept or decline invitation"""
    action: str = Field(..., description="Action: 'accept' or 'decline'")


class InvitationListResponse(BaseModel):
    """Response model for listing invitations"""
    data: List[TeamInvitation]
    total: int

    model_config = ConfigDict(from_attributes=True)


# Resource Sharing Models

class ShareResourceRequest(BaseModel):
    """Request model for sharing a resource to team"""
    resource_type: str = Field(..., description="Resource type: 'agent' or 'dataset'")
    resource_id: str = Field(..., description="Resource UUID")
    user_permissions: Dict[str, str] = Field(
        ...,
        description="User permissions: {user_id: 'read'|'edit'}"
    )


class SharedResource(BaseModel):
    """Model for a shared resource"""
    resource_type: str = Field(..., description="Resource type: 'agent' or 'dataset'")
    resource_id: str = Field(..., description="Resource UUID")
    resource_name: str = Field(..., description="Resource name")
    resource_owner: str = Field(..., description="Resource owner name or email")
    user_permissions: Dict[str, str] = Field(..., description="User permissions map")


class SharedResourcesResponse(BaseModel):
    """Response model for listing shared resources"""
    data: List[SharedResource]
    total: int

    model_config = ConfigDict(from_attributes=True)


# Observable Request Models

class ObservableRequest(BaseModel):
    """Observable access request for a team member"""
    team_id: str = Field(..., description="Team UUID")
    team_name: str = Field(..., description="Team name")
    requested_by_name: str = Field(..., description="Name of manager/owner who requested")
    requested_by_email: str = Field(..., description="Email of manager/owner who requested")
    requested_at: str = Field(..., description="When request was made")

    model_config = ConfigDict(from_attributes=True)


class ObservableRequestListResponse(BaseModel):
    """Response model for listing Observable requests"""
    data: List[ObservableRequest]
    total: int

    model_config = ConfigDict(from_attributes=True)


# Team Activity Models

class TeamActivityMetrics(BaseModel):
    """Team activity metrics for Observable members"""
    team_id: str
    team_name: str
    date_range_days: int
    observable_member_count: int
    total_member_count: int
    team_totals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated metrics: conversations, messages, tokens"
    )
    member_breakdown: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-member activity stats"
    )
    time_series: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Activity over time"
    )

    model_config = ConfigDict(from_attributes=True)


class TeamActivityResponse(BaseModel):
    """Response model for team activity"""
    data: TeamActivityMetrics

    model_config = ConfigDict(from_attributes=True)


# Error Response Models

class ErrorDetail(BaseModel):
    """Error detail model"""
    message: str
    field: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    details: Optional[List[ErrorDetail]] = None

    model_config = ConfigDict(from_attributes=True)
