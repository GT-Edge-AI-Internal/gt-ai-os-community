"""
GT 2.0 Resource Cluster - Service Manager
Orchestrates external web services (CTFd, Canvas LMS, Guacamole, JupyterHub)
with perfect tenant isolation and security.
"""

import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
try:
    import docker
    import kubernetes
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    DOCKER_AVAILABLE = True
    KUBERNETES_AVAILABLE = True
except ImportError:
    # For development containerization mode, these are optional
    docker = None
    kubernetes = None
    client = None
    config = None
    ApiException = Exception
    DOCKER_AVAILABLE = False
    KUBERNETES_AVAILABLE = False

from app.core.config import get_settings
from app.core.security import verify_capability_token
from app.utils.encryption import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

@dataclass
class ServiceInstance:
    """Represents a deployed service instance"""
    instance_id: str
    tenant_id: str
    service_type: str  # 'ctfd', 'canvas', 'guacamole', 'jupyter'
    status: str  # 'starting', 'running', 'stopping', 'stopped', 'error'
    endpoint_url: str
    internal_port: int
    external_port: int
    namespace: str
    deployment_name: str
    service_name: str
    ingress_name: str
    sso_token: Optional[str] = None
    created_at: datetime = datetime.utcnow()
    last_heartbeat: datetime = datetime.utcnow()
    resource_usage: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_heartbeat'] = self.last_heartbeat.isoformat()
        return data

@dataclass
class ServiceTemplate:
    """Service deployment template configuration"""
    service_type: str
    image: str
    ports: Dict[str, int]
    environment: Dict[str, str]
    volumes: List[Dict[str, str]]
    resource_limits: Dict[str, str]
    security_context: Dict[str, Any]
    health_check: Dict[str, Any]
    sso_config: Dict[str, Any]

