// Tenant management utilities
import { Tenant, TenantCreateRequest } from '@gt2/types';
import { generateEncryptionKey, deriveTenantKey } from './crypto';

/**
 * Generate Kubernetes namespace name for tenant
 */
export function generateTenantNamespace(domain: string): string {
  return `gt-${domain}`;
}

/**
 * Generate tenant subdomain
 */
export function generateTenantSubdomain(domain: string): string {
  return domain; // For now, subdomain matches domain
}

/**
 * Generate OS user ID for tenant isolation
 */
export function generateTenantUserId(tenantId: number): number {
  const baseUserId = 10000; // Start user IDs from 10000
  return baseUserId + tenantId;
}

/**
 * Generate OS group ID for tenant isolation
 */
export function generateTenantGroupId(tenantId: number): number {
  return generateTenantUserId(tenantId); // Use same ID for group
}

/**
 * Get tenant data directory path
 */
export function getTenantDataPath(domain: string, baseDataDir: string = '/data'): string {
  return `${baseDataDir}/${domain}`;
}

/**
 * Get default resource limits based on template
 */
export function getTemplateResourceLimits(template: string): {
  cpu: string;
  memory: string;
  storage: string;
} {
  switch (template) {
    case 'basic':
      return {
        cpu: '500m',
        memory: '1Gi',
        storage: '5Gi'
      };
    case 'professional':
      return {
        cpu: '1000m',
        memory: '2Gi',
        storage: '20Gi'
      };
    case 'enterprise':
      return {
        cpu: '2000m',
        memory: '4Gi',
        storage: '100Gi'
      };
    default:
      return {
        cpu: '500m',
        memory: '1Gi',
        storage: '5Gi'
      };
  }
}

/**
 * Get default max users based on template
 */
export function getTemplateMaxUsers(template: string): number {
  switch (template) {
    case 'basic':
      return 10;
    case 'professional':
      return 100;
    case 'enterprise':
      return 1000;
    default:
      return 10;
  }
}

/**
 * Validate tenant domain availability (placeholder - would check database in real implementation)
 */
export function isDomainAvailable(domain: string): boolean {
  // In real implementation, this would check the database
  // For now, just check format
  const reservedDomains = ['admin', 'api', 'www', 'mail', 'ftp', 'localhost', 'gt2'];
  return !reservedDomains.includes(domain.toLowerCase());
}

/**
 * Generate complete tenant configuration from create request
 */
export function generateTenantConfig(
  request: TenantCreateRequest,
  masterEncryptionKey: string
): Partial<Tenant> {
  const template = request.template || 'basic';
  const resourceLimits = request.resource_limits || getTemplateResourceLimits(template);
  const maxUsers = request.max_users || getTemplateMaxUsers(template);
  
  return {
    name: request.name.trim(),
    domain: request.domain.toLowerCase(),
    template,
    max_users: maxUsers,
    resource_limits: resourceLimits,
    namespace: generateTenantNamespace(request.domain),
    subdomain: generateTenantSubdomain(request.domain),
    status: 'pending'
  };
}

/**
 * Generate Kubernetes deployment YAML for tenant
 */
export function generateTenantDeploymentYAML(tenant: Tenant, tenantUserId: number): string {
  return `
apiVersion: v1
kind: Namespace
metadata:
  name: ${tenant.namespace}
  labels:
    gt.tenant: ${tenant.domain}
    gt.template: ${tenant.template}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ${tenant.domain}-isolation
  namespace: ${tenant.namespace}
spec:
  podSelector: {}
  policyTypes: ["Ingress", "Egress"]
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: gt-admin
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: gt-resource
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${tenant.domain}-config
  namespace: ${tenant.namespace}
data:
  TENANT_ID: "${tenant.id}"
  TENANT_DOMAIN: "${tenant.domain}"
  TENANT_NAME: "${tenant.name}"
  DATABASE_PATH: "/data/${tenant.domain}/app.db"
  CHROMA_COLLECTION: "gt2_${tenant.domain.replace(/-/g, '_')}_documents"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${tenant.domain}-app
  namespace: ${tenant.namespace}
  labels:
    app: ${tenant.domain}-app
    tenant: ${tenant.domain}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${tenant.domain}-app
  template:
    metadata:
      labels:
        app: ${tenant.domain}-app
        tenant: ${tenant.domain}
    spec:
      securityContext:
        runAsUser: ${tenantUserId}
        runAsGroup: ${tenantUserId}
        fsGroup: ${tenantUserId}
      containers:
      - name: frontend
        image: gt2/tenant-frontend:latest
        ports:
        - containerPort: 3000
          name: frontend
        env:
        - name: NEXT_PUBLIC_API_URL
          value: "http://localhost:8000"
        - name: NEXT_PUBLIC_WS_URL
          value: "ws://localhost:8000"
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "${tenant.resource_limits.cpu}"
            memory: "${tenant.resource_limits.memory}"
        volumeMounts:
        - name: tenant-data
          mountPath: /data/${tenant.domain}
      - name: backend
        image: gt2/tenant-backend:latest
        ports:
        - containerPort: 8000
          name: backend
        envFrom:
        - configMapRef:
            name: ${tenant.domain}-config
        env:
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: ${tenant.domain}-secrets
              key: encryption-key
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "${tenant.resource_limits.cpu}"
            memory: "${tenant.resource_limits.memory}"
        volumeMounts:
        - name: tenant-data
          mountPath: /data/${tenant.domain}
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: tenant-data
        persistentVolumeClaim:
          claimName: ${tenant.domain}-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${tenant.domain}-data
  namespace: ${tenant.namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: ${tenant.resource_limits.storage}
---
apiVersion: v1
kind: Secret
metadata:
  name: ${tenant.domain}-secrets
  namespace: ${tenant.namespace}
type: Opaque
data:
  encryption-key: ${Buffer.from(tenant.encryption_key || '').toString('base64')}
---
apiVersion: v1
kind: Service
metadata:
  name: ${tenant.domain}-service
  namespace: ${tenant.namespace}
spec:
  selector:
    app: ${tenant.domain}-app
  ports:
  - name: frontend
    port: 3000
    targetPort: 3000
  - name: backend
    port: 8000
    targetPort: 8000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${tenant.domain}-ingress
  namespace: ${tenant.namespace}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: ${tenant.subdomain}.gt2.local
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: ${tenant.domain}-service
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ${tenant.domain}-service
            port:
              number: 3000
  `.trim();
}

/**
 * Calculate tenant usage costs
 */
export function calculateTenantCosts(
  cpuUsage: number, // CPU hours
  memoryUsage: number, // Memory GB-hours
  storageUsage: number, // Storage GB-hours
  aiTokens: number // AI tokens used
): {
  cpu_cost_cents: number;
  memory_cost_cents: number;
  storage_cost_cents: number;
  ai_cost_cents: number;
  total_cost_cents: number;
} {
  // Pricing (example rates)
  const CPU_COST_PER_HOUR = 5; // 5 cents per CPU hour
  const MEMORY_COST_PER_GB_HOUR = 1; // 1 cent per GB-hour
  const STORAGE_COST_PER_GB_HOUR = 0.1; // 0.1 cents per GB-hour
  const AI_COST_PER_1K_TOKENS = 0.5; // 0.5 cents per 1K tokens

  const cpu_cost_cents = Math.round(cpuUsage * CPU_COST_PER_HOUR);
  const memory_cost_cents = Math.round(memoryUsage * MEMORY_COST_PER_GB_HOUR);
  const storage_cost_cents = Math.round(storageUsage * STORAGE_COST_PER_GB_HOUR);
  const ai_cost_cents = Math.round((aiTokens / 1000) * AI_COST_PER_1K_TOKENS);

  return {
    cpu_cost_cents,
    memory_cost_cents,
    storage_cost_cents,
    ai_cost_cents,
    total_cost_cents: cpu_cost_cents + memory_cost_cents + storage_cost_cents + ai_cost_cents
  };
}