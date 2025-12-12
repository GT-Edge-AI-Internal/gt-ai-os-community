/**
 * Generate a random encryption key
 */
export declare function generateEncryptionKey(): string;
/**
 * Encrypt data using AES-256-GCM
 */
export declare function encrypt(data: string, keyHex: string): {
    encrypted: string;
    iv: string;
    tag: string;
};
/**
 * Decrypt data using AES-256-GCM
 */
export declare function decrypt(encryptedData: string, keyHex: string, ivHex: string, tagHex: string): string;
/**
 * Hash data using SHA-256
 */
export declare function sha256Hash(data: string): string;
/**
 * Generate HMAC signature
 */
export declare function generateHMAC(data: string, secret: string): string;
/**
 * Verify HMAC signature
 */
export declare function verifyHMAC(data: string, signature: string, secret: string): boolean;
/**
 * Generate tenant-specific encryption key from master key and tenant ID
 */
export declare function deriveTenantKey(masterKey: string, tenantId: string): string;
/**
 * Encrypt JSON data for database storage
 */
export declare function encryptForDatabase(data: any, encryptionKey: string): string;
/**
 * Decrypt JSON data from database storage
 */
export declare function decryptFromDatabase(encryptedData: string, encryptionKey: string): any;
/**
 * Generate a secure random password
 */
export declare function generateSecurePassword(length?: number): string;