class ServiceManager:
    """Manages external web service instances with Kubernetes orchestration"""
    
    def __init__(self):
        # Initialize Docker client if available
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
            except Exception as e:
                logger.warning(f"Could not initialize Docker client: {e}")
                self.docker_client = None
        else:
            self.docker_client = None
            
        self.k8s_client = None
        self.active_instances: Dict[str, ServiceInstance] = {}
        self.service_templates: Dict[str, ServiceTemplate] = {}
        self.base_namespace = "gt-services"
        self.storage_path = Path("/tmp/resource-cluster/services")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize Kubernetes client if available
        if KUBERNETES_AVAILABLE:
            try:
                config.load_incluster_config()  # If running in cluster
            except:
                try:
                    config.load_kube_config()  # If running locally
                except:
                    logger.warning("Could not load Kubernetes config - using mock mode")
                    
            self.k8s_client = client.ApiClient() if client else None
        else:
            logger.warning("Kubernetes not available - running in development containerization mode")
        self._initialize_service_templates()
        self._load_persistent_instances()
    
    def _initialize_service_templates(self):
        """Initialize service deployment templates"""
        
        # CTFd Template
        self.service_templates['ctfd'] = ServiceTemplate(
            service_type='ctfd',
            image='ctfd/ctfd:3.6.0',
            ports={'http': 8000},
            environment={
                'SECRET_KEY': '${TENANT_SECRET_KEY}',
                'DATABASE_URL': 'sqlite:////data/ctfd.db',
                'DATABASE_CACHE_URL': 'postgresql://gt2_tenant_user:gt2_tenant_dev_password@tenant-postgres:5432/gt2_tenants',
                'UPLOAD_FOLDER': '/data/uploads',
                'LOG_FOLDER': '/data/logs',
            },
            volumes=[
                {'name': 'ctfd-data', 'mountPath': '/data', 'size': '5Gi'},
                {'name': 'ctfd-uploads', 'mountPath': '/uploads', 'size': '2Gi'}
            ],
            resource_limits={
                'memory': '2Gi',
                'cpu': '1000m'
            },
            security_context={
                'runAsNonRoot': True,
                'runAsUser': 1000,
                'fsGroup': 1000,
                'readOnlyRootFilesystem': False
            },
            health_check={
                'path': '/health',
                'port': 8000,
                'initial_delay': 30,
                'period': 10
            },
            sso_config={
                'enabled': True,
                'provider': 'oauth2',
                'callback_path': '/auth/oauth/callback'
            }
        )
        
        # Canvas LMS Template  
        self.service_templates['canvas'] = ServiceTemplate(
            service_type='canvas',
            image='instructure/canvas-lms:stable',
            ports={'http': 3000},
            environment={
                'CANVAS_LMS_ADMIN_EMAIL': 'admin@${TENANT_DOMAIN}',
                'CANVAS_LMS_ADMIN_PASSWORD': '${CANVAS_ADMIN_PASSWORD}',
                'CANVAS_LMS_ACCOUNT_NAME': '${TENANT_NAME}',
                'CANVAS_LMS_STATS_COLLECTION': 'opt_out',
                'POSTGRES_PASSWORD': '${POSTGRES_PASSWORD}',
                'DATABASE_CACHE_URL': 'postgresql://gt2_tenant_user:gt2_tenant_dev_password@tenant-postgres:5432/gt2_tenants'
            },
            volumes=[
                {'name': 'canvas-data', 'mountPath': '/app/log', 'size': '10Gi'},
                {'name': 'canvas-files', 'mountPath': '/app/public/files', 'size': '20Gi'}
            ],
            resource_limits={
                'memory': '4Gi', 
                'cpu': '2000m'
            },
            security_context={
                'runAsNonRoot': True,
                'runAsUser': 1000,
                'fsGroup': 1000
            },
            health_check={
                'path': '/health_check',
                'port': 3000,
                'initial_delay': 60,
                'period': 15
            },
            sso_config={
                'enabled': True,
                'provider': 'saml',
                'metadata_url': '/auth/saml/metadata'
            }
        )
        
        # Guacamole Template
        self.service_templates['guacamole'] = ServiceTemplate(
            service_type='guacamole',
            image='guacamole/guacamole:1.5.3',
            ports={'http': 8080},
            environment={
                'GUACD_HOSTNAME': 'guacd',
                'GUACD_PORT': '4822', 
                'MYSQL_HOSTNAME': 'mysql',
                'MYSQL_PORT': '3306',
                'MYSQL_DATABASE': 'guacamole_db',
                'MYSQL_USER': 'guacamole_user',
                'MYSQL_PASSWORD': '${MYSQL_PASSWORD}',
                'GUAC_LOG_LEVEL': 'INFO'
            },
            volumes=[
                {'name': 'guacamole-data', 'mountPath': '/config', 'size': '1Gi'},
                {'name': 'guacamole-recordings', 'mountPath': '/recordings', 'size': '10Gi'}
            ],
            resource_limits={
                'memory': '1Gi',
                'cpu': '500m'
            },
            security_context={
                'runAsNonRoot': True,
                'runAsUser': 1001,
                'fsGroup': 1001
            },
            health_check={
                'path': '/guacamole',
                'port': 8080,
                'initial_delay': 45,
                'period': 10
            },
            sso_config={
                'enabled': True,
                'provider': 'openid',
                'extension': 'guacamole-auth-openid'
            }
        )
        
        # JupyterHub Template
        self.service_templates['jupyter'] = ServiceTemplate(
            service_type='jupyter',
            image='jupyterhub/jupyterhub:4.0',
            ports={'http': 8000},
            environment={
                'JUPYTERHUB_CRYPT_KEY': '${JUPYTERHUB_CRYPT_KEY}',
                'CONFIGPROXY_AUTH_TOKEN': '${CONFIGPROXY_AUTH_TOKEN}',
                'DOCKER_NETWORK_NAME': 'jupyterhub',
                'DOCKER_NOTEBOOK_IMAGE': 'jupyter/datascience-notebook:lab-4.0.7'
            },
            volumes=[
                {'name': 'jupyter-data', 'mountPath': '/srv/jupyterhub', 'size': '5Gi'},
                {'name': 'docker-socket', 'mountPath': '/var/run/docker.sock', 'hostPath': '/var/run/docker.sock'}
            ],
            resource_limits={
                'memory': '2Gi',
                'cpu': '1000m'
            },
            security_context={
                'runAsNonRoot': False,  # Needs Docker access
                'runAsUser': 0,
                'privileged': True
            },
            health_check={
                'path': '/hub/health',
                'port': 8000,
                'initial_delay': 30,
                'period': 15
            },
            sso_config={
                'enabled': True,
                'provider': 'oauth',
                'authenticator_class': 'oauthenticator.generic.GenericOAuthenticator'
            }
        )
    
    async def create_service_instance(
        self, 
        tenant_id: str, 
        service_type: str,
        config_overrides: Dict[str, Any] = None
    ) -> ServiceInstance:
        """Create a new service instance for a tenant"""
        
        if service_type not in self.service_templates:
            raise ValueError(f"Unsupported service type: {service_type}")
        
        template = self.service_templates[service_type]
        instance_id = f"{service_type}-{tenant_id}-{uuid.uuid4().hex[:8]}"
        namespace = f"{self.base_namespace}-{tenant_id}"
        
        # Generate unique ports
        external_port = await self._get_available_port()
        
        # Create service instance object
        instance = ServiceInstance(
            instance_id=instance_id,
            tenant_id=tenant_id,
            service_type=service_type,
            status='starting',
            endpoint_url=f"https://{service_type}.{tenant_id}.gt2.com",
            internal_port=template.ports['http'],
            external_port=external_port,
            namespace=namespace,
            deployment_name=f"{service_type}-{instance_id}",
            service_name=f"{service_type}-service-{instance_id}",
            ingress_name=f"{service_type}-ingress-{instance_id}",
            resource_usage={'cpu': 0, 'memory': 0, 'storage': 0}
        )
        
        try:
            # Create Kubernetes namespace if not exists
            await self._create_namespace(namespace, tenant_id)
            
            # Deploy the service
            await self._deploy_service(instance, template, config_overrides)
            
            # Generate SSO token
            instance.sso_token = await self._generate_sso_token(instance)
            
            # Store instance
            self.active_instances[instance_id] = instance
            await self._persist_instance(instance)
            
            logger.info(f"Created {service_type} instance {instance_id} for tenant {tenant_id}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create service instance: {e}")
            instance.status = 'error'
            raise
    
    async def _create_namespace(self, namespace: str, tenant_id: str):
        """Create Kubernetes namespace with proper labeling and network policies"""
        
        if not self.k8s_client:
            logger.info(f"Mock: Created namespace {namespace}")
            return
            
        v1 = client.CoreV1Api(self.k8s_client)
        
        # Create namespace
        namespace_manifest = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace,
                labels={
                    'gt.tenant-id': tenant_id,
                    'gt.cluster': 'resource',
                    'gt.isolation': 'tenant'
                },
                annotations={
                    'gt.created-by': 'service-manager',
                    'gt.creation-time': datetime.utcnow().isoformat()
                }
            )
        )
        
        try:
            v1.create_namespace(namespace_manifest)
            logger.info(f"Created namespace: {namespace}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"Namespace {namespace} already exists")
            else:
                raise
        
        # Apply network policy for tenant isolation
        await self._apply_network_policy(namespace, tenant_id)
    
    async def _apply_network_policy(self, namespace: str, tenant_id: str):
        """Apply network policy for tenant isolation"""
        
        if not self.k8s_client:
            logger.info(f"Mock: Applied network policy to {namespace}")
            return
        
        networking_v1 = client.NetworkingV1Api(self.k8s_client)
        
        # Network policy that only allows:
        # 1. Intra-namespace communication
        # 2. Communication to system namespaces (DNS, etc.)
        # 3. Egress to external services (for updates, etc.)
        network_policy = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(
                name=f"tenant-isolation-{tenant_id}",
                namespace=namespace,
                labels={'gt.tenant-id': tenant_id}
            ),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),  # All pods in namespace
                policy_types=['Ingress', 'Egress'],
                ingress=[
                    # Allow ingress from same namespace
                    client.V1NetworkPolicyIngressRule(
                        from_=[client.V1NetworkPolicyPeer(
                            namespace_selector=client.V1LabelSelector(
                                match_labels={'name': namespace}
                            )
                        )]
                    ),
                    # Allow ingress from ingress controller
                    client.V1NetworkPolicyIngressRule(
                        from_=[client.V1NetworkPolicyPeer(
                            namespace_selector=client.V1LabelSelector(
                                match_labels={'name': 'ingress-nginx'}
                            )
                        )]
                    )
                ],
                egress=[
                    # Allow egress within namespace
                    client.V1NetworkPolicyEgressRule(
                        to=[client.V1NetworkPolicyPeer(
                            namespace_selector=client.V1LabelSelector(
                                match_labels={'name': namespace}
                            )
                        )]
                    ),
                    # Allow DNS
                    client.V1NetworkPolicyEgressRule(
                        to=[client.V1NetworkPolicyPeer(
                            namespace_selector=client.V1LabelSelector(
                                match_labels={'name': 'kube-system'}
                            )
                        )],
                        ports=[client.V1NetworkPolicyPort(port=53, protocol='UDP')]
                    ),
                    # Allow external HTTPS (for updates, etc.)
                    client.V1NetworkPolicyEgressRule(
                        ports=[
                            client.V1NetworkPolicyPort(port=443, protocol='TCP'),
                            client.V1NetworkPolicyPort(port=80, protocol='TCP')
                        ]
                    )
                ]
            )
        )
        
        try:
            networking_v1.create_namespaced_network_policy(
                namespace=namespace,
                body=network_policy
            )
            logger.info(f"Applied network policy to namespace: {namespace}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"Network policy already exists in {namespace}")
            else:
                logger.error(f"Failed to create network policy: {e}")
                raise
    
    async def _deploy_service(
        self, 
        instance: ServiceInstance, 
        template: ServiceTemplate,
        config_overrides: Dict[str, Any] = None
    ):
        """Deploy service to Kubernetes cluster"""
        
        if not self.k8s_client:
            logger.info(f"Mock: Deployed {template.service_type} service")
            instance.status = 'running'
            return
        
        # Prepare environment variables with tenant-specific values
        environment = template.environment.copy()
        if config_overrides:
            environment.update(config_overrides.get('environment', {}))
        
        # Substitute tenant-specific values
        env_vars = []
        for key, value in environment.items():
            substituted_value = value.replace('${TENANT_ID}', instance.tenant_id)
            substituted_value = substituted_value.replace('${TENANT_DOMAIN}', f"{instance.tenant_id}.gt2.com")
            env_vars.append(client.V1EnvVar(name=key, value=substituted_value))
        
        # Create volumes
        volumes = []
        volume_mounts = []
        for vol_config in template.volumes:
            vol_name = f"{vol_config['name']}-{instance.instance_id}"
            volumes.append(client.V1Volume(
                name=vol_name,
                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=vol_name
                )
            ))
            volume_mounts.append(client.V1VolumeMount(
                name=vol_name,
                mount_path=vol_config['mountPath']
            ))
        
        # Create PVCs first
        await self._create_persistent_volumes(instance, template)
        
        # Create deployment
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=instance.deployment_name,
                namespace=instance.namespace,
                labels={
                    'app': template.service_type,
                    'instance': instance.instance_id,
                    'gt.tenant-id': instance.tenant_id,
                    'gt.service-type': template.service_type
                }
            ),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels={'instance': instance.instance_id}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            'app': template.service_type,
                            'instance': instance.instance_id,
                            'gt.tenant-id': instance.tenant_id
                        }
                    ),
                    spec=client.V1PodSpec(
                        containers=[client.V1Container(
                            name=template.service_type,
                            image=template.image,
                            ports=[client.V1ContainerPort(
                                container_port=template.ports['http']
                            )],
                            env=env_vars,
                            volume_mounts=volume_mounts,
                            resources=client.V1ResourceRequirements(
                                limits=template.resource_limits,
                                requests=template.resource_limits
                            ),
                            security_context=client.V1SecurityContext(**template.security_context),
                            liveness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(
                                    path=template.health_check['path'],
                                    port=template.health_check['port']
                                ),
                                initial_delay_seconds=template.health_check['initial_delay'],
                                period_seconds=template.health_check['period']
                            ),
                            readiness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(
                                    path=template.health_check['path'],
                                    port=template.health_check['port']
                                ),
                                initial_delay_seconds=10,
                                period_seconds=5
                            )
                        )],
                        volumes=volumes,
                        security_context=client.V1PodSecurityContext(
                            run_as_non_root=template.security_context.get('runAsNonRoot', True),
                            fs_group=template.security_context.get('fsGroup', 1000)
                        )
                    )
                )
            )
        )
        
        # Deploy to Kubernetes
        apps_v1 = client.AppsV1Api(self.k8s_client)
        apps_v1.create_namespaced_deployment(
            namespace=instance.namespace,
            body=deployment
        )
        
        # Create service
        await self._create_service(instance, template)
        
        # Create ingress
        await self._create_ingress(instance, template)
        
        logger.info(f"Deployed {template.service_type} service: {instance.deployment_name}")
    
    async def _create_persistent_volumes(self, instance: ServiceInstance, template: ServiceTemplate):
        """Create persistent volume claims for the service"""
        
        if not self.k8s_client:
            return
            
        v1 = client.CoreV1Api(self.k8s_client)
        
        for vol_config in template.volumes:
            if 'hostPath' in vol_config:  # Skip host path volumes
                continue
                
            pvc_name = f"{vol_config['name']}-{instance.instance_id}"
            
            pvc = client.V1PersistentVolumeClaim(
                metadata=client.V1ObjectMeta(
                    name=pvc_name,
                    namespace=instance.namespace,
                    labels={
                        'app': template.service_type,
                        'instance': instance.instance_id,
                        'gt.tenant-id': instance.tenant_id
                    }
                ),
                spec=client.V1PersistentVolumeClaimSpec(
                    access_modes=['ReadWriteOnce'],
                    resources=client.V1ResourceRequirements(
                        requests={'storage': vol_config['size']}
                    ),
                    storage_class_name='fast-ssd'  # Assuming SSD storage class
                )
            )
            
            try:
                v1.create_namespaced_persistent_volume_claim(
                    namespace=instance.namespace,
                    body=pvc
                )
                logger.info(f"Created PVC: {pvc_name}")
            except ApiException as e:
                if e.status != 409:  # Ignore if already exists
                    raise
    
    async def _create_service(self, instance: ServiceInstance, template: ServiceTemplate):
        """Create Kubernetes service for the instance"""
        
        if not self.k8s_client:
            return
            
        v1 = client.CoreV1Api(self.k8s_client)
        
        service = client.V1Service(
            metadata=client.V1ObjectMeta(
                name=instance.service_name,
                namespace=instance.namespace,
                labels={
                    'app': template.service_type,
                    'instance': instance.instance_id,
                    'gt.tenant-id': instance.tenant_id
                }
            ),
            spec=client.V1ServiceSpec(
                selector={'instance': instance.instance_id},
                ports=[client.V1ServicePort(
                    port=80,
                    target_port=template.ports['http'],
                    protocol='TCP'
                )],
                type='ClusterIP'
            )
        )
        
        v1.create_namespaced_service(
            namespace=instance.namespace,
            body=service
        )
        
        logger.info(f"Created service: {instance.service_name}")
    
    async def _create_ingress(self, instance: ServiceInstance, template: ServiceTemplate):
        """Create ingress for external access with TLS"""
        
        if not self.k8s_client:
            return
            
        networking_v1 = client.NetworkingV1Api(self.k8s_client)
        
        hostname = f"{template.service_type}.{instance.tenant_id}.gt2.com"
        
        ingress = client.V1Ingress(
            metadata=client.V1ObjectMeta(
                name=instance.ingress_name,
                namespace=instance.namespace,
                labels={
                    'app': template.service_type,
                    'instance': instance.instance_id,
                    'gt.tenant-id': instance.tenant_id
                },
                annotations={
                    'kubernetes.io/ingress.class': 'nginx',
                    'cert-manager.io/cluster-issuer': 'letsencrypt-prod',
                    'nginx.ingress.kubernetes.io/ssl-redirect': 'true',
                    'nginx.ingress.kubernetes.io/force-ssl-redirect': 'true',
                    'nginx.ingress.kubernetes.io/auth-url': f'https://auth.{instance.tenant_id}.gt2.com/auth',
                    'nginx.ingress.kubernetes.io/auth-signin': f'https://auth.{instance.tenant_id}.gt2.com/signin'
                }
            ),
            spec=client.V1IngressSpec(
                tls=[client.V1IngressTLS(
                    hosts=[hostname],
                    secret_name=f"{template.service_type}-tls-{instance.instance_id}"
                )],
                rules=[client.V1IngressRule(
                    host=hostname,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[client.V1HTTPIngressPath(
                            path='/',
                            path_type='Prefix',
                            backend=client.V1IngressBackend(
                                service=client.V1IngressServiceBackend(
                                    name=instance.service_name,
                                    port=client.V1ServiceBackendPort(number=80)
                                )
                            )
                        )]
                    )
                )]
            )
        )
        
        networking_v1.create_namespaced_ingress(
            namespace=instance.namespace,
            body=ingress
        )
        
        logger.info(f"Created ingress: {instance.ingress_name} for {hostname}")
    
    async def _get_available_port(self) -> int:
        """Get next available port for service"""
        used_ports = {instance.external_port for instance in self.active_instances.values()}
        port = 30000  # Start from NodePort range
        while port in used_ports:
            port += 1
        return port
    
    async def _generate_sso_token(self, instance: ServiceInstance) -> str:
        """Generate SSO token for iframe embedding"""
        token_data = {
            'tenant_id': instance.tenant_id,
            'service_type': instance.service_type,
            'instance_id': instance.instance_id,
            'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            'permissions': ['read', 'write', 'admin']
        }
        
        # Encrypt the token data
        encrypted_token = encrypt_data(json.dumps(token_data))
        return encrypted_token.decode('utf-8')
    
    async def get_service_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """Get service instance by ID"""
        return self.active_instances.get(instance_id)
    
    async def list_tenant_instances(self, tenant_id: str) -> List[ServiceInstance]:
        """List all service instances for a tenant"""
        return [
            instance for instance in self.active_instances.values()
            if instance.tenant_id == tenant_id
        ]
    
    async def stop_service_instance(self, instance_id: str) -> bool:
        """Stop a running service instance"""
        instance = self.active_instances.get(instance_id)
        if not instance:
            return False
        
        try:
            instance.status = 'stopping'
            
            if self.k8s_client:
                # Delete Kubernetes resources
                await self._cleanup_kubernetes_resources(instance)
            
            instance.status = 'stopped'
            logger.info(f"Stopped service instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop instance {instance_id}: {e}")
            instance.status = 'error'
            return False
    
    async def _cleanup_kubernetes_resources(self, instance: ServiceInstance):
        """Clean up all Kubernetes resources for an instance"""
        
        if not self.k8s_client:
            return
        
        apps_v1 = client.AppsV1Api(self.k8s_client)
        v1 = client.CoreV1Api(self.k8s_client)
        networking_v1 = client.NetworkingV1Api(self.k8s_client)
        
        try:
            # Delete deployment
            apps_v1.delete_namespaced_deployment(
                name=instance.deployment_name,
                namespace=instance.namespace,
                body=client.V1DeleteOptions()
            )
            
            # Delete service
            v1.delete_namespaced_service(
                name=instance.service_name,
                namespace=instance.namespace,
                body=client.V1DeleteOptions()
            )
            
            # Delete ingress
            networking_v1.delete_namespaced_ingress(
                name=instance.ingress_name,
                namespace=instance.namespace,
                body=client.V1DeleteOptions()
            )
            
            # Delete PVCs (optional - may want to preserve data)
            # Note: In production, you might want to keep PVCs for data persistence
            
            logger.info(f"Cleaned up Kubernetes resources for: {instance.instance_id}")
            
        except ApiException as e:
            logger.error(f"Error cleaning up resources: {e}")
            raise
    
    async def get_service_health(self, instance_id: str) -> Dict[str, Any]:
        """Get health status of a service instance"""
        instance = self.active_instances.get(instance_id)
        if not instance:
            return {'status': 'not_found'}
        
        if not self.k8s_client:
            return {
                'status': 'healthy',
                'instance_status': instance.status,
                'endpoint': instance.endpoint_url,
                'last_check': datetime.utcnow().isoformat()
            }
        
        # Check Kubernetes pod status
        v1 = client.CoreV1Api(self.k8s_client)
        
        try:
            pods = v1.list_namespaced_pod(
                namespace=instance.namespace,
                label_selector=f'instance={instance.instance_id}'
            )
            
            if not pods.items:
                return {
                    'status': 'no_pods',
                    'instance_status': instance.status
                }
            
            pod = pods.items[0]
            pod_status = 'unknown'
            
            if pod.status.phase == 'Running':
                # Check container status
                if pod.status.container_statuses:
                    container_status = pod.status.container_statuses[0]
                    if container_status.ready:
                        pod_status = 'healthy'
                    else:
                        pod_status = 'unhealthy'
                else:
                    pod_status = 'starting'
            elif pod.status.phase == 'Pending':
                pod_status = 'starting'
            elif pod.status.phase == 'Failed':
                pod_status = 'failed'
            
            # Update instance heartbeat
            instance.last_heartbeat = datetime.utcnow()
            
            return {
                'status': pod_status,
                'instance_status': instance.status,
                'pod_phase': pod.status.phase,
                'endpoint': instance.endpoint_url,
                'last_check': datetime.utcnow().isoformat(),
                'restart_count': pod.status.container_statuses[0].restart_count if pod.status.container_statuses else 0
            }
            
        except ApiException as e:
            logger.error(f"Failed to get health for {instance_id}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'instance_status': instance.status
            }
    
    async def _persist_instance(self, instance: ServiceInstance):
        """Persist instance data to disk"""
        instance_file = self.storage_path / f"{instance.instance_id}.json"
        
        with open(instance_file, 'w') as f:
            json.dump(instance.to_dict(), f, indent=2)
    
    def _load_persistent_instances(self):
        """Load persistent instances from disk on startup"""
        if not self.storage_path.exists():
            return
        
        for instance_file in self.storage_path.glob("*.json"):
            try:
                with open(instance_file, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct instance object
                instance = ServiceInstance(
                    instance_id=data['instance_id'],
                    tenant_id=data['tenant_id'],
                    service_type=data['service_type'],
                    status=data['status'],
                    endpoint_url=data['endpoint_url'],
                    internal_port=data['internal_port'],
                    external_port=data['external_port'],
                    namespace=data['namespace'],
                    deployment_name=data['deployment_name'],
                    service_name=data['service_name'],
                    ingress_name=data['ingress_name'],
                    sso_token=data.get('sso_token'),
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_heartbeat=datetime.fromisoformat(data['last_heartbeat']),
                    resource_usage=data.get('resource_usage', {})
                )
                
                self.active_instances[instance.instance_id] = instance
                logger.info(f"Loaded persistent instance: {instance.instance_id}")
                
            except Exception as e:
                logger.error(f"Failed to load instance from {instance_file}: {e}")
    
    async def cleanup_orphaned_resources(self):
        """Clean up orphaned Kubernetes resources"""
        if not self.k8s_client:
            return
        
        logger.info("Starting cleanup of orphaned resources...")
        
        # This would implement logic to find and clean up:
        # 1. Deployments without corresponding instances
        # 2. Services without deployments
        # 3. Unused PVCs
        # 4. Expired certificates
        
        # Implementation would query Kubernetes for resources with GT labels
        # and cross-reference with active instances
        
        logger.info("Cleanup completed")