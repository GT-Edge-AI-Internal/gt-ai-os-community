"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateEncryptionKey = generateEncryptionKey;
exports.encrypt = encrypt;
exports.decrypt = decrypt;
exports.sha256Hash = sha256Hash;
exports.generateHMAC = generateHMAC;
exports.verifyHMAC = verifyHMAC;
exports.deriveTenantKey = deriveTenantKey;
exports.encryptForDatabase = encryptForDatabase;
exports.decryptFromDatabase = decryptFromDatabase;
exports.generateSecurePassword = generateSecurePassword;
// Cryptographic utilities for GT 2.0
const crypto_1 = __importDefault(require("crypto"));
// Encryption configuration
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16; // 128 bits
const TAG_LENGTH = 16; // 128 bits
/**
 * Generate a random encryption key
 */
function generateEncryptionKey() {
    return crypto_1.default.randomBytes(KEY_LENGTH).toString('hex');
}
/**
 * Encrypt data using AES-256-GCM
 */
function encrypt(data, keyHex) {
    const key = Buffer.from(keyHex, 'hex');
    const iv = crypto_1.default.randomBytes(IV_LENGTH);
    const cipher = crypto_1.default.createCipher(ALGORITHM, key);
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
function decrypt(encryptedData, keyHex, ivHex, tagHex) {
    const key = Buffer.from(keyHex, 'hex');
    const iv = Buffer.from(ivHex, 'hex');
    const tag = Buffer.from(tagHex, 'hex');
    const decipher = crypto_1.default.createDecipher(ALGORITHM, key);
    decipher.setAuthTag(tag);
    decipher.setAAD(Buffer.from('GT2-TENANT-DATA'));
    let decrypted = decipher.update(encryptedData, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
}
/**
 * Hash data using SHA-256
 */
function sha256Hash(data) {
    return crypto_1.default.createHash('sha256').update(data).digest('hex');
}
/**
 * Generate HMAC signature
 */
function generateHMAC(data, secret) {
    return crypto_1.default.createHmac('sha256', secret).update(data).digest('hex');
}
/**
 * Verify HMAC signature
 */
function verifyHMAC(data, signature, secret) {
    const expectedSignature = generateHMAC(data, secret);
    return crypto_1.default.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expectedSignature, 'hex'));
}
/**
 * Generate tenant-specific encryption key from master key and tenant ID
 */
function deriveTenantKey(masterKey, tenantId) {
    const key = crypto_1.default.pbkdf2Sync(tenantId, Buffer.from(masterKey, 'hex'), 100000, // iterations
    KEY_LENGTH, 'sha256');
    return key.toString('hex');
}
/**
 * Encrypt JSON data for database storage
 */
function encryptForDatabase(data, encryptionKey) {
    const jsonString = JSON.stringify(data);
    const { encrypted, iv, tag } = encrypt(jsonString, encryptionKey);
    // Combine all components into a single string
    return `${iv}:${tag}:${encrypted}`;
}
/**
 * Decrypt JSON data from database storage
 */
function decryptFromDatabase(encryptedData, encryptionKey) {
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
function generateSecurePassword(length = 16) {
    const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
    let password = '';
    for (let i = 0; i < length; i++) {
        const randomIndex = crypto_1.default.randomInt(0, charset.length);
        password += charset[randomIndex];
    }
    return password;
}
