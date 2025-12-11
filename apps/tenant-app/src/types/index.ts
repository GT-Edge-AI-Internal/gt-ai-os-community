// Core GT 2.0 Tenant Application Types

export interface User {
  id: number;
  email: string;
  full_name?: string;
  role?: 'admin' | 'developer' | 'analyst' | 'student';
  user_type?: 'tenant_user' | 'tenant_admin';
  tenant_id?: number;
  capabilities?: Capability[];
  preferences?: UserPreferences;
  created_at?: string;
  updated_at?: string;
  is_active?: boolean;
}

export interface Capability {
  resource: string;
  actions: string[];
  constraints?: Record<string, any>;
}

export interface UserPreferences {
  ui_preferences: {
    theme?: 'light' | 'dark' | 'auto';
    compact_mode?: boolean;
    sidebar_collapsed?: boolean;
  };
  ai_preferences: {
    default_model?: string;
    temperature?: number;
    max_tokens?: number;
    system_prompt?: string;
  };
  notification_preferences: {
    email_enabled?: boolean;
    in_app_enabled?: boolean;
    security_alerts?: boolean;
  };
}

export interface Conversation {
  id: number;
  uuid: string;
  title: string;
  model_id: string;
  system_prompt?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message_at?: string;
}

export interface Message {
  id: number;
  uuid: string;
  conversation_id: number;
  role: 'user' | 'agent' | 'system';
  content: string;
  model_used?: string;
  tokens_used?: number;
  context_sources?: string[];
  created_at: string;
  streaming?: boolean;
  response_time?: number; // Response time in seconds

  // Agentic metadata
  phaseMetadata?: {
    phases: Array<{
      phase: AgenticPhase;
      startTime: Date;
      endTime?: Date;
      duration?: number;
    }>;
    totalExecutionTime?: number;
    complexityLevel?: 'simple' | 'moderate' | 'complex';
  };

  toolCalls?: ToolExecution[];
  subagentActivity?: SubagentExecution[];
  sourceRetrievals?: SourceRetrieval[];

  // Enhanced source attribution
  sources?: Array<{
    id: string;
    type: 'document' | 'dataset' | 'conversation' | 'web';
    name: string;
    relevance: number;
    content?: string;
    metadata?: Record<string, any>;
  }>;
}

export interface Document {
  id: number;
  uuid: string;
  filename: string;
  file_type: string;
  file_size: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
  error_message?: string;
}

export interface AIResource {
  id: number;
  uuid: string;
  name: string;
  description?: string;
  resource_type: 'ai_ml' | 'rag_engine' | 'agentic_workflow' | 'app_integration' | 'external_service' | 'ai_literacy';
  resource_subtype?: string;
  provider: string;
  model_name?: string;
  personalization_mode: 'shared' | 'user_scoped' | 'session_based';
  primary_endpoint?: string;
  iframe_url?: string;
  configuration: Record<string, any>;
  health_status: 'healthy' | 'unhealthy' | 'unknown';
  is_active: boolean;
  max_requests_per_minute: number;
  max_tokens_per_request: number;
  cost_per_1k_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface ChatState {
  currentConversation: Conversation | null;
  conversations: Conversation[];
  messages: Message[];
  isLoading: boolean;
  isTyping: boolean;
  isExecutingTools: boolean;
  currentTool?: string;
  error: string | null;
  connected: boolean;

  // Unread message tracking
  unreadCounts: Record<string, number>;

  // Agentic state tracking
  currentPhase: AgenticPhase;
  phaseStartTime?: Date;
  activeTools: ToolExecution[];
  subagentActivity: SubagentExecution[];
  sourceRetrieval: SourceRetrieval[];

  // Execution metadata
  taskComplexity?: 'simple' | 'moderate' | 'complex';
  orchestrationStrategy?: string;
  totalPhases?: number;
  completedPhases?: number;
}

export interface FileUpload {
  file: File;
  id: string;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

// Agentic execution phases
export type AgenticPhase =
  | 'idle'
  | 'thinking'
  | 'planning'
  | 'tool_execution'
  | 'subagent_orchestration'
  | 'source_retrieval'
  | 'responding'
  | 'completed';

// Tool execution states
export interface ToolExecution {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime?: Date;
  endTime?: Date;
  progress?: number;
  arguments?: Record<string, any>;
  result?: any;
  error?: string;
}

// Subagent execution for complex tasks
export interface SubagentExecution {
  id: string;
  type: string;
  task: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  startTime?: Date;
  endTime?: Date;
  dependsOn?: string[];
  result?: any;
  error?: string;
}

// Source retrieval information
export interface SourceRetrieval {
  id: string;
  type: 'dataset' | 'conversation' | 'web';
  query: string;
  status: 'searching' | 'found' | 'failed';
  results?: Array<{
    id: string;
    name: string;
    relevance: number;
    content?: string;
    metadata?: Record<string, any>;
  }>;
}

export interface WebSocketMessage {
  type:
    | 'message'
    | 'typing'
    | 'error'
    | 'status'
    | 'phase_start'
    | 'phase_transition'
    | 'tool_execution'
    | 'subagent_status'
    | 'source_retrieval'
    | 'phase_complete';
  data: any;
  conversation_id?: number;
  timestamp: string;
  // Additional fields for agentic events
  phase?: AgenticPhase;
  toolExecution?: ToolExecution;
  subagentStatus?: SubagentExecution;
  sourceRetrieval?: SourceRetrieval;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface TenantInfo {
  id: number;
  name: string;
  domain: string;
  status: 'active' | 'pending' | 'suspended';
  template: string;
  max_users: number;
  current_users: number;
  resource_limits: Record<string, any>;
  created_at: string;
}

export interface UsageStats {
  api_calls_today: number;
  tokens_used_today: number;
  conversations_today: number;
  documents_processed_today: number;
  cost_today_cents: number;
  monthly_usage: {
    api_calls: number;
    tokens_used: number;
    cost_cents: number;
  };
}

// UI Component Props Types
export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  children: React.ReactNode;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export interface InputProps {
  label?: string;
  error?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
  type?: 'text' | 'email' | 'password' | 'number';
  className?: string;
}

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  children: React.ReactNode;
}

// Theme and Settings
export interface ThemeConfig {
  colors: {
    primary: string;
    accent: string;
    success: string;
    warning: string;
    error: string;
    gray: Record<string, string>;
  };
  typography: {
    fontFamily: {
      sans: string[];
      mono: string[];
    };
    fontSize: Record<string, string>;
    fontWeight: Record<string, number>;
  };
  spacing: Record<string, string>;
  borderRadius: Record<string, string>;
  shadows: Record<string, string>;
}