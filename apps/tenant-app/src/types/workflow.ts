// Workflow System Type Definitions for GT 2.0

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type WorkflowStatus = 'draft' | 'active' | 'paused' | 'archived';
export type InteractionMode = 'chat' | 'button' | 'form' | 'dashboard' | 'api';
export type NodeType = 'agent' | 'trigger' | 'integration' | 'logic' | 'output';
export type TriggerType = 'manual' | 'webhook' | 'cron' | 'event' | 'api';

// Core Workflow Interfaces
export interface Workflow {
  id: string;
  name: string;
  description?: string;
  status: WorkflowStatus;
  definition: WorkflowDefinition;
  interaction_modes: InteractionMode[];
  execution_count: number;
  last_executed?: string;
  total_cost_cents: number;
  average_execution_time_ms?: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  config?: Record<string, any>;
}

export interface WorkflowNode {
  id: string;
  type: NodeType;
  position: { x: number; y: number };
  data: NodeData;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  type?: string;
  data?: Record<string, any>;
}

// Node Data Types
export interface NodeData {
  label: string;
  description?: string;
  config: Record<string, any>;
  input_schema?: FormField[];
  output_schema?: Record<string, any>;
}

export interface AgentNodeData extends NodeData {
  agent_id: string;
  agent_name: string;
  personality_type: string;
  confidence_threshold: number;
  max_tokens: number;
  temperature: number;
  capabilities: string[];
}

export interface TriggerNodeData extends NodeData {
  trigger_type: TriggerType;
  trigger_config: Record<string, any>;
  input_schema: FormField[];
}

export interface IntegrationNodeData extends NodeData {
  integration_type: string;
  integration_id?: string;
  method: string;
  endpoint?: string;
  auth_required: boolean;
  sandbox_level: string;
}

export interface LogicNodeData extends NodeData {
  logic_type: 'condition' | 'loop' | 'transform' | 'aggregate' | 'filter';
  logic_config: Record<string, any>;
}

export interface OutputNodeData extends NodeData {
  output_type: 'webhook' | 'api' | 'email' | 'storage' | 'notification';
  output_config: Record<string, any>;
}

// Execution Interfaces
export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: ExecutionStatus;
  progress_percentage: number;
  current_node_id?: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error_details?: string;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  tokens_used: number;
  cost_cents: number;
  interaction_mode: InteractionMode;
  node_executions: NodeExecution[];
}

export interface NodeExecution {
  id: string;
  node_id: string;
  node_type: NodeType;
  status: ExecutionStatus;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error_message?: string;
  tokens_used: number;
  cost_cents: number;
  is_simulated?: boolean; // For integration nodes without external connections
}

// Chat Interface Types
export interface WorkflowSession {
  id: string;
  workflow_id: string;
  status: 'active' | 'completed' | 'failed';
  messages: WorkflowMessage[];
  context: WorkflowContext;
  created_at: string;
  last_activity: string;
}

export interface WorkflowMessage {
  id: string;
  session_id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: string;
  execution_id?: string;
  node_id?: string;
  metadata?: Record<string, any>;
}

export interface WorkflowContext {
  current_node_id?: string;
  completed_nodes: string[];
  node_outputs: Record<string, any>;
  session_variables: Record<string, any>;
}

// Form Interface Types
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'email' | 'url' | 'tel' | 'password' | 'textarea' | 'select' | 'checkbox' | 'radio' | 'file' | 'date' | 'time' | 'datetime-local';
  required?: boolean;
  placeholder?: string;
  description?: string;
  default_value?: any;
  validation?: FieldValidation;
  options?: SelectOption[]; // For select, radio types
  multiple?: boolean; // For select, file types
  accept?: string; // For file type
  min?: number | string; // For number, date types
  max?: number | string; // For number, date types
  step?: number; // For number type
  pattern?: string; // For text types
}

export interface FieldValidation {
  required?: boolean;
  min_length?: number;
  max_length?: number;
  min_value?: number;
  max_value?: number;
  pattern?: string;
  custom_message?: string;
}

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface FormData {
  [key: string]: any;
}

export interface FormErrors {
  [key: string]: string[];
}

// Button Interface Types
export interface ButtonInterfaceConfig {
  button_text: string;
  button_variant: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  button_size: 'default' | 'sm' | 'lg' | 'icon';
  description?: string;
  show_stats: boolean;
  show_last_execution: boolean;
  auto_execute_on_load?: boolean;
}

// Dashboard Interface Types
export interface DashboardMetrics {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_execution_time_ms: number;
  total_cost_cents: number;
  total_tokens_used: number;
  last_24h_executions: number;
  last_7d_executions: number;
}

export interface ExecutionSummary {
  id: string;
  status: ExecutionStatus;
  started_at: string;
  duration_ms?: number;
  cost_cents: number;
  interaction_mode: InteractionMode;
  error_summary?: string;
}

// API Request/Response Types
export interface WorkflowExecutionRequest {
  input_data: Record<string, any>;
  trigger_type?: TriggerType;
  interaction_mode?: InteractionMode;
}

export interface WorkflowCreateRequest {
  name: string;
  description?: string;
  definition: WorkflowDefinition;
  triggers?: Record<string, any>[];
  interaction_modes?: InteractionMode[];
  config?: Record<string, any>;
}

export interface WorkflowUpdateRequest {
  name?: string;
  description?: string;
  definition?: WorkflowDefinition;
  status?: WorkflowStatus;
  interaction_modes?: InteractionMode[];
  config?: Record<string, any>;
}

export interface ChatMessageRequest {
  message: string;
  session_id?: string;
}

export interface ChatMessageResponse {
  session_id: string;
  user_message: {
    id: string;
    content: string;
    timestamp: string;
  };
  agent_message: {
    id: string;
    content: string;
    timestamp: string;
  };
  execution?: {
    id: string;
    status: ExecutionStatus;
  };
}

// Integration Types (for documentation - not implemented)
export interface IntegrationConfig {
  id: string;
  name: string;
  type: string;
  description?: string;
  available: boolean;
  requires_auth: boolean;
  sandbox_level: 'none' | 'basic' | 'restricted' | 'strict';
  capabilities_required: string[];
}

export interface IntegrationExecution {
  integration_id: string;
  method: string;
  endpoint: string;
  data?: Record<string, any>;
  headers?: Record<string, string>;
  timeout?: number;
}

// Error Types
export interface WorkflowError {
  code: string;
  message: string;
  details?: Record<string, any>;
  node_id?: string;
  timestamp: string;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

// Utility Types
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

// Event Types for Real-time Updates
export interface WorkflowEvent {
  type: 'execution_started' | 'execution_completed' | 'execution_failed' | 'node_started' | 'node_completed' | 'node_failed';
  workflow_id: string;
  execution_id: string;
  node_id?: string;
  data: Record<string, any>;
  timestamp: string;
}

// Component Props Types
export interface WorkflowInterfaceProps {
  workflow: Workflow;
  onExecute: (input_data: Record<string, any>) => Promise<WorkflowExecution>;
  onExecutionUpdate?: (execution: WorkflowExecution) => void;
  className?: string;
}

export interface WorkflowExecutionViewProps {
  execution: WorkflowExecution;
  workflow?: Workflow;
  onRerun?: () => void;
  onCancel?: () => void;
  realtime?: boolean;
  className?: string;
}