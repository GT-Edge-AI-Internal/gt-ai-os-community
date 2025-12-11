/**
 * Generate SQLite database path for tenant
 */
export declare function getTenantDatabasePath(tenantDomain: string, dataDir?: string): string;
/**
 * Generate ChromaDB collection name for tenant
 */
export declare function getTenantChromaCollection(tenantDomain: string): string;
/**
 * Generate Redis key prefix for tenant
 */
export declare function getTenantRedisPrefix(tenantDomain: string): string;
/**
 * Generate MinIO bucket name for tenant
 */
export declare function getTenantMinioBucket(tenantDomain: string): string;
/**
 * Generate SQLite WAL mode configuration
 */
export declare function getSQLiteWALConfig(): string;
/**
 * Generate SQLite encryption configuration
 */
export declare function getSQLiteEncryptionConfig(encryptionKey: string): string;
/**
 * Create tenant database schema (SQLite)
 */
export declare function getTenantDatabaseSchema(): string;
/**
 * Generate unique document chunk ID
 */
export declare function generateDocumentChunkId(documentId: number, chunkIndex: number): string;
/**
 * Parse connection string for database configuration
 */
export declare function parseConnectionString(connectionString: string): {
    host?: string;
    port?: number;
    database?: string;
    username?: string;
    password?: string;
    options?: Record<string, string>;
};
/**
 * Escape SQL identifiers (table names, column names, etc.)
 */
export declare function escapeSQLIdentifier(identifier: string): string;
/**
 * Generate database backup filename
 */
export declare function generateBackupFilename(tenantDomain: string, timestamp?: Date): string;
