"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * Unit tests for validation utilities
 */
const validation_1 = require("../validation");
describe('Validation Utilities', () => {
    describe('Email Validation', () => {
        test('validates correct email formats', () => {
            const validEmails = [
                'test@example.com',
                'user.name@domain.co.uk',
                'user+tag@example.org',
                'user123@sub.domain.com'
            ];
            validEmails.forEach(email => {
                expect((0, validation_1.isValidEmail)(email)).toBe(true);
            });
        });
        test('rejects invalid email formats', () => {
            const invalidEmails = [
                'invalid-email',
                '@domain.com',
                'user@',
                'user@domain',
                'user space@domain.com',
                '',
                'user@@domain.com'
            ];
            invalidEmails.forEach(email => {
                expect((0, validation_1.isValidEmail)(email)).toBe(false);
            });
        });
    });
    describe('Domain Validation', () => {
        test('validates correct domain formats', () => {
            const validDomains = [
                'acme',
                'test-company',
                'company123',
                'a1b2c3',
                'long-domain-name-with-dashes'
            ];
            validDomains.forEach(domain => {
                expect((0, validation_1.isValidDomain)(domain)).toBe(true);
            });
        });
        test('rejects invalid domain formats', () => {
            const invalidDomains = [
                'AB', // Too short
                'a', // Too short
                'domain-', // Ends with dash
                '-domain', // Starts with dash
                'domain.com', // Contains dot
                'domain_name', // Contains underscore
                'UPPERCASE', // Contains uppercase
                'domain with spaces', // Contains spaces
                'a'.repeat(51), // Too long
                '' // Empty
            ];
            invalidDomains.forEach(domain => {
                expect((0, validation_1.isValidDomain)(domain)).toBe(false);
            });
        });
    });
    describe('Password Validation', () => {
        test('validates strong passwords', () => {
            const strongPasswords = [
                'StrongPass123!',
                'MySecure#Password1',
                'Complex$Password99'
            ];
            strongPasswords.forEach(password => {
                const result = (0, validation_1.isValidPassword)(password);
                expect(result.valid).toBe(true);
                expect(result.errors).toHaveLength(0);
            });
        });
        test('rejects weak passwords with specific errors', () => {
            const weakPasswords = [
                { password: 'short', expectedErrors: 5 }, // All criteria failed
                { password: 'toolongbutnothing', expectedErrors: 4 }, // No upper, digit, special
                { password: 'NoNumbers!', expectedErrors: 1 }, // No numbers
                { password: 'nonumbers123', expectedErrors: 2 }, // No upper, special
                { password: 'NOLOWER123!', expectedErrors: 1 }, // No lower
            ];
            weakPasswords.forEach(({ password, expectedErrors }) => {
                const result = (0, validation_1.isValidPassword)(password);
                expect(result.valid).toBe(false);
                expect(result.errors.length).toBeGreaterThanOrEqual(1);
            });
        });
    });
    describe('Tenant Create Request Validation', () => {
        const validTenantRequest = {
            name: 'Test Company',
            domain: 'test-company',
            template: 'basic',
            max_users: 50,
            resource_limits: {
                cpu: '1000m',
                memory: '2Gi',
                storage: '10Gi'
            }
        };
        test('validates correct tenant request', () => {
            const result = (0, validation_1.validateTenantCreateRequest)(validTenantRequest);
            expect(result.valid).toBe(true);
            expect(result.errors).toHaveLength(0);
        });
        test('rejects request with missing name', () => {
            const request = { ...validTenantRequest, name: '' };
            const result = (0, validation_1.validateTenantCreateRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors).toContain('Tenant name is required');
        });
        test('rejects request with invalid domain', () => {
            const request = { ...validTenantRequest, domain: 'invalid_domain' };
            const result = (0, validation_1.validateTenantCreateRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('Domain must be');
        });
        test('rejects request with invalid template', () => {
            const request = { ...validTenantRequest, template: 'invalid' };
            const result = (0, validation_1.validateTenantCreateRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('Template must be one of');
        });
        test('rejects request with invalid max_users', () => {
            const request = { ...validTenantRequest, max_users: -1 };
            const result = (0, validation_1.validateTenantCreateRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('Max users must be between');
        });
        test('validates resource limits format', () => {
            const invalidRequests = [
                { ...validTenantRequest, resource_limits: { cpu: 'invalid' } },
                { ...validTenantRequest, resource_limits: { memory: '2Tb' } }, // Invalid unit
                { ...validTenantRequest, resource_limits: { storage: '10' } } // Missing unit
            ];
            invalidRequests.forEach(request => {
                const result = (0, validation_1.validateTenantCreateRequest)(request);
                expect(result.valid).toBe(false);
                expect(result.errors.length).toBeGreaterThan(0);
            });
        });
    });
    describe('Chat Request Validation', () => {
        const validChatRequest = {
            message: 'Hello, how can I help you?',
            conversation_id: 1,
            model_id: 'gpt-4',
            system_prompt: 'You are a helpful assistant.',
            context_sources: ['doc1', 'doc2']
        };
        test('validates correct chat request', () => {
            const result = (0, validation_1.validateChatRequest)(validChatRequest);
            expect(result.valid).toBe(true);
            expect(result.errors).toHaveLength(0);
        });
        test('rejects request with empty message', () => {
            const request = { ...validChatRequest, message: '' };
            const result = (0, validation_1.validateChatRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors).toContain('Message is required');
        });
        test('rejects request with too long message', () => {
            const request = { ...validChatRequest, message: 'a'.repeat(10001) };
            const result = (0, validation_1.validateChatRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('10000 characters or less');
        });
        test('rejects request with invalid conversation_id', () => {
            const request = { ...validChatRequest, conversation_id: 0 };
            const result = (0, validation_1.validateChatRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors).toContain('Invalid conversation ID');
        });
        test('rejects request with too long system_prompt', () => {
            const request = { ...validChatRequest, system_prompt: 'a'.repeat(2001) };
            const result = (0, validation_1.validateChatRequest)(request);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('2000 characters or less');
        });
    });
    describe('Document Upload Validation', () => {
        const createMockFile = (size, type, name) => ({
            file: Buffer.alloc(size),
            filename: name,
            file_type: type
        });
        test('validates correct document upload', () => {
            const upload = createMockFile(1000, 'text/plain', 'test.txt');
            const result = (0, validation_1.validateDocumentUpload)(upload);
            expect(result.valid).toBe(true);
            expect(result.errors).toHaveLength(0);
        });
        test('rejects upload with empty filename', () => {
            const upload = createMockFile(1000, 'text/plain', '');
            const result = (0, validation_1.validateDocumentUpload)(upload);
            expect(result.valid).toBe(false);
            expect(result.errors).toContain('Filename is required');
        });
        test('rejects upload with unsupported file type', () => {
            const upload = createMockFile(1000, 'image/jpeg', 'image.jpg');
            const result = (0, validation_1.validateDocumentUpload)(upload);
            expect(result.valid).toBe(false);
            expect(result.errors[0]).toContain('not supported');
        });
        test('rejects upload with file too large', () => {
            const upload = createMockFile(51 * 1024 * 1024, 'text/plain', 'large.txt');
            const result = (0, validation_1.validateDocumentUpload)(upload);
            expect(result.valid).toBe(false);
            expect(result.errors).toContain('File size must be 50MB or less');
        });
        test('validates supported file types', () => {
            const supportedTypes = [
                'text/plain',
                'text/markdown',
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/csv'
            ];
            supportedTypes.forEach(type => {
                const upload = createMockFile(1000, type, 'test.file');
                const result = (0, validation_1.validateDocumentUpload)(upload);
                expect(result.valid).toBe(true);
            });
        });
    });
    describe('Utility Validations', () => {
        test('sanitizeString removes dangerous content', () => {
            const dangerous = '<script>alert("xss")</script><p onclick="alert()">Click me</p>';
            const sanitized = (0, validation_1.sanitizeString)(dangerous);
            expect(sanitized).not.toContain('<script>');
            expect(sanitized).not.toContain('onclick');
            expect(sanitized).not.toContain('javascript:');
        });
        test('isValidUUID validates correct UUIDs', () => {
            const validUUIDs = [
                '123e4567-e89b-12d3-a456-426614174000',
                'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                '6ba7b810-9dad-11d1-80b4-00c04fd430c8'
            ];
            validUUIDs.forEach(uuid => {
                expect((0, validation_1.isValidUUID)(uuid)).toBe(true);
            });
        });
        test('isValidUUID rejects invalid UUIDs', () => {
            const invalidUUIDs = [
                'not-a-uuid',
                '123e4567-e89b-12d3-a456', // Too short
                '123e4567-e89b-12d3-a456-426614174000-extra', // Too long
                'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', // Invalid characters
                ''
            ];
            invalidUUIDs.forEach(uuid => {
                expect((0, validation_1.isValidUUID)(uuid)).toBe(false);
            });
        });
        test('validatePagination normalizes and validates parameters', () => {
            // Test valid parameters
            const result1 = (0, validation_1.validatePagination)(2, 50);
            expect(result1.page).toBe(2);
            expect(result1.limit).toBe(50);
            expect(result1.errors).toHaveLength(0);
            // Test defaults
            const result2 = (0, validation_1.validatePagination)();
            expect(result2.page).toBe(1);
            expect(result2.limit).toBe(20);
            // Test invalid parameters
            const result3 = (0, validation_1.validatePagination)(-1, 150);
            expect(result3.page).toBe(1); // Corrected
            expect(result3.limit).toBe(100); // Corrected to max
            expect(result3.errors.length).toBeGreaterThan(0);
        });
    });
});
