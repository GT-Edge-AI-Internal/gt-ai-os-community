/**
 * Test setup for utility functions
 */

// Mock environment variables for testing
process.env.JWT_SECRET = 'test-jwt-secret-for-testing-only';
process.env.MASTER_ENCRYPTION_KEY = 'test-master-key-32-bytes-long-test';

// Mock crypto for consistent testing
jest.mock('crypto', () => {
  const originalCrypto = jest.requireActual('crypto');
  return {
    ...originalCrypto,
    randomBytes: jest.fn().mockImplementation((size: number) => {
      return Buffer.alloc(size, 'a'); // Return consistent fake random bytes
    }),
    randomInt: jest.fn().mockReturnValue(5), // Return consistent fake random int
  };
});

// Global test timeout
jest.setTimeout(10000);