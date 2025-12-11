// Cryptographic utilities for GT 2.0
import crypto from 'crypto';

// Encryption configuration
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16;  // 128 bits
const TAG_LENGTH = 16; // 128 bits

/**
 * Generate a random encryption key
 */
export function generateEncryptionKey(): string {
  return crypto.randomBytes(KEY_LENGTH).toString('hex');
}

/**
 * Encrypt data using AES-256-GCM
 */
export function encrypt(data: string, keyHex: string): {
  encrypted: string;
  iv: string;
  tag: string;
} {
  const key = Buffer.from(keyHex, 'hex');
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipher(ALGORITHM, key);
  cipher.setAAD(Buffer.from('GT2-TENANT-DATA'));

  let encrypted = cipher.update(data, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  
  const tag = cipher.getAuthTag();

  return {
    encrypted,
    iv: iv.toString('hex'),
    tag: tag.toString('hex')
  };
}

/**
 * Decrypt data using AES-256-GCM
 */
export function decrypt(
  encryptedData: string,
  keyHex: string,
  ivHex: string,
  tagHex: string
): string {
  const key = Buffer.from(keyHex, 'hex');
  const iv = Buffer.from(ivHex, 'hex');
  const tag = Buffer.from(tagHex, 'hex');
  
  const decipher = crypto.createDecipher(ALGORITHM, key);
  decipher.setAuthTag(tag);
  decipher.setAAD(Buffer.from('GT2-TENANT-DATA'));

  let decrypted = decipher.update(encryptedData, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

/**
 * Hash data using SHA-256
 */
export function sha256Hash(data: string): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}

/**
 * Generate HMAC signature
 */
export function generateHMAC(data: string, secret: string): string {
  return crypto.createHmac('sha256', secret).update(data).digest('hex');
}

/**
 * Verify HMAC signature
 */
export function verifyHMAC(data: string, signature: string, secret: string): boolean {
  const expectedSignature = generateHMAC(data, secret);
  return crypto.timingSafeEqual(
    Buffer.from(signature, 'hex'),
    Buffer.from(expectedSignature, 'hex')
  );
}

/**
 * Generate tenant-specific encryption key from master key and tenant ID
 */
export function deriveTenantKey(masterKey: string, tenantId: string): string {
  const key = crypto.pbkdf2Sync(
    tenantId,
    Buffer.from(masterKey, 'hex'),
    100000, // iterations
    KEY_LENGTH,
    'sha256'
  );
  return key.toString('hex');
}

/**
 * Encrypt JSON data for database storage
 */
export function encryptForDatabase(
  data: any,
  encryptionKey: string
): string {
  const jsonString = JSON.stringify(data);
  const { encrypted, iv, tag } = encrypt(jsonString, encryptionKey);
  
  // Combine all components into a single string
  return `${iv}:${tag}:${encrypted}`;
}

/**
 * Decrypt JSON data from database storage
 */
export function decryptFromDatabase(
  encryptedData: string,
  encryptionKey: string
): any {
  const [iv, tag, encrypted] = encryptedData.split(':');
  if (!iv || !tag || !encrypted) {
    throw new Error('Invalid encrypted data format');
  }

  const jsonString = decrypt(encrypted, encryptionKey, iv, tag);
  return JSON.parse(jsonString);
}

/**
 * Generate a secure random password
 */
export function generateSecurePassword(length: number = 16): string {
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
  let password = '';
  
  for (let i = 0; i < length; i++) {
    const randomIndex = crypto.randomInt(0, charset.length);
    password += charset[randomIndex];
  }
  
  return password;
}