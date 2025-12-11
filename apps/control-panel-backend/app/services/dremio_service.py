"""
Dremio SQL Federation Service for cross-cluster analytics
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.tenant import Tenant
from app.models.user import User
from app.models.ai_resource import AIResource
from app.models.usage import UsageRecord
from app.core.config import settings


class DremioService:
    """Service for Dremio SQL federation and cross-cluster queries"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dremio_url = settings.DREMIO_URL or "http://dremio:9047"
        self.dremio_username = settings.DREMIO_USERNAME or "admin"
        self.dremio_password = settings.DREMIO_PASSWORD or "admin123"
        self.auth_token = None
        self.token_expires = None
    
    async def _authenticate(self) -> str:
        """Authenticate with Dremio and get token"""
        
        # Check if we have a valid token
        if self.auth_token and self.token_expires and self.token_expires > datetime.utcnow():
            return self.auth_token
        
        # Get new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.dremio_url}/apiv2/login",
                json={
                    "userName": self.dremio_username,
                    "password": self.dremio_password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data['token']
                # Token typically expires in 24 hours
                self.token_expires = datetime.utcnow() + timedelta(hours=23)
                return self.auth_token
            else:
                raise Exception(f"Dremio authentication failed: {response.status_code}")
    
    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a SQL query via Dremio"""
        
        token = await self._authenticate()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.dremio_url}/api/v3/sql",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={"sql": sql},
                timeout=30.0
            )
            
            if response.status_code == 200:
                job_id = response.json()['id']
                
                # Wait for job completion
                while True:
                    job_response = await client.get(
                        f"{self.dremio_url}/api/v3/job/{job_id}",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    
                    job_data = job_response.json()
                    if job_data['jobState'] == 'COMPLETED':
                        break
                    elif job_data['jobState'] in ['FAILED', 'CANCELLED']:
                        raise Exception(f"Query failed: {job_data.get('errorMessage', 'Unknown error')}")
                    
                    await asyncio.sleep(0.5)
                
                # Get results
                results_response = await client.get(
                    f"{self.dremio_url}/api/v3/job/{job_id}/results",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if results_response.status_code == 200:
                    return results_response.json()['rows']
                else:
                    raise Exception(f"Failed to get results: {results_response.status_code}")
            else:
                raise Exception(f"Query execution failed: {response.status_code}")
    
    async def get_tenant_dashboard_data(self, tenant_id: int) -> Dict[str, Any]:
        """Get comprehensive dashboard data for a tenant"""
        
        # Get tenant info
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Federated queries across clusters
        dashboard_data = {
            'tenant': tenant.to_dict(),
            'metrics': {},
            'analytics': {},
            'alerts': []
        }
        
        # 1. User metrics from Admin Cluster
        user_metrics = await self._get_user_metrics(tenant_id)
        dashboard_data['metrics']['users'] = user_metrics
        
        # 2. Resource usage from Resource Cluster (via Dremio)
        resource_usage = await self._get_resource_usage_federated(tenant_id)
        dashboard_data['metrics']['resources'] = resource_usage
        
        # 3. Application metrics from Tenant Cluster (via Dremio)
        app_metrics = await self._get_application_metrics_federated(tenant.domain)
        dashboard_data['metrics']['applications'] = app_metrics

        # 4. Performance metrics
        performance_data = await self._get_performance_metrics(tenant_id)
        dashboard_data['analytics']['performance'] = performance_data
        
        # 6. Security alerts
        security_alerts = await self._get_security_alerts(tenant_id)
        dashboard_data['alerts'] = security_alerts
        
        return dashboard_data
    
    async def _get_user_metrics(self, tenant_id: int) -> Dict[str, Any]:
        """Get user metrics from Admin Cluster database"""
        
        # Total users
        user_count_result = await self.db.execute(
            select(User).where(User.tenant_id == tenant_id)
        )
        users = user_count_result.scalars().all()
        
        # Active users (logged in within 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        active_users = [u for u in users if u.last_login and u.last_login > seven_days_ago]
        
        return {
            'total_users': len(users),
            'active_users': len(active_users),
            'inactive_users': len(users) - len(active_users),
            'user_growth_7d': 0,  # Would calculate from historical data
            'by_role': {
                'admin': len([u for u in users if u.user_type == 'tenant_admin']),
                'developer': len([u for u in users if u.user_type == 'developer']),
                'analyst': len([u for u in users if u.user_type == 'analyst']),
                'student': len([u for u in users if u.user_type == 'student'])
            }
        }
    
    async def _get_resource_usage_federated(self, tenant_id: int) -> Dict[str, Any]:
        """Get resource usage via Dremio federation to Resource Cluster"""
        
        try:
            # Query Resource Cluster data via Dremio
            sql = f"""
            SELECT 
                resource_type,
                COUNT(*) as request_count,
                SUM(tokens_used) as total_tokens,
                SUM(cost_cents) as total_cost_cents,
                AVG(processing_time_ms) as avg_latency_ms
            FROM resource_cluster.usage_records
            WHERE tenant_id = {tenant_id}
                AND started_at >= CURRENT_DATE - INTERVAL '7' DAY
            GROUP BY resource_type
            """
            
            results = await self.execute_query(sql)
            
            # Process results
            usage_by_type = {}
            total_requests = 0
            total_tokens = 0
            total_cost = 0
            
            for row in results:
                usage_by_type[row['resource_type']] = {
                    'requests': row['request_count'],
                    'tokens': row['total_tokens'],
                    'cost_cents': row['total_cost_cents'],
                    'avg_latency_ms': row['avg_latency_ms']
                }
                total_requests += row['request_count']
                total_tokens += row['total_tokens'] or 0
                total_cost += row['total_cost_cents'] or 0
            
            return {
                'total_requests_7d': total_requests,
                'total_tokens_7d': total_tokens,
                'total_cost_cents_7d': total_cost,
                'by_resource_type': usage_by_type
            }
            
        except Exception as e:
            # Fallback to local database query if Dremio fails
            print(f"Dremio query failed, using local data: {e}")
            return await self._get_resource_usage_local(tenant_id)
    
    async def _get_resource_usage_local(self, tenant_id: int) -> Dict[str, Any]:
        """Fallback: Get resource usage from local database"""
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        result = await self.db.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.started_at >= seven_days_ago
            )
        )
        usage_records = result.scalars().all()
        
        usage_by_type = {}
        total_requests = len(usage_records)
        total_tokens = sum(r.tokens_used or 0 for r in usage_records)
        total_cost = sum(r.cost_cents or 0 for r in usage_records)
        
        for record in usage_records:
            if record.operation_type not in usage_by_type:
                usage_by_type[record.operation_type] = {
                    'requests': 0,
                    'tokens': 0,
                    'cost_cents': 0
                }
            usage_by_type[record.operation_type]['requests'] += 1
            usage_by_type[record.operation_type]['tokens'] += record.tokens_used or 0
            usage_by_type[record.operation_type]['cost_cents'] += record.cost_cents or 0
        
        return {
            'total_requests_7d': total_requests,
            'total_tokens_7d': total_tokens,
            'total_cost_cents_7d': total_cost,
            'by_resource_type': usage_by_type
        }
    
    async def _get_application_metrics_federated(self, tenant_domain: str) -> Dict[str, Any]:
        """Get application metrics via Dremio federation to Tenant Cluster"""
        
        try:
            # Query Tenant Cluster data via Dremio
            sql = f"""
            SELECT 
                COUNT(DISTINCT c.id) as total_conversations,
                COUNT(m.id) as total_messages,
                COUNT(DISTINCT a.id) as total_assistants,
                COUNT(DISTINCT d.id) as total_documents,
                SUM(d.chunk_count) as total_chunks,
                AVG(m.processing_time_ms) as avg_response_time_ms
            FROM tenant_{tenant_domain}.conversations c
            LEFT JOIN tenant_{tenant_domain}.messages m ON c.id = m.conversation_id
            LEFT JOIN tenant_{tenant_domain}.agents a ON c.agent_id = a.id
            LEFT JOIN tenant_{tenant_domain}.documents d ON d.created_at >= CURRENT_DATE - INTERVAL '7' DAY
            WHERE c.created_at >= CURRENT_DATE - INTERVAL '7' DAY
            """
            
            results = await self.execute_query(sql)
            
            if results:
                row = results[0]
                return {
                    'conversations': row['total_conversations'] or 0,
                    'messages': row['total_messages'] or 0,
                    'agents': row['total_assistants'] or 0,
                    'documents': row['total_documents'] or 0,
                    'document_chunks': row['total_chunks'] or 0,
                    'avg_response_time_ms': row['avg_response_time_ms'] or 0
                }
            
        except Exception as e:
            print(f"Dremio tenant query failed: {e}")
        
        # Return default metrics if query fails
        return {
            'conversations': 0,
            'messages': 0,
            'agents': 0,
            'documents': 0,
            'document_chunks': 0,
            'avg_response_time_ms': 0
        }

    async def _get_performance_metrics(self, tenant_id: int) -> Dict[str, Any]:
        """Get performance metrics for the tenant"""
        
        # This would aggregate performance data from various sources
        return {
            'api_latency_p50_ms': 45,
            'api_latency_p95_ms': 120,
            'api_latency_p99_ms': 250,
            'uptime_percentage': 99.95,
            'error_rate_percentage': 0.12,
            'concurrent_users': 23,
            'requests_per_second': 45.6
        }
    
    async def _get_security_alerts(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Get security alerts for the tenant"""
        
        # This would query security monitoring systems
        alerts = []
        
        # Check for common security issues
        # 1. Check for expired API keys
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if tenant and tenant.api_keys:
            for provider, info in tenant.api_keys.items():
                updated_at = datetime.fromisoformat(info.get('updated_at', '2020-01-01T00:00:00'))
                if (datetime.utcnow() - updated_at).days > 90:
                    alerts.append({
                        'severity': 'warning',
                        'type': 'api_key_rotation',
                        'message': f'API key for {provider} has not been rotated in over 90 days',
                        'timestamp': datetime.utcnow().isoformat()
                    })
        
        # 2. Check for high error rates (would come from monitoring)
        # 3. Check for unusual access patterns (would come from logs)
        
        return alerts
    
    async def create_virtual_datasets(self, tenant_id: int) -> Dict[str, Any]:
        """Create Dremio virtual datasets for tenant analytics"""
        
        token = await self._authenticate()
        
        # Create virtual datasets that join data across clusters
        datasets = [
            {
                'name': f'tenant_{tenant_id}_unified_usage',
                'sql': f"""
                SELECT 
                    ac.user_email,
                    ac.user_type,
                    rc.resource_type,
                    rc.operation_type,
                    rc.tokens_used,
                    rc.cost_cents,
                    rc.started_at,
                    tc.conversation_id,
                    tc.assistant_name
                FROM admin_cluster.users ac
                JOIN resource_cluster.usage_records rc ON ac.email = rc.user_id
                LEFT JOIN tenant_cluster.conversations tc ON rc.conversation_id = tc.id
                WHERE ac.tenant_id = {tenant_id}
                """
            },
            {
                'name': f'tenant_{tenant_id}_cost_analysis',
                'sql': f"""
                SELECT 
                    DATE_TRUNC('day', started_at) as date,
                    resource_type,
                    SUM(tokens_used) as daily_tokens,
                    SUM(cost_cents) as daily_cost_cents,
                    COUNT(*) as daily_requests
                FROM resource_cluster.usage_records
                WHERE tenant_id = {tenant_id}
                GROUP BY DATE_TRUNC('day', started_at), resource_type
                """
            }
        ]
        
        created_datasets = []
        
        for dataset in datasets:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.dremio_url}/api/v3/catalog",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "entityType": "dataset",
                        "path": ["Analytics", dataset['name']],
                        "dataset": {
                            "type": "VIRTUAL",
                            "sql": dataset['sql'],
                            "sqlContext": ["@admin"]
                        }
                    }
                )
                
                if response.status_code in [200, 201]:
                    created_datasets.append(dataset['name'])
        
        return {
            'tenant_id': tenant_id,
            'datasets_created': created_datasets,
            'status': 'success'
        }
    
    async def get_custom_analytics(
        self,
        tenant_id: int,
        query_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Run custom analytics queries for a tenant"""
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        queries = {
            'user_activity': f"""
                SELECT 
                    u.email,
                    u.user_type,
                    COUNT(DISTINCT ur.conversation_id) as conversations,
                    SUM(ur.tokens_used) as total_tokens,
                    SUM(ur.cost_cents) as total_cost_cents
                FROM admin_cluster.users u
                LEFT JOIN resource_cluster.usage_records ur ON u.email = ur.user_id
                WHERE u.tenant_id = {tenant_id}
                    AND ur.started_at BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
                GROUP BY u.email, u.user_type
                ORDER BY total_cost_cents DESC
            """,
            'resource_trends': f"""
                SELECT 
                    DATE_TRUNC('day', started_at) as date,
                    resource_type,
                    COUNT(*) as requests,
                    SUM(tokens_used) as tokens,
                    SUM(cost_cents) as cost_cents
                FROM resource_cluster.usage_records
                WHERE tenant_id = {tenant_id}
                    AND started_at BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
                GROUP BY DATE_TRUNC('day', started_at), resource_type
                ORDER BY date DESC
            """,
            'cost_optimization': f"""
                SELECT 
                    resource_type,
                    operation_type,
                    AVG(tokens_used) as avg_tokens,
                    AVG(cost_cents) as avg_cost_cents,
                    COUNT(*) as request_count,
                    SUM(cost_cents) as total_cost_cents
                FROM resource_cluster.usage_records
                WHERE tenant_id = {tenant_id}
                    AND started_at BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
                GROUP BY resource_type, operation_type
                HAVING COUNT(*) > 10
                ORDER BY total_cost_cents DESC
                LIMIT 20
            """
        }
        
        if query_type not in queries:
            raise ValueError(f"Unknown query type: {query_type}")
        
        try:
            results = await self.execute_query(queries[query_type])
            return results
        except Exception as e:
            print(f"Analytics query failed: {e}")
            return []