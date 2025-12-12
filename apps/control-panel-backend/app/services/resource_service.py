"""
Comprehensive Resource management service for all GT 2.0 resource families

Supports business logic and validation for:
- AI/ML Resources (LLMs, embeddings, image generation, function calling)
- RAG Engine Resources (vector databases, document processing, retrieval systems)
- Agentic Workflow Resources (multi-step AI workflows, agent frameworks)
- App Integration Resources (external tools, APIs, webhooks)
- External Web Services (Canvas LMS, CTFd, Guacamole, iframe-embedded services)
- AI Literacy & Cognitive Skills (educational games, puzzles, learning content)
"""
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import logging
import json
import base64
from cryptography.fernet import Fernet
from app.core.config import get_settings

from app.models.ai_resource import AIResource
from app.models.tenant import Tenant, TenantResource
from app.models.usage import UsageRecord
from app.models.user_data import UserResourceData, UserPreferences, UserProgress, SessionData
from app.models.resource_schemas import validate_resource_config, get_config_schema
from app.services.groq_service import groq_service
# Use existing encryption implementation from GT 2.0
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)


class ResourceService:
    """Comprehensive service for managing all GT 2.0 resource families with HA and business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_resource(self, resource_data: Dict[str, Any]) -> AIResource:
        """Create a new resource with comprehensive validation for all resource families"""
        # Validate required fields (model_name is now optional for non-AI resources)
        required_fields = ["name", "resource_type", "provider"]
        for field in required_fields:
            if field not in resource_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate resource type
        valid_resource_types = [
            "ai_ml", "rag_engine", "agentic_workflow", 
            "app_integration", "external_service", "ai_literacy"
        ]
        if resource_data["resource_type"] not in valid_resource_types:
            raise ValueError(f"Invalid resource_type. Must be one of: {valid_resource_types}")
        
        # Validate and apply configuration based on resource type and subtype
        resource_subtype = resource_data.get("resource_subtype")
        if "configuration" in resource_data:
            try:
                validated_config = validate_resource_config(
                    resource_data["resource_type"],
                    resource_subtype or "default",
                    resource_data["configuration"]
                )
                resource_data["configuration"] = validated_config
            except Exception as e:
                logger.warning(f"Configuration validation failed: {e}. Using provided config as-is.")
        
        # Apply resource-family-specific defaults
        await self._apply_resource_defaults(resource_data)
        
        # Validate specific requirements by resource family
        await self._validate_resource_requirements(resource_data)
        
        # Create resource
        resource = AIResource(**resource_data)
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        
        logger.info(f"Created {resource.resource_type} resource: {resource.name} ({resource.provider})")
        return resource
    
    async def get_resource(self, resource_id: int) -> Optional[AIResource]:
        """Get resource by ID with relationships"""
        result = await self.db.execute(
            select(AIResource)
            .options(selectinload(AIResource.tenant_resources))
            .where(AIResource.id == resource_id)
        )
        return result.scalar_one_or_none()
    
    async def get_resource_by_uuid(self, resource_uuid: str) -> Optional[AIResource]:
        """Get resource by UUID"""
        result = await self.db.execute(
            select(AIResource)
            .where(AIResource.uuid == resource_uuid)
        )
        return result.scalar_one_or_none()
    
    async def list_resources(
        self, 
        provider: Optional[str] = None,
        resource_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        health_status: Optional[str] = None
    ) -> List[AIResource]:
        """List resources with filtering"""
        query = select(AIResource).options(selectinload(AIResource.tenant_resources))
        
        conditions = []
        if provider:
            conditions.append(AIResource.provider == provider)
        if resource_type:
            conditions.append(AIResource.resource_type == resource_type)
        if is_active is not None:
            conditions.append(AIResource.is_active == is_active)
        if health_status:
            conditions.append(AIResource.health_status == health_status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query.order_by(AIResource.priority.desc(), AIResource.created_at))
        return result.scalars().all()
    
    async def update_resource(self, resource_id: int, updates: Dict[str, Any]) -> Optional[AIResource]:
        """Update resource with validation"""
        resource = await self.get_resource(resource_id)
        if not resource:
            return None
        
        # Update fields
        for key, value in updates.items():
            if hasattr(resource, key):
                setattr(resource, key, value)
        
        resource.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resource)
        
        logger.info(f"Updated resource {resource_id}: {list(updates.keys())}")
        return resource
    
    async def delete_resource(self, resource_id: int) -> bool:
        """Delete resource (soft delete by deactivating)"""
        resource = await self.get_resource(resource_id)
        if not resource:
            return False
        
        # Check if resource is in use by tenants
        result = await self.db.execute(
            select(TenantResource)
            .where(and_(
                TenantResource.resource_id == resource_id,
                TenantResource.is_enabled == True
            ))
        )
        active_assignments = result.scalars().all()
        
        if active_assignments:
            raise ValueError(f"Cannot delete resource in use by {len(active_assignments)} tenants")
        
        # Soft delete
        resource.is_active = False
        resource.health_status = "deleted"
        resource.updated_at = datetime.utcnow()
        
        await self.db.commit()
        logger.info(f"Deleted resource {resource_id}")
        return True
    
    async def assign_resource_to_tenant(
        self, 
        resource_id: int, 
        tenant_id: int,
        usage_limits: Optional[Dict[str, Any]] = None
    ) -> TenantResource:
        """Assign resource to tenant with usage limits"""
        # Validate resource exists and is active
        resource = await self.get_resource(resource_id)
        if not resource or not resource.is_active:
            raise ValueError("Resource not found or inactive")
        
        # Validate tenant exists
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Check if assignment already exists
        existing_result = await self.db.execute(
            select(TenantResource)
            .where(and_(
                TenantResource.tenant_id == tenant_id,
                TenantResource.resource_id == resource_id
            ))
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Update existing assignment
            existing.is_enabled = True
            existing.usage_limits = usage_limits or {}
            existing.updated_at = datetime.utcnow()
            await self.db.commit()
            return existing
        
        # Create new assignment
        assignment = TenantResource(
            tenant_id=tenant_id,
            resource_id=resource_id,
            usage_limits=usage_limits or {},
            is_enabled=True
        )
        
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        
        logger.info(f"Assigned resource {resource_id} to tenant {tenant_id}")
        return assignment
    
    async def unassign_resource_from_tenant(self, resource_id: int, tenant_id: int) -> bool:
        """Remove resource assignment from tenant"""
        result = await self.db.execute(
            select(TenantResource)
            .where(and_(
                TenantResource.tenant_id == tenant_id,
                TenantResource.resource_id == resource_id
            ))
        )
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            return False
        
        assignment.is_enabled = False
        assignment.updated_at = datetime.utcnow()
        await self.db.commit()
        
        logger.info(f"Unassigned resource {resource_id} from tenant {tenant_id}")
        return True
    
    async def get_tenant_resources(self, tenant_id: int) -> List[AIResource]:
        """Get all resources assigned to a tenant"""
        result = await self.db.execute(
            select(AIResource)
            .join(TenantResource)
            .where(and_(
                TenantResource.tenant_id == tenant_id,
                TenantResource.is_enabled == True,
                AIResource.is_active == True
            ))
            .order_by(AIResource.priority.desc())
        )
        return result.scalars().all()
    
    async def health_check_all_resources(self) -> Dict[str, Any]:
        """Perform health checks on all active resources"""
        resources = await self.list_resources(is_active=True)
        results = {
            "total_resources": len(resources),
            "healthy": 0,
            "unhealthy": 0,
            "unknown": 0,
            "details": []
        }
        
        # Run health checks concurrently
        tasks = []
        for resource in resources:
            if resource.provider == "groq" and resource.api_key_encrypted:
                # Decrypt API key for health check
                try:
                    # Decrypt API key using tenant encryption key
                    api_key = await self._decrypt_api_key(resource.api_key_encrypted, resource.tenant_id)
                    task = self._health_check_resource(resource, api_key)
                    tasks.append(task)
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for resource {resource.id}: {e}")
                    resource.update_health_status("unhealthy")
        
        if tasks:
            health_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(health_results):
                resource = resources[i]
                if isinstance(result, Exception):
                    logger.error(f"Health check failed for resource {resource.id}: {result}")
                    resource.update_health_status("unhealthy")
                else:
                    # result is already updated in _health_check_resource
                    pass
        
        # Count results
        for resource in resources:
            results["details"].append({
                "id": resource.id,
                "name": resource.name,
                "provider": resource.provider,
                "health_status": resource.health_status,
                "last_check": resource.last_health_check.isoformat() if resource.last_health_check else None
            })
            
            if resource.health_status == "healthy":
                results["healthy"] += 1
            elif resource.health_status == "unhealthy":
                results["unhealthy"] += 1
            else:
                results["unknown"] += 1
        
        await self.db.commit()  # Save health status updates
        return results
    
    async def _health_check_resource(self, resource: AIResource, api_key: str) -> bool:
        """Internal method to health check a single resource"""
        try:
            if resource.provider == "groq":
                return await groq_service.health_check_resource(resource, api_key)
            else:
                # For other providers, implement specific health checks
                logger.warning(f"No health check implementation for provider: {resource.provider}")
                resource.update_health_status("unknown")
                return False
        except Exception as e:
            logger.error(f"Health check failed for resource {resource.id}: {e}")
            resource.update_health_status("unhealthy")
            return False
    
    async def get_resource_usage_stats(
        self, 
        resource_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage statistics for a resource"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get usage records
        result = await self.db.execute(
            select(UsageRecord)
            .where(and_(
                UsageRecord.resource_id == resource_id,
                UsageRecord.created_at >= start_date,
                UsageRecord.created_at <= end_date
            ))
            .order_by(UsageRecord.created_at.desc())
        )
        usage_records = result.scalars().all()
        
        # Calculate statistics
        total_requests = len(usage_records)
        total_tokens = sum(record.tokens_used for record in usage_records)
        total_cost_cents = sum(record.cost_cents for record in usage_records)
        
        avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0
        avg_cost_per_request = total_cost_cents / total_requests if total_requests > 0 else 0
        
        # Group by day for trending
        daily_stats = {}
        for record in usage_records:
            date_key = record.created_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    "requests": 0,
                    "tokens": 0,
                    "cost_cents": 0
                }
            daily_stats[date_key]["requests"] += 1
            daily_stats[date_key]["tokens"] += record.tokens_used
            daily_stats[date_key]["cost_cents"] += record.cost_cents
        
        return {
            "resource_id": resource_id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "total_cost_dollars": total_cost_cents / 100,
                "avg_tokens_per_request": round(avg_tokens_per_request, 2),
                "avg_cost_per_request_cents": round(avg_cost_per_request, 2)
            },
            "daily_stats": daily_stats
        }
    
    async def get_tenant_usage_stats(
        self, 
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage statistics for all resources used by a tenant"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get usage records with resource information
        result = await self.db.execute(
            select(UsageRecord, AIResource)
            .join(AIResource, UsageRecord.resource_id == AIResource.id)
            .where(and_(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.created_at >= start_date,
                UsageRecord.created_at <= end_date
            ))
            .order_by(UsageRecord.created_at.desc())
        )
        records_with_resources = result.all()
        
        # Calculate statistics by resource
        resource_stats = {}
        total_cost_cents = 0
        total_requests = 0
        
        for usage_record, ai_resource in records_with_resources:
            resource_id = ai_resource.id
            if resource_id not in resource_stats:
                resource_stats[resource_id] = {
                    "resource_name": ai_resource.name,
                    "provider": ai_resource.provider,
                    "model_name": ai_resource.model_name,
                    "requests": 0,
                    "tokens": 0,
                    "cost_cents": 0
                }
            
            resource_stats[resource_id]["requests"] += 1
            resource_stats[resource_id]["tokens"] += usage_record.tokens_used
            resource_stats[resource_id]["cost_cents"] += usage_record.cost_cents
            
            total_cost_cents += usage_record.cost_cents
            total_requests += 1
        
        return {
            "tenant_id": tenant_id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_requests": total_requests,
                "total_cost_dollars": total_cost_cents / 100,
                "resources_used": len(resource_stats)
            },
            "by_resource": resource_stats
        }
    
    # Resource-family-specific methods
    async def _apply_resource_defaults(self, resource_data: Dict[str, Any]) -> None:
        """Apply defaults based on resource family and provider"""
        resource_type = resource_data["resource_type"]
        provider = resource_data["provider"]
        
        if resource_type == "ai_ml" and provider == "groq":
            # Apply Groq-specific defaults for AI/ML resources
            groq_defaults = AIResource.get_groq_defaults()
            for key, value in groq_defaults.items():
                if key not in resource_data:
                    resource_data[key] = value
        
        elif resource_type == "external_service":
            # Apply defaults for external web services
            if "sandbox_config" not in resource_data:
                resource_data["sandbox_config"] = {
                    "permissions": ["allow-same-origin", "allow-scripts", "allow-forms"],
                    "csp_policy": "default-src 'self'",
                    "secure": True
                }
            
            if "personalization_mode" not in resource_data:
                resource_data["personalization_mode"] = "user_scoped"  # Most external services are user-specific
        
        elif resource_type == "ai_literacy":
            # Apply defaults for AI literacy resources
            if "personalization_mode" not in resource_data:
                resource_data["personalization_mode"] = "user_scoped"  # Track individual progress
            
            if "configuration" not in resource_data:
                resource_data["configuration"] = {
                    "difficulty_adaptive": True,
                    "progress_tracking": True,
                    "explanation_mode": True
                }
        
        elif resource_type == "rag_engine":
            # Apply defaults for RAG engines
            if "personalization_mode" not in resource_data:
                resource_data["personalization_mode"] = "shared"  # RAG engines typically shared
            
            if "configuration" not in resource_data:
                resource_data["configuration"] = {
                    "chunk_size": 512,
                    "similarity_threshold": 0.7,
                    "max_results": 10
                }
        
        elif resource_type == "agentic_workflow":
            # Apply defaults for agentic workflows
            if "personalization_mode" not in resource_data:
                resource_data["personalization_mode"] = "user_scoped"  # Workflows are typically user-specific
            
            if "configuration" not in resource_data:
                resource_data["configuration"] = {
                    "max_iterations": 10,
                    "human_in_loop": True,
                    "retry_on_failure": True
                }
        
        elif resource_type == "app_integration":
            # Apply defaults for app integrations
            if "personalization_mode" not in resource_data:
                resource_data["personalization_mode"] = "shared"  # Most integrations are shared
            
            if "configuration" not in resource_data:
                resource_data["configuration"] = {
                    "timeout_seconds": 30,
                    "retry_attempts": 3,
                    "auth_method": "api_key"
                }
        
        # Set default personalization mode if not specified
        if "personalization_mode" not in resource_data:
            resource_data["personalization_mode"] = "shared"
    
    async def _validate_resource_requirements(self, resource_data: Dict[str, Any]) -> None:
        """Validate resource-specific requirements"""
        resource_type = resource_data["resource_type"]
        resource_subtype = resource_data.get("resource_subtype")
        
        if resource_type == "ai_ml":
            # AI/ML resources must have model_name
            if not resource_data.get("model_name"):
                raise ValueError("AI/ML resources must specify model_name")
            
            # Validate AI/ML subtypes
            valid_ai_subtypes = ["llm", "embedding", "image_generation", "function_calling"]
            if resource_subtype and resource_subtype not in valid_ai_subtypes:
                raise ValueError(f"Invalid AI/ML subtype. Must be one of: {valid_ai_subtypes}")
        
        elif resource_type == "external_service":
            # External services must have iframe_url or primary_endpoint
            if not resource_data.get("iframe_url") and not resource_data.get("primary_endpoint"):
                raise ValueError("External service resources must specify iframe_url or primary_endpoint")
            
            # Validate external service subtypes
            valid_external_subtypes = ["lms", "cyber_range", "iframe", "custom"]
            if resource_subtype and resource_subtype not in valid_external_subtypes:
                raise ValueError(f"Invalid external service subtype. Must be one of: {valid_external_subtypes}")
        
        elif resource_type == "ai_literacy":
            # AI literacy resources must have appropriate subtype
            valid_literacy_subtypes = ["strategic_game", "logic_puzzle", "philosophical_dilemma", "educational_content"]
            if not resource_subtype or resource_subtype not in valid_literacy_subtypes:
                raise ValueError(f"AI literacy resources must specify valid subtype: {valid_literacy_subtypes}")
        
        elif resource_type == "rag_engine":
            # RAG engines must have appropriate configuration
            valid_rag_subtypes = ["vector_database", "document_processor", "retrieval_system"]
            if resource_subtype and resource_subtype not in valid_rag_subtypes:
                raise ValueError(f"Invalid RAG engine subtype. Must be one of: {valid_rag_subtypes}")
        
        elif resource_type == "agentic_workflow":
            # Agentic workflows must have appropriate configuration
            valid_workflow_subtypes = ["workflow", "agent_framework", "multi_agent"]
            if resource_subtype and resource_subtype not in valid_workflow_subtypes:
                raise ValueError(f"Invalid agentic workflow subtype. Must be one of: {valid_workflow_subtypes}")
        
        elif resource_type == "app_integration":
            # App integrations must have endpoint or webhook configuration
            if not resource_data.get("primary_endpoint") and not resource_data.get("configuration", {}).get("webhook_enabled"):
                raise ValueError("App integration resources must specify primary_endpoint or enable webhooks")
            
            valid_integration_subtypes = ["api", "webhook", "oauth_app", "custom"]
            if resource_subtype and resource_subtype not in valid_integration_subtypes:
                raise ValueError(f"Invalid app integration subtype. Must be one of: {valid_integration_subtypes}")
    
    # User data separation methods
    async def get_user_resource_data(
        self, 
        user_id: int, 
        resource_id: int, 
        data_type: str, 
        session_id: Optional[str] = None
    ) -> Optional[UserResourceData]:
        """Get user-specific data for a resource"""
        query = select(UserResourceData).where(and_(
            UserResourceData.user_id == user_id,
            UserResourceData.resource_id == resource_id,
            UserResourceData.data_type == data_type
        ))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def set_user_resource_data(
        self, 
        user_id: int, 
        tenant_id: int,
        resource_id: int, 
        data_type: str, 
        data_key: str,
        data_value: Dict[str, Any],
        session_id: Optional[str] = None,
        expires_minutes: Optional[int] = None
    ) -> UserResourceData:
        """Set user-specific data for a resource"""
        # Check if data already exists
        existing = await self.get_user_resource_data(user_id, resource_id, data_type)
        
        if existing:
            # Update existing data
            existing.data_key = data_key
            existing.data_value = data_value
            existing.accessed_at = datetime.utcnow()
            
            if expires_minutes:
                existing.expiry_date = datetime.utcnow() + timedelta(minutes=expires_minutes)
            
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new data
            expiry_date = None
            if expires_minutes:
                expiry_date = datetime.utcnow() + timedelta(minutes=expires_minutes)
            
            user_data = UserResourceData(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_id=resource_id,
                data_type=data_type,
                data_key=data_key,
                data_value=data_value,
                expiry_date=expiry_date
            )
            
            self.db.add(user_data)
            await self.db.commit()
            await self.db.refresh(user_data)
            
            logger.info(f"Created user data: user={user_id}, resource={resource_id}, type={data_type}")
            return user_data
    
    async def get_user_progress(self, user_id: int, resource_id: int) -> Optional[UserProgress]:
        """Get user progress for AI literacy resources"""
        result = await self.db.execute(
            select(UserProgress).where(and_(
                UserProgress.user_id == user_id,
                UserProgress.resource_id == resource_id
            ))
        )
        return result.scalar_one_or_none()
    
    async def update_user_progress(
        self, 
        user_id: int, 
        tenant_id: int,
        resource_id: int, 
        skill_area: str,
        progress_data: Dict[str, Any]
    ) -> UserProgress:
        """Update user progress for learning resources"""
        existing = await self.get_user_progress(user_id, resource_id)
        
        if existing:
            # Update existing progress
            for key, value in progress_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            
            existing.last_activity = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new progress record
            progress = UserProgress(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_id=resource_id,
                skill_area=skill_area,
                **progress_data
            )
            
            self.db.add(progress)
            await self.db.commit()
            await self.db.refresh(progress)
            
            logger.info(f"Created user progress: user={user_id}, resource={resource_id}, skill={skill_area}")
            return progress
    
    # Enhanced filtering and search
    async def list_resources_by_family(
        self, 
        resource_type: str,
        resource_subtype: Optional[str] = None,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        include_inactive: bool = False
    ) -> List[AIResource]:
        """List resources by resource family with optional filtering"""
        query = select(AIResource).options(selectinload(AIResource.tenant_resources))
        
        conditions = [AIResource.resource_type == resource_type]
        
        if resource_subtype:
            conditions.append(AIResource.resource_subtype == resource_subtype)
        
        if not include_inactive:
            conditions.append(AIResource.is_active == True)
        
        if tenant_id:
            # Filter to resources available to this tenant
            query = query.join(TenantResource).where(and_(
                TenantResource.tenant_id == tenant_id,
                TenantResource.is_enabled == True
            ))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(
            query.order_by(AIResource.priority.desc(), AIResource.created_at)
        )
        return result.scalars().all()
    
    async def get_resource_families_summary(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of all resource families"""
        base_query = select(
            AIResource.resource_type,
            AIResource.resource_subtype,
            func.count(AIResource.id).label('count'),
            func.count(func.nullif(AIResource.health_status == 'healthy', False)).label('healthy_count')
        ).group_by(AIResource.resource_type, AIResource.resource_subtype)
        
        if tenant_id:
            base_query = base_query.join(TenantResource).where(and_(
                TenantResource.tenant_id == tenant_id,
                TenantResource.is_enabled == True,
                AIResource.is_active == True
            ))
        else:
            base_query = base_query.where(AIResource.is_active == True)
        
        result = await self.db.execute(base_query)
        rows = result.all()
        
        # Organize by resource family
        families = {}
        for row in rows:
            family = row.resource_type
            if family not in families:
                families[family] = {
                    "total_resources": 0,
                    "healthy_resources": 0,
                    "subtypes": {}
                }
            
            subtype = row.resource_subtype or "default"
            families[family]["total_resources"] += row.count
            families[family]["healthy_resources"] += row.healthy_count or 0
            families[family]["subtypes"][subtype] = {
                "count": row.count,
                "healthy_count": row.healthy_count or 0
            }
        
        return families
    
    async def _decrypt_api_key(self, encrypted_api_key: str, tenant_id: str) -> str:
        """Decrypt API key using tenant-specific encryption key"""
        try:
            settings = get_settings()
            
            # Generate tenant-specific encryption key from settings secret
            tenant_key = base64.urlsafe_b64encode(
                f"{settings.secret_key}:{tenant_id}".encode()[:32].ljust(32, b'\0')
            )
            
            cipher = Fernet(tenant_key)
            
            # Decrypt the API key
            decrypted_bytes = cipher.decrypt(encrypted_api_key.encode())
            return decrypted_bytes.decode()
            
        except Exception as e:
            logger.error(f"Failed to decrypt API key for tenant {tenant_id}: {e}")
            raise ValueError(f"API key decryption failed: {e}")
    
    async def _encrypt_api_key(self, api_key: str, tenant_id: str) -> str:
        """Encrypt API key using tenant-specific encryption key"""
        try:
            settings = get_settings()
            
            # Generate tenant-specific encryption key from settings secret
            tenant_key = base64.urlsafe_b64encode(
                f"{settings.secret_key}:{tenant_id}".encode()[:32].ljust(32, b'\0')
            )
            
            cipher = Fernet(tenant_key)
            
            # Encrypt the API key
            encrypted_bytes = cipher.encrypt(api_key.encode())
            return encrypted_bytes.decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt API key for tenant {tenant_id}: {e}")
            raise ValueError(f"API key encryption failed: {e}")