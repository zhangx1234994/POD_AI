export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonRecord = Record<string, JsonValue>;

export interface Executor {
  id: string;
  name: string;
  type: string;
  base_url?: string;
  status: string;
  weight: number;
  max_concurrency: number;
  health_status?: string;
  last_heartbeat_at?: string;
  config?: JsonRecord;
}

export interface Workflow {
  id: string;
  action: string;
  name: string;
  version?: string;
  type?: string;
  status?: string;
  definition?: JsonRecord;
  metadata?: JsonRecord;
  updated_at?: string;
}

export interface Binding {
  id: string;
  action: string;
  workflow_id: string;
  executor_id: string;
  priority: number;
  enabled: boolean;
}

export interface ApiKey {
  id: string;
  provider: string;
  name: string;
  status: string;
  daily_quota?: number;
  usage_count?: number;
  expire_at?: string;
  key?: string;
}

export type ExecutorFormState = Partial<Omit<Executor, 'config'>> & {
  config?: string;
};

export type WorkflowFormState = Partial<Omit<Workflow, 'definition' | 'metadata'>> & {
  definition?: string;
  metadata?: string;
};

export type BindingFormState = Partial<Binding>;

export type ApiKeyFormState = Partial<ApiKey>;

export interface Ability {
  id: string;
  provider: string;
  category: string;
  capability_key: string;
  display_name: string;
  description?: string | null;
  status: string;
  ability_type: string;
  executor_id?: string | null;
  workflow_id?: string | null;
  coze_workflow_id?: string | null;
  default_params?: JsonRecord | null;
  input_schema?: JsonRecord | null;
  metadata?: JsonRecord | null;
  last_health_check_at?: string | null;
  last_health_status?: string | null;
  success_rate?: number | null;
  created_at: string;
  updated_at: string;
}

export type AbilityFormState = Partial<Omit<Ability, 'default_params' | 'input_schema' | 'metadata'>> & {
  default_params?: string;
  input_schema?: string;
  metadata?: string;
};

export interface PublicAbility {
  id: string;
  provider: string;
  category: string;
  capabilityKey: string;
  displayName: string;
  description?: string | null;
  status: string;
  abilityType: string;
  workflowId?: string | null;
  executorId?: string | null;
  cozeWorkflowId?: string | null;
  defaultParams?: JsonRecord | null;
  inputSchema?: JsonRecord | null;
  metadata?: JsonRecord | null;
  requiresImage?: boolean;
  supportsMultipleImages?: boolean;
  maxOutputImages?: number | null;
  lastHealthCheckAt?: string | null;
  lastHealthStatus?: string | null;
  successRate?: number | null;
}

export interface AbilityListResponse {
  items: PublicAbility[];
}

export interface StoredAsset {
  ossUrl: string;
  ossKey: string;
  sourceUrl?: string | null;
  contentType?: string | null;
  size?: number | null;
  tag?: string | null;
  url?: string | null;
}

export interface AbilityInvocationLog {
  id: number;
  ability_id?: string | null;
  ability_provider: string;
  capability_key: string;
  ability_name?: string | null;
  executor_id?: string | null;
  executor_name?: string | null;
  executor_type?: string | null;
  source: string;
  task_id?: string | null;
  trace_id?: string | null;
  workflow_run_id?: string | null;
  status: string;
  duration_ms?: number | null;
  stored_url?: string | null;
  request_payload?: JsonRecord | null;
  response_payload?: JsonRecord | null;
  result_assets?: StoredAsset[] | null;
  error_message?: string | null;
  billing_unit?: string | null;
  unit_price?: number | null;
  currency?: string | null;
  cost_amount?: number | null;
  created_at: string;
}

export interface ComfyuiQueueStatus {
  executorId: string;
  baseUrl: string;
  runningCount: number;
  pendingCount: number;
  queueMaxSize?: number | null;
  supported?: boolean;
  message?: string | null;
  raw?: JsonRecord | null;
}

export interface DashboardTotals {
  total_tasks: number;
  queue_depth: number;
  pending_batches: number;
  failed_tasks: number;
}

export interface TaskStatusBucket {
  status: string;
  count: number;
}

export interface TodaySummary {
  created: number;
  completed: number;
  failed: number;
}

export interface RecentTask {
  id: string;
  user_id: string;
  tool_action: string;
  channel: string;
  status: string;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
}

export interface ExecutorHealth {
  id: string;
  name: string;
  status: string;
  health_status?: string | null;
  max_concurrency: number;
  weight: number;
  last_heartbeat_at?: string | null;
}

export interface DashboardMetrics {
  totals: DashboardTotals;
  status_buckets: TaskStatusBucket[];
  today: TodaySummary;
  recent_tasks: RecentTask[];
  executor_health: ExecutorHealth[];
}

export interface DispatchLogEntry {
  id: number;
  task_id: string;
  tool_action: string;
  task_status: string;
  event_type: string;
  payload?: JsonRecord | null;
  created_at: string;
}

export interface DispatchLogResponse {
  entries: DispatchLogEntry[];
}

export interface DatabaseConfig {
  backend: string;
  driver?: string | null;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  dsn: string;
}

export interface OssConfig {
  bucket: string;
  endpoint: string;
  public_domain?: string | null;
  root_prefix: string;
  sts_duration: number;
  role_arn?: string | null;
}

export interface SecurityConfig {
  jwt_access_ttl: number;
  jwt_refresh_ttl: number;
  upload_token_ttl: number;
}

export interface CozeConfig {
  base_url?: string | null;
  loop_base_url?: string | null;
  default_timeout: number;
  token_present: boolean;
  token_hint?: string | null;
}

export interface TodoItem {
  title: string;
  description: string;
  severity: string;
  status: string;
}

export interface SystemConfig {
  app_name: string;
  database: DatabaseConfig;
  oss: OssConfig;
  security: SecurityConfig;
  coze?: CozeConfig | null;
  feature_flags: Record<string, boolean>;
  todo_items: TodoItem[];
}

export interface AbilityLogListResponse {
  items: AbilityInvocationLog[];
}

export interface AbilityLogMetricBucket {
  ability_provider: string;
  capability_key: string;
  executor_id?: string | null;
  count: number;
  success_count: number;
  failed_count: number;
  success_rate?: number | null;
  avg_duration_ms?: number | null;
  p50_duration_ms?: number | null;
  p95_duration_ms?: number | null;
  last_success_at?: string | null;
  last_failed_at?: string | null;
}

export interface AbilityLogMetricsResponse {
  window_hours: number;
  buckets: AbilityLogMetricBucket[];
}
