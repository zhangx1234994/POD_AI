export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonRecord = Record<string, JsonValue>;

export interface AbilityGovernance {
  scopes?: string[];
  release_status?: string;
  route_policy?: string;
  quality_status?: string;
}

export interface AbilityBusinessStatus {
  availability_code?: string;
  availability_label?: string;
  stability_code?: string;
  stability_label?: string;
  surface_labels?: string[];
}

export interface AbilityPresentation {
  visible?: boolean;
  sort_order?: number;
  category_label?: string;
  usage_hint?: string;
  operation_label?: string;
}

export interface AbilityDeprecation {
  is_deprecated?: boolean;
  replacement_ability_id?: string | null;
  replacement_capability_key?: string | null;
  replacement_display_name?: string | null;
  reason?: string | null;
  retirement_mode?: string | null;
}

export interface ExecutorRouting {
  routing_enabled?: boolean;
  fallback_only?: boolean;
  selection_policy?: string;
  tags?: string[];
  allowed_workflow_keys?: string[];
  blocked_workflow_keys?: string[];
  concurrency_limit?: number;
}

export interface ExecutorBusinessStatus {
  execution_mode_code?: string;
  execution_mode_label?: string;
  concurrency_label?: string;
  tags?: string[];
}

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
  routing?: ExecutorRouting | null;
  business_status?: ExecutorBusinessStatus | null;
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
  version?: string | null;
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
  governance?: AbilityGovernance | null;
  presentation?: AbilityPresentation | null;
  deprecation?: AbilityDeprecation | null;
  business_status?: AbilityBusinessStatus | null;
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
  version?: string | null;
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
  ability_current_template_id?: string | null;
  ability_template_history_count?: number | null;
  ability_template_published?: boolean | null;
  executor_id?: string | null;
  executor_name?: string | null;
  executor_type?: string | null;
  source: string;
  task_id?: string | null;
  callback_id?: string | null;
  trace_id?: string | null;
  workflow_run_id?: string | null;
  status: string;
  submit_status?: string | null;
  final_status?: string | null;
  error_code?: string | null;
  duration_ms?: number | null;
  stored_url?: string | null;
  request_payload?: JsonRecord | null;
  response_payload?: JsonRecord | null;
  result_assets?: StoredAsset[] | null;
  error_message?: string | null;
  callback_status?: string | null;
  callback_http_status?: number | null;
  callback_payload?: JsonRecord | null;
  callback_response?: JsonRecord | null;
  callback_error?: string | null;
  callback_started_at?: string | null;
  callback_finished_at?: string | null;
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

export interface ComfyuiModelCatalogResponse {
  executorId: string;
  baseUrl: string;
  models: Record<string, string[]>;
  nodeKeys?: string[] | null;
  nodeCount?: number | null;
}

export interface ComfyuiQueueSummary {
  totalRunning: number;
  totalPending: number;
  totalCount: number;
  timestamp?: string | null;
  servers: ComfyuiQueueStatus[];
}

export interface ComfyuiLora {
  id: number;
  file_name: string;
  display_name: string;
  description?: string | null;
  base_model?: string | null;
  base_models?: string[] | null;
  tags?: string[] | null;
  trigger_words?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
  installed?: boolean | null;
}

export interface ComfyuiLoraCatalogResponse {
  executorId?: string | null;
  baseUrl?: string | null;
  installedFiles?: string[] | null;
  untrackedFiles?: string[] | null;
  items: ComfyuiLora[];
}

