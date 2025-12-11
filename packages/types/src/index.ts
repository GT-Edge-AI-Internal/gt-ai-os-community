// GT 2.0 Shared TypeScript Types

// Authentication & Authorization
export interface Capability {
  resource: string;
  actions: string[];
  constraints?: {
    valid_until?: string;
    ip_restrictions?: string[];
    usage_limits?: {
      max_requests_per_hour?: number;
      max_tokens_per_request?: number;
    };
  };
}

export interface JWTPayload {
  sub: string;
  tenant_id?: string;
  user_type: 'super_admin' | 'tenant_admin' | 'tenant_user';
  capabilities: Capability[];
  capability_hash: string;
  exp: number;
  iat: number;
}

export interface User {
  id: number;
  uuid: string;
  email: string;
  full_name: string;
  user_type: 'super_admin' | 'tenant_admin' | 'tenant_user';
  tenant_id?: number;
  capabilities: Capability[];
  is_active: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

// Tenant Management
export interface Tenant {
  id: number;
  uuid: string;
  name: string;
  domain: string;
  template: string;
  status: 'pending' | 'deploying' | 'active' | 'suspended' | 'terminated';
  max_users: number;
  resource_limits: {
    cpu: string;
    memory: string;
    storage: string;
    max_users?: number;
  };
  namespace: string;
  subdomain: string;
  database_path?: string;
  created_at: string;
  updated_at: string;
}

export interface TenantCreateRequest {
  name: string;
  domain: string;
  template?: string;
  max_users?: number;
  resource_limits?: {
    cpu?: string;
    memory?: string;
    storage?: string;
  };
}

// AI Resources
export interface AIResource {
  id: number;
  uuid: string;
  name: string;
  resource_type: 'llm' | 'embedding' | 'image_generation';
  provider: string;
  model_name: string;
  api_endpoint?: string;
  configuration: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantResource {
  id: number;
  tenant_id: number;
  resource_id: number;
  usage_limits: {
    max_requests_per_hour: number;
    max_tokens_per_request: number;
  };
  is_enabled: boolean;
  created_at: string;
}

// Chat & Conversations
export interface Conversation {
  id: number;
  title: string;
  model_id: string;
  system_prompt?: string;
  created_by: string;
  created_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'agent' | 'system';
  content: string;
  model_used?: string;
  tokens_used?: number;
  context_sources?: string[];
  created_at: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: number;
  model_id?: string;
  system_prompt?: string;
  context_sources?: string[];
}

export interface ChatResponse {
  message: Message;
  conversation: Conversation;
  tokens_used: number;
  context_sources?: DocumentChunk[];
}

// Document Processing
export interface Document {
  id: number;
  filename: string;
  file_type: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  uploaded_by: string;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: number;
  content: string;
  metadata: Record<string, any>;
  embedding?: number[];
  similarity_score?: number;
}

export interface DocumentUploadRequest {
  file: File | Buffer;
  filename: string;
  file_type: string;
}

// Usage & Billing
export interface UsageRecord {
  id: number;
  tenant_id: number;
  resource_id: number;
  user_email: string;
  request_type: string;
  tokens_used: number;
  cost_cents: number;
  metadata: Record<string, any>;
  created_at: string;
}

export interface UsageSummary {
  tenant_id: number;
  period: 'hour' | 'day' | 'month';
  total_requests: number;
  total_tokens: number;
  total_cost_cents: number;
  by_resource: Record<string, {
    requests: number;
    tokens: number;
    cost_cents: number;
  }>;
}

// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
  meta?: {
    page?: number;
    limit?: number;
    total?: number;
  };
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  meta: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

// WebSocket Types
export interface WebSocketMessage {
  type: 'chat_message' | 'chat_response' | 'typing_start' | 'typing_stop' | 'error';
  conversation_id?: number;
  data: any;
  timestamp: string;
}

// System Configuration
export interface SystemConfig {
  tenant_templates: Record<string, {
    name: string;
    description: string;
    resource_limits: {
      cpu: string;
      memory: string;
      storage: string;
    };
    features: string[];
  }>;
  ai_providers: Record<string, {
    name: string;
    api_endpoint: string;
    models: string[];
  }>;
}

// Audit & Security
export interface AuditLog {
  id: number;
  user_id?: number;
  tenant_id?: number;
  action: string;
  resource_type?: string;
  resource_id?: string;
  details: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}