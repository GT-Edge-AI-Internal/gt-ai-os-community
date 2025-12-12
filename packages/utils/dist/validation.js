"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isValidEmail = isValidEmail;
exports.isValidDomain = isValidDomain;
exports.isValidPassword = isValidPassword;
exports.validateTenantCreateRequest = validateTenantCreateRequest;
exports.validateChatRequest = validateChatRequest;
exports.validateDocumentUpload = validateDocumentUpload;
exports.sanitizeString = sanitizeString;
exports.isValidUUID = isValidUUID;
exports.validatePagination = validatePagination;
/**
 * Validate email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}
/**
 * Validate domain name format
 */
function isValidDomain(domain) {
    // Must be lowercase alphanumeric with hyphens, 3-50 characters
    const domainRegex = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;
    return domainRegex.test(domain);
}
/**
 * Validate password strength
 */
function isValidPassword(password) {
    const errors = [];
    if (password.length < 8) {
        errors.push('Password must be at least 8 characters long');
    }
    if (!/[A-Z]/.test(password)) {
        errors.push('Password must contain at least one uppercase letter');
    }
    if (!/[a-z]/.test(password)) {
        errors.push('Password must contain at least one lowercase letter');
    }
    if (!/[0-9]/.test(password)) {
        errors.push('Password must contain at least one number');
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        errors.push('Password must contain at least one special character');
    }
    return {
        valid: errors.length === 0,
        errors
    };
}
/**
 * Validate tenant creation request
 */
function validateTenantCreateRequest(request) {
    const errors = [];
    // Validate name
    if (!request.name || request.name.trim().length === 0) {
        errors.push('Tenant name is required');
    }
    else if (request.name.length > 100) {
        errors.push('Tenant name must be 100 characters or less');
    }
    // Validate domain
    if (!request.domain) {
        errors.push('Domain is required');
    }
    else if (!isValidDomain(request.domain)) {
        errors.push('Domain must be 3-50 characters, lowercase alphanumeric with hyphens');
    }
    // Validate template
    const validTemplates = ['basic', 'professional', 'enterprise'];
    if (request.template && !validTemplates.includes(request.template)) {
        errors.push(`Template must be one of: ${validTemplates.join(', ')}`);
    }
    // Validate max_users
    if (request.max_users !== undefined) {
        if (request.max_users < 1 || request.max_users > 10000) {
            errors.push('Max users must be between 1 and 10000');
        }
    }
    // Validate resource limits
    if (request.resource_limits) {
        if (request.resource_limits.cpu) {
            if (!/^\d+m?$/.test(request.resource_limits.cpu)) {
                errors.push('CPU limit must be in format like "1000m" or "2"');
            }
        }
        if (request.resource_limits.memory) {
            if (!/^\d+(Mi|Gi)$/.test(request.resource_limits.memory)) {
                errors.push('Memory limit must be in format like "2Gi" or "512Mi"');
            }
        }
        if (request.resource_limits.storage) {
            if (!/^\d+(Mi|Gi|Ti)$/.test(request.resource_limits.storage)) {
                errors.push('Storage limit must be in format like "10Gi" or "100Mi"');
            }
        }
    }
    return {
        valid: errors.length === 0,
        errors
    };
}
/**
 * Validate chat request
 */
function validateChatRequest(request) {
    const errors = [];
    if (!request.message || request.message.trim().length === 0) {
        errors.push('Message is required');
    }
    else if (request.message.length > 10000) {
        errors.push('Message must be 10000 characters or less');
    }
    if (request.conversation_id !== undefined && request.conversation_id < 1) {
        errors.push('Invalid conversation ID');
    }
    if (request.system_prompt && request.system_prompt.length > 2000) {
        errors.push('System prompt must be 2000 characters or less');
    }
    return {
        valid: errors.length === 0,
        errors
    };
}
/**
 * Validate file upload request
 */
function validateDocumentUpload(request) {
    const errors = [];
    if (!request.filename || request.filename.trim().length === 0) {
        errors.push('Filename is required');
    }
    else if (request.filename.length > 255) {
        errors.push('Filename must be 255 characters or less');
    }
    // Validate file type
    const allowedTypes = [
        'text/plain',
        'text/markdown',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/csv'
    ];
    if (!allowedTypes.includes(request.file_type)) {
        errors.push(`File type ${request.file_type} is not supported`);
    }
    // Check file size (assuming file is Buffer with length property)
    if (Buffer.isBuffer(request.file)) {
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (request.file.length > maxSize) {
            errors.push('File size must be 50MB or less');
        }
    }
    else if (request.file instanceof File) {
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (request.file.size > maxSize) {
            errors.push('File size must be 50MB or less');
        }
    }
    return {
        valid: errors.length === 0,
        errors
    };
}
/**
 * Sanitize string input to prevent injection attacks
 */
function sanitizeString(input) {
    return input
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '') // Remove script tags
        .replace(/javascript:/gi, '') // Remove javascript: protocol
        .replace(/on\w+\s*=\s*['"][^'"]*['"]?/gi, '') // Remove event handlers
        .trim();
}
/**
 * Validate UUID format
 */
function isValidUUID(uuid) {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
}
/**
 * Validate pagination parameters
 */
function validatePagination(page, limit) {
    const errors = [];
    let validatedPage = page || 1;
    let validatedLimit = limit || 20;
    if (validatedPage < 1) {
        errors.push('Page must be 1 or greater');
        validatedPage = 1;
    }
    if (validatedLimit < 1 || validatedLimit > 100) {
        errors.push('Limit must be between 1 and 100');
        validatedLimit = Math.min(Math.max(validatedLimit, 1), 100);
    }
    return {
        page: validatedPage,
        limit: validatedLimit,
        errors
    };
}