export interface ComfyuiModelCatalogItem {
  id: number;
  file_name: string;
  display_name: string;
  model_type: string;
  description?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  tags?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiModelCatalogResponse {
  items: ComfyuiModelCatalogItem[];
}

export interface ComfyuiPluginCatalogItem {
  id: number;
  node_key: string;
  display_name: string;
  package_name?: string | null;
  version?: string | null;
  description?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  tags?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiPluginCatalogResponse {
  items: ComfyuiPluginCatalogItem[];
}

export interface ComfyuiVersionCatalogItem {
  id: number;
  version: string;
  commit_sha?: string | null;
  repo_url?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  released_at?: string | null;
  notes?: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiVersionCatalogResponse {
  items: ComfyuiVersionCatalogItem[];
}

export interface ComfyuiVersionCatalogSyncResponse {
  repo_url: string;
  fetched_at: string;
  total: number;
  created: number;
  updated: number;
}

export interface ComfyuiServerDiffLog {
  id: number;
  baseline_executor_id: string;
  payload?: JsonRecord | null;
  created_at: string;
}

export interface ComfyuiAgent {
  id: string;
  name?: string | null;
  role?: string | null;
  host?: string | null;
  baseUrl?: string | null;
  base_url?: string | null;
  status?: string | null;
  allowed?: boolean | null;
  last_seen_at?: string | null;
  last_heartbeat_at?: string | null;
  last_manifest_version?: string | null;
  metrics?: JsonRecord | null;
  config?: JsonRecord | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiAgentManifest {
  id: number;
  role: string;
  version: string;
  status?: string | null;
  downloadUrl?: string | null;
  download_url?: string | null;
  content?: JsonRecord | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiManifestDriftCollection {
  expected: string[];
  reported: string[];
  missing: string[];
  extra: string[];
}

export interface ComfyuiManifestDriftResponse {
  manifestId: number;
  manifestVersion: string;
  agentId: string;
  agentLastManifestVersion?: string | null;
  sameVersion: boolean;
  hasSnapshot: boolean;
  comfyui: JsonRecord;
  models: ComfyuiManifestDriftCollection;
  plugins: ComfyuiManifestDriftCollection;
  workflows: ComfyuiManifestDriftCollection;
}

export interface ComfyuiRepairPlanItem {
  agentId: string;
  role?: string | null;
  actions: string[];
  missingItems: Record<string, string[]>;
  reason?: string | null;
}

export interface ComfyuiRepairPlan {
  manifestId: number;
  manifestVersion: string;
  mode: string;
  generatedAt: string;
  items: ComfyuiRepairPlanItem[];
  summary: {
    totalAgents: number;
    executableAgents: number;
    skippedAgents: number;
    totalActions: number;
  };
}

export interface ComfyuiRepairJobItem {
  id: number;
  agentId?: string | null;
  taskId?: string | null;
  status: string;
  submitStatus?: string | null;
  callbackStatus?: string | null;
  finalStatus?: string | null;
  actions: string[];
  missingItems: Record<string, string[]>;
  failedItems?: JsonRecord | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  updatedAt: string;
}

export interface ComfyuiRepairJob {
  id: string;
  manifestId: number;
  mode: string;
  status: string;
  requestedAgentCount: number;
  submittedTaskCount: number;
  succeededTaskCount: number;
  failedTaskCount: number;
  skippedTaskCount: number;
  createdBy?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  resultPayload?: JsonRecord | null;
  items: ComfyuiRepairJobItem[];
}

export interface ComfyuiRolePrimary {
  role: string;
  agentId?: string | null;
  baseUrl?: string | null;
  updatedAt?: string | null;
}

export interface ComfyuiMonitoringLane {
  lane: string;
  total: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  avgWaitSeconds: number;
  failureRate: number;
  retryCount: number;
}

export interface ComfyuiMonitoringSummary {
  generatedAt: string;
  windowHours: number;
  lanes: ComfyuiMonitoringLane[];
}

export interface ComfyuiMonitoringQueueItem {
  lane: string;
  provider: string;
  queued: number;
  running: number;
  total: number;
  avgWaitSeconds: number;
}

export interface ComfyuiMonitoringQueuesResponse {
  generatedAt: string;
  windowHours: number;
  items: ComfyuiMonitoringQueueItem[];
}

export interface ComfyuiMonitoringErrorItem {
  provider: string;
  stage: string;
  errorCode: string;
  count: number;
  lastOccurredAt?: string | null;
  sampleMessage?: string | null;
}

export interface ComfyuiMonitoringErrorsResponse {
  generatedAt: string;
  windowHours: number;
  items: ComfyuiMonitoringErrorItem[];
}

export interface ComfyuiRuntimePolicy {
  policyType: string;
  defaultPolicy: JsonRecord;
  laneOverrides: JsonRecord;
  nodeOverrides: JsonRecord;
  notes?: string | null;
  updatedAt: string;
}

export interface ComfyuiResourceOption {
  id: string;
  key: string;
  label: string;
  resourceType: string;
  status: string;
  description?: string | null;
  downloadUrl?: string | null;
  metadata?: JsonRecord | null;
}

export interface ComfyuiResourceOptionsResponse {
  resourceType: string;
  status?: string | null;
  total: number;
  items: ComfyuiResourceOption[];
}

export interface ComfyuiAgentTask {
  id: string;
  agentId: string;
  manifestId?: number | null;
  manifestUrl?: string | null;
  actions?: string[] | null;
  status: string;
  submitStatus?: string | null;
  callbackStatus?: string | null;
  finalStatus?: string | null;
  errorCode?: string | null;
  tokenNonce?: string | null;
  pushedAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  requestPayload?: JsonRecord | null;
  resultPayload?: JsonRecord | null;
  errorMessage?: string | null;
  expiresAt?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiAgentTaskEvent {
  id: number;
  taskId: string;
  level: string;
  message: string;
  payload?: JsonRecord | null;
  eventTime?: string | null;
  created_at?: string;
}

export interface ComfyuiAgentAlert {
  id: number;
  agentId: string;
  alertType: string;
  message: string;
  payload?: JsonRecord | null;
  created_at?: string;
}

export interface ComfyuiAgentTokenResponse {
  token: string;
  expiresAt: string;
  scope: string;
  agentId: string;
}

export interface ComfyuiEnrollCode {
  id: number;
  code: string;
  role: string;
  status: string;
  note?: string | null;
  maxUses: number;
  usedCount: number;
  expiresAt: string;
  usedAt?: string | null;
  usedByAgentId?: string | null;
  createdBy?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ComfyuiDesktopRelease {
  id: number;
  channel: string;
  version: string;
  osType: string;
  arch: string;
  status: string;
  downloadUrl: string;
  sha256: string;
  minAgentVersion?: string | null;
  notes?: string | null;
  payload?: JsonRecord | null;
  publishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DashboardTotals {
  total_tasks: number;
  queue_depth: number;
  pending_batches: number;
  failed_tasks: number;
}

export interface QueueOverview {
  total_pending: number;
  total_running: number;
  task_pending: number;
  task_running: number;
  ability_pending: number;
  ability_running: number;
  eval_pending: number;
  eval_running: number;
  pending_batches: number;
  pending_batch_tasks: number;
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
  queue_overview: QueueOverview;
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
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
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
  total_cost?: number | null;
  avg_cost?: number | null;
  last_success_at?: string | null;
  last_failed_at?: string | null;
}

export interface AbilityLogCostSummary {
  key: string;
  count: number;
  total_cost?: number | null;
  avg_cost?: number | null;
}

export interface AbilityLogMetricsResponse {
  window_hours: number;
  total_count?: number | null;
  total_success_count?: number | null;
  total_failed_count?: number | null;
  uncosted_count?: number | null;
  total_cost?: number | null;
  avg_cost_per_call?: number | null;
  provider_totals?: AbilityLogCostSummary[];
  currency_totals?: AbilityLogCostSummary[];
  buckets: AbilityLogMetricBucket[];
}

export interface AbilityTemplateSnapshot {
  id: string;
  version_label?: string | null;
  action: string;
  created_at: string;
  notes?: string | null;
  default_params?: JsonRecord | null;
  input_schema?: JsonRecord | null;
  metadata?: JsonRecord | null;
}

export interface AbilityTemplateStateResponse {
  ability_id: string;
  current_template_id?: string | null;
  history: AbilityTemplateSnapshot[];
}

export interface AbilityTemplateValidateResponse {
  ok: boolean;
  errors: string[];
  warnings: string[];
}
