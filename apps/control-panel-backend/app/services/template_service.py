"""
GT 2.0 Template Service
Handles applying tenant templates to existing tenants
"""
import logging
import os
import uuid
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.models.tenant_template import TenantTemplate
from app.models.tenant import Tenant
from app.models.tenant_model_config import TenantModelConfig

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for applying tenant templates"""

    def __init__(self):
        tenant_password = os.environ["TENANT_POSTGRES_PASSWORD"]
        self.tenant_db_url = f"postgresql://gt2_tenant_user:{tenant_password}@gentwo-tenant-postgres-primary:5432/gt2_tenants"

    async def apply_template(
        self,
        template_id: int,
        tenant_id: int,
        control_panel_db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Apply a template to an existing tenant

        Args:
            template_id: ID of template to apply
            tenant_id: ID of tenant to apply to
            control_panel_db: Control panel database session

        Returns:
            Dict with applied resources summary
        """
        try:
            template = await control_panel_db.get(TenantTemplate, template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")

            tenant = await control_panel_db.get(Tenant, tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            logger.info(f"Applying template '{template.name}' to tenant '{tenant.domain}'")

            template_data = template.template_data
            results = {
                "models_added": 0,
                "agents_added": 0,
                "datasets_added": 0
            }

            results["models_added"] = await self._apply_model_configs(
                template_data.get("model_configs", []),
                tenant_id,
                control_panel_db
            )

            tenant_schema = f"tenant_{tenant.domain.replace('-', '_').replace('.', '_')}"

            results["agents_added"] = await self._apply_agents(
                template_data.get("agents", []),
                tenant_schema
            )

            results["datasets_added"] = await self._apply_datasets(
                template_data.get("datasets", []),
                tenant_schema
            )

            logger.info(f"Template applied successfully: {results}")
            return results

        except Exception as e:
            logger.error(f"Failed to apply template: {e}")
            raise

    async def _apply_model_configs(
        self,
        model_configs: List[Dict],
        tenant_id: int,
        db: AsyncSession
    ) -> int:
        """Apply model configurations to control panel DB"""
        count = 0

        for config in model_configs:
            stmt = insert(TenantModelConfig).values(
                tenant_id=tenant_id,
                model_id=config["model_id"],
                is_enabled=config.get("is_enabled", True),
                rate_limits=config.get("rate_limits", {}),
                usage_constraints=config.get("usage_constraints", {}),
                priority=config.get("priority", 5),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ).on_conflict_do_update(
                index_elements=['tenant_id', 'model_id'],
                set_={
                    'is_enabled': config.get("is_enabled", True),
                    'rate_limits': config.get("rate_limits", {}),
                    'updated_at': datetime.utcnow()
                }
            )

            await db.execute(stmt)
            count += 1

        await db.commit()
        logger.info(f"Applied {count} model configs")
        return count

    async def _apply_agents(
        self,
        agents: List[Dict],
        tenant_schema: str
    ) -> int:
        """Apply agents to tenant DB"""
        from asyncpg import connect

        count = 0
        conn = await connect(self.tenant_db_url)

        try:
            for agent in agents:
                result = await conn.fetchrow(f"""
                    SELECT id FROM {tenant_schema}.tenants LIMIT 1
                """)
                tenant_id = result['id'] if result else None

                result = await conn.fetchrow(f"""
                    SELECT id FROM {tenant_schema}.users LIMIT 1
                """)
                created_by = result['id'] if result else None

                if not tenant_id or not created_by:
                    logger.warning(f"No tenant or user found in {tenant_schema}, skipping agents")
                    break

                agent_id = str(uuid.uuid4())

                await conn.execute(f"""
                    INSERT INTO {tenant_schema}.agents (
                        id, name, description, system_prompt, tenant_id, created_by,
                        model, temperature, max_tokens, visibility, configuration,
                        is_active, access_group, agent_type, disclaimer, easy_prompts,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO NOTHING
                """,
                    agent_id,
                    agent.get("name"),
                    agent.get("description"),
                    agent.get("system_prompt"),
                    tenant_id,
                    created_by,
                    agent.get("model"),
                    agent.get("temperature"),
                    agent.get("max_tokens"),
                    agent.get("visibility", "individual"),
                    agent.get("configuration", {}),
                    True,
                    "individual",
                    agent.get("agent_type", "conversational"),
                    agent.get("disclaimer"),
                    agent.get("easy_prompts", [])
                )
                count += 1

            logger.info(f"Applied {count} agents to {tenant_schema}")

        finally:
            await conn.close()

        return count

    async def _apply_datasets(
        self,
        datasets: List[Dict],
        tenant_schema: str
    ) -> int:
        """Apply datasets to tenant DB"""
        from asyncpg import connect

        count = 0
        conn = await connect(self.tenant_db_url)

        try:
            for dataset in datasets:
                result = await conn.fetchrow(f"""
                    SELECT id FROM {tenant_schema}.tenants LIMIT 1
                """)
                tenant_id = result['id'] if result else None

                result = await conn.fetchrow(f"""
                    SELECT id FROM {tenant_schema}.users LIMIT 1
                """)
                created_by = result['id'] if result else None

                if not tenant_id or not created_by:
                    logger.warning(f"No tenant or user found in {tenant_schema}, skipping datasets")
                    break

                dataset_id = str(uuid.uuid4())
                collection_name = f"dataset_{dataset_id.replace('-', '_')}"

                await conn.execute(f"""
                    INSERT INTO {tenant_schema}.datasets (
                        id, name, description, tenant_id, created_by, collection_name,
                        document_count, total_size_bytes, embedding_model, visibility,
                        metadata, is_active, access_group, search_method,
                        specialized_language, chunk_size, chunk_overlap,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, 0, 0, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO NOTHING
                """,
                    dataset_id,
                    dataset.get("name"),
                    dataset.get("description"),
                    tenant_id,
                    created_by,
                    collection_name,
                    dataset.get("embedding_model", "BAAI/bge-m3"),
                    dataset.get("visibility", "individual"),
                    dataset.get("metadata", {}),
                    True,
                    "individual",
                    dataset.get("search_method", "hybrid"),
                    dataset.get("specialized_language", False),
                    dataset.get("chunk_size", 512),
                    dataset.get("chunk_overlap", 128)
                )
                count += 1

            logger.info(f"Applied {count} datasets to {tenant_schema}")

        finally:
            await conn.close()

        return count

    async def export_tenant_as_template(
        self,
        tenant_id: int,
        template_name: str,
        template_description: str,
        control_panel_db: AsyncSession
    ) -> TenantTemplate:
        """Export existing tenant configuration as a new template"""
        try:
            tenant = await control_panel_db.get(Tenant, tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            logger.info(f"Exporting tenant '{tenant.domain}' as template '{template_name}'")

            result = await control_panel_db.execute(
                select(TenantModelConfig).where(TenantModelConfig.tenant_id == tenant_id)
            )
            model_configs = result.scalars().all()

            model_config_data = [
                {
                    "model_id": mc.model_id,
                    "is_enabled": mc.is_enabled,
                    "rate_limits": mc.rate_limits,
                    "usage_constraints": mc.usage_constraints,
                    "priority": mc.priority
                }
                for mc in model_configs
            ]

            tenant_schema = f"tenant_{tenant.domain.replace('-', '_').replace('.', '_')}"

            from asyncpg import connect
            conn = await connect(self.tenant_db_url)

            try:
                query = f"""
                    SELECT name, description, system_prompt, model, temperature, max_tokens,
                           visibility, configuration, agent_type, disclaimer, easy_prompts
                    FROM {tenant_schema}.agents
                    WHERE is_active = true
                """
                logger.info(f"Executing agents query: {query}")
                agents_data = await conn.fetch(query)
                logger.info(f"Found {len(agents_data)} agents")

                agents = [dict(row) for row in agents_data]

                datasets_data = await conn.fetch(f"""
                    SELECT name, description, embedding_model, visibility, metadata,
                           search_method, specialized_language, chunk_size, chunk_overlap
                    FROM {tenant_schema}.datasets
                    WHERE is_active = true
                    LIMIT 10
                """)

                datasets = [dict(row) for row in datasets_data]

            finally:
                await conn.close()

            template_data = {
                "model_configs": model_config_data,
                "agents": agents,
                "datasets": datasets
            }

            new_template = TenantTemplate(
                name=template_name,
                description=template_description,
                template_data=template_data,
                is_default=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            control_panel_db.add(new_template)
            await control_panel_db.commit()
            await control_panel_db.refresh(new_template)

            logger.info(f"Template '{template_name}' created successfully with ID {new_template.id}")
            return new_template

        except Exception as e:
            logger.error(f"Failed to export tenant as template: {e}")
            await control_panel_db.rollback()
            raise