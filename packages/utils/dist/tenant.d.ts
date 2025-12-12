import { Tenant, TenantCreateRequest } from '@gt2/types';
/**
 * Generate Kubernetes namespace name for tenant
 */
export declare function generateTenantNamespace(domain: string): string;
/**
 * Generate tenant subdomain
 */
export declare function generateTenantSubdomain(domain: string): string;
/**
 * Generate OS user ID for tenant isolation
 */
export declare function generateTenantUserId(tenantId: number): number;
/**
 * Generate OS group ID for tenant isolation
 */
export declare function generateTenantGroupId(tenantId: number): number;
/**
 * Get tenant data directory path
 */
export declare function getTenantDataPath(domain: string, baseDataDir?: string): string;
/**
 * Get default resource limits based on template
 */
export declare function getTemplateResourceLimits(template: string): {
    cpu: string;
    memory: string;
    storage: string;
};
/**
 * Get default max users based on template
 */
export declare function getTemplateMaxUsers(template: string): number;
/**
 * Validate tenant domain availability (placeholder - would check database in real implementation)
 */
export declare function isDomainAvailable(domain: string): boolean;
/**
 * Generate complete tenant configuration from create request
 */
export declare function generateTenantConfig(request: TenantCreateRequest, masterEncryptionKey: string): Partial<Tenant>;
/**
 * Generate Kubernetes deployment YAML for tenant
 */
export declare function generateTenantDeploymentYAML(tenant: Tenant, tenantUserId: number): string;
/**
 * Calculate tenant usage costs
 */
export declare function calculateTenantCosts(cpuUsage: number, // CPU hours
memoryUsage: number, // Memory GB-hours
storageUsage: number, // Storage GB-hours
aiTokens: number): {
    cpu_cost_cents: number;
    memory_cost_cents: number;
    storage_cost_cents: number;
    ai_cost_cents: number;
    total_cost_cents: number;
};
