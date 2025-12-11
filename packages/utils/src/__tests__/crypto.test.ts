/**
 * Unit tests for cryptographic utilities
 */
import {
  generateEncryptionKey,
  encrypt,
  decrypt,
  sha256Hash,
  generateHMAC,
  verifyHMAC,
  deriveTenantKey,
  encryptForDatabase,
  decryptFromDatabase,
  generateSecurePassword
} from '../crypto';

describe('Cryptographic Utilities', () => {
  describe('Key Generation', () => {
    test('generateEncryptionKey creates valid key', () => {
      const key = generateEncryptionKey();
      
      expect(typeof key).toBe('string');
      expect(key.length).toBe(64); // 32 bytes * 2 for hex encoding
      expect(/^[a-f0-9]+$/i.test(key)).toBe(true); // Valid hex string
    });

    test('generateEncryptionKey creates different keys', () => {
      const key1 = generateEncryptionKey();
      const key2 = generateEncryptionKey();
      
      expect(key1).not.toBe(key2);
    });
  });

  describe('Encryption/Decryption', () => {
    const testData = 'This is test data to encrypt';
    const testKey = 'a'.repeat(64); // 32-byte key in hex

    test('encrypt returns encrypted data with IV and tag', () => {
      const result = encrypt(testData, testKey);
      
      expect(result).toHaveProperty('encrypted');
      expect(result).toHaveProperty('iv');
      expect(result).toHaveProperty('tag');
      expect(typeof result.encrypted).toBe('string');
      expect(typeof result.iv).toBe('string');
      expect(typeof result.tag).toBe('string');
      expect(result.encrypted).not.toBe(testData);
    });

    test('decrypt successfully recovers original data', () => {
      const { encrypted, iv, tag } = encrypt(testData, testKey);
      const decrypted = decrypt(encrypted, testKey, iv, tag);
      
      expect(decrypted).toBe(testData);
    });

    test('decrypt fails with wrong key', () => {
      const { encrypted, iv, tag } = encrypt(testData, testKey);
      const wrongKey = 'b'.repeat(64);
      
      expect(() => {
        decrypt(encrypted, wrongKey, iv, tag);
      }).toThrow();
    });

    test('decrypt fails with tampered data', () => {
      const { encrypted, iv, tag } = encrypt(testData, testKey);
      const tamperedData = encrypted.slice(0, -2) + 'XX';
      
      expect(() => {
        decrypt(tamperedData, testKey, iv, tag);
      }).toThrow();
    });

    test('encryption produces different results for same data', () => {
      const result1 = encrypt(testData, testKey);
      const result2 = encrypt(testData, testKey);
      
      // Different IVs should produce different encrypted data
      expect(result1.encrypted).not.toBe(result2.encrypted);
      expect(result1.iv).not.toBe(result2.iv);
      
      // But both should decrypt to same original data
      const decrypted1 = decrypt(result1.encrypted, testKey, result1.iv, result1.tag);
      const decrypted2 = decrypt(result2.encrypted, testKey, result2.iv, result2.tag);
      expect(decrypted1).toBe(testData);
      expect(decrypted2).toBe(testData);
    });
  });

  describe('Hashing', () => {
    test('sha256Hash creates consistent hash', () => {
      const data = 'test data';
      const hash1 = sha256Hash(data);
      const hash2 = sha256Hash(data);
      
      expect(hash1).toBe(hash2);
      expect(typeof hash1).toBe('string');
      expect(hash1.length).toBe(64); // SHA-256 produces 32 bytes = 64 hex chars
    });

    test('sha256Hash creates different hashes for different data', () => {
      const hash1 = sha256Hash('data 1');
      const hash2 = sha256Hash('data 2');
      
      expect(hash1).not.toBe(hash2);
    });
  });

  describe('HMAC', () => {
    const testData = 'test data';
    const testSecret = 'test secret';

    test('generateHMAC creates valid signature', () => {
      const signature = generateHMAC(testData, testSecret);
      
      expect(typeof signature).toBe('string');
      expect(signature.length).toBe(64); // HMAC-SHA256 = 64 hex chars
      expect(/^[a-f0-9]+$/i.test(signature)).toBe(true);
    });

    test('verifyHMAC validates correct signature', () => {
      const signature = generateHMAC(testData, testSecret);
      const isValid = verifyHMAC(testData, signature, testSecret);
      
      expect(isValid).toBe(true);
    });

    test('verifyHMAC rejects incorrect signature', () => {
      const signature = generateHMAC(testData, testSecret);
      const isValid = verifyHMAC(testData, signature + 'tampered', testSecret);
      
      expect(isValid).toBe(false);
    });

    test('verifyHMAC rejects signature with wrong secret', () => {
      const signature = generateHMAC(testData, testSecret);
      const isValid = verifyHMAC(testData, signature, 'wrong secret');
      
      expect(isValid).toBe(false);
    });

    test('HMAC is consistent for same inputs', () => {
      const signature1 = generateHMAC(testData, testSecret);
      const signature2 = generateHMAC(testData, testSecret);
      
      expect(signature1).toBe(signature2);
    });
  });

  describe('Key Derivation', () => {
    const masterKey = 'a'.repeat(64); // 32-byte master key
    const tenantId = 'tenant-123';

    test('deriveTenantKey creates consistent key for tenant', () => {
      const key1 = deriveTenantKey(masterKey, tenantId);
      const key2 = deriveTenantKey(masterKey, tenantId);
      
      expect(key1).toBe(key2);
      expect(typeof key1).toBe('string');
      expect(key1.length).toBe(64); // 32 bytes in hex
    });

    test('deriveTenantKey creates different keys for different tenants', () => {
      const key1 = deriveTenantKey(masterKey, 'tenant-1');
      const key2 = deriveTenantKey(masterKey, 'tenant-2');
      
      expect(key1).not.toBe(key2);
    });

    test('deriveTenantKey creates different keys for different master keys', () => {
      const masterKey2 = 'b'.repeat(64);
      const key1 = deriveTenantKey(masterKey, tenantId);
      const key2 = deriveTenantKey(masterKey2, tenantId);
      
      expect(key1).not.toBe(key2);
    });
  });

  describe('Database Encryption', () => {
    const testData = { id: 1, name: 'test', data: [1, 2, 3] };
    const testKey = 'a'.repeat(64);

    test('encryptForDatabase encrypts JSON data', () => {
      const encrypted = encryptForDatabase(testData, testKey);
      
      expect(typeof encrypted).toBe('string');
      expect(encrypted.split(':')).toHaveLength(3); // iv:tag:encrypted format
      expect(encrypted).not.toContain('test'); // Should not contain original data
    });

    test('decryptFromDatabase recovers original JSON data', () => {
      const encrypted = encryptForDatabase(testData, testKey);
      const decrypted = decryptFromDatabase(encrypted, testKey);
      
      expect(decrypted).toEqual(testData);
    });

    test('decryptFromDatabase fails with wrong key', () => {
      const encrypted = encryptForDatabase(testData, testKey);
      const wrongKey = 'b'.repeat(64);
      
      expect(() => {
        decryptFromDatabase(encrypted, wrongKey);
      }).toThrow();
    });

    test('decryptFromDatabase fails with invalid format', () => {
      expect(() => {
        decryptFromDatabase('invalid-format', testKey);
      }).toThrow('Invalid encrypted data format');
    });

    test('database encryption handles complex objects', () => {
      const complexData = {
        user: { id: 1, name: 'John Doe' },
        preferences: { theme: 'dark', lang: 'en' },
        timestamps: { created: new Date().toISOString() },
        numbers: [1, 2.5, -3],
        boolean: true,
        null_value: null
      };

      const encrypted = encryptForDatabase(complexData, testKey);
      const decrypted = decryptFromDatabase(encrypted, testKey);
      
      expect(decrypted).toEqual(complexData);
    });
  });

  describe('Password Generation', () => {
    test('generateSecurePassword creates password of correct length', () => {
      const password = generateSecurePassword(16);
      
      expect(typeof password).toBe('string');
      expect(password.length).toBe(16);
    });

    test('generateSecurePassword uses default length', () => {
      const password = generateSecurePassword();
      
      expect(password.length).toBe(16); // Default length
    });

    test('generateSecurePassword creates different passwords', () => {
      const password1 = generateSecurePassword();
      const password2 = generateSecurePassword();
      
      expect(password1).not.toBe(password2);
    });

    test('generateSecurePassword includes variety of characters', () => {
      const password = generateSecurePassword(50); // Longer for better test
      
      expect(/[a-z]/.test(password)).toBe(true); // Lowercase
      expect(/[A-Z]/.test(password)).toBe(true); // Uppercase  
      expect(/[0-9]/.test(password)).toBe(true); // Numbers
      expect(/[!@#$%^&*]/.test(password)).toBe(true); // Special chars
    });

    test('generateSecurePassword creates strong passwords', () => {
      // Test multiple passwords to ensure consistency
      for (let i = 0; i < 10; i++) {
        const password = generateSecurePassword(12);
        expect(password.length).toBe(12);
        expect(/[a-zA-Z0-9!@#$%^&*]/.test(password)).toBe(true);
      }
    });
  });
});