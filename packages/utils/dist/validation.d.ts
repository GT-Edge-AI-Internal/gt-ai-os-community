import { TenantCreateRequest, ChatRequest, DocumentUploadRequest } from '@gt2/types';
/**
 * Validate email format
 */
export declare function isValidEmail(email: string): boolean;
/**
 * Validate domain name format
 */
export declare function isValidDomain(domain: string): boolean;
/**
 * Validate password strength
 */
export declare function isValidPassword(password: string): {
    valid: boolean;
    errors: string[];
};
/**
 * Validate tenant creation request
 */
export declare function validateTenantCreateRequest(request: TenantCreateRequest): {
    valid: boolean;
    errors: string[];
};
/**
 * Validate chat request
 */
export declare function validateChatRequest(request: ChatRequest): {
    valid: boolean;
    errors: string[];
};
/**
 * Validate file upload request
 */
export declare function validateDocumentUpload(request: DocumentUploadRequest): {
    valid: boolean;
    errors: string[];
};
/**
 * Sanitize string input to prevent injection attacks
 */
export declare function sanitizeString(input: string): string;
/**
 * Validate UUID format
 */
export declare function isValidUUID(uuid: string): boolean;
/**
 * Validate pagination parameters
 */
export declare function validatePagination(page?: number, limit?: number): {
    page: number;
    limit: number;
    errors: string[];
};
