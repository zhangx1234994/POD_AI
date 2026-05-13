export type EvalWorkflowVersion = {
  id: string;
  category: string;
  name: string;
  version: string;
  workflow_id: string;
  parameters_schema?: Record<string, unknown> | null;
  resourceBindings?: Array<{
    field: string;
    resourceType: 'lora' | 'model' | 'plugin' | string;
    source: string;
  }>;
  output_schema?: Record<string, unknown> | null;
  notes?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown> | null;
  presentation?: {
    visible?: boolean;
    sortOrder?: number;
    categoryLabel?: string;
    usageHint?: string;
    operationLabel?: string;
    variantLabel?: string;
    entryMode?: string;
    resultMode?: string;
    supportsBatch?: boolean;
    recommendedRepeatCount?: number;
    badges?: string[];
    releaseTime?: string;
    updateTime?: string;
    updateNote?: string;
  } | null;
  usage?: {
    singleRunEnabled?: boolean;
    batchEnabled?: boolean;
    docsEnabled?: boolean;
    recommendedEntry?: string;
    supportsAnnotation?: boolean;
    requiresResourceOptions?: boolean;
    resourceOptionTypes?: string[];
  } | null;
  deprecation?: {
    isDeprecated?: boolean;
    replacementWorkflowId?: string | null;
    replacementDisplayName?: string | null;
    reason?: string | null;
    retirementMode?: string | null;
  } | null;
  governance?: {
    role?: 'production' | 'candidate' | 'legacy' | 'auxiliary' | 'disabled' | string;
    roleLabel?: string;
    roleReason?: string;
    rank?: number;
    isPrimary?: boolean;
  } | null;
  routingGovernance?: EvalWorkflowRoutingGovernance | null;
};

export type EvalWorkflowRoutingGovernance = {
  abilityType: string;
  abilityTypeLabel: string;
  entryMode: string;
  entryLabel: string;
  executionSurface: string;
  executionLabel: string;
  trackingRequired: boolean;
  expectedTracking: string;
  currentTracking: string;
  currentTrackingLabel: string;
  governanceStatus: string;
  governanceLabel: string;
  notes?: string[];
};

export type EvalResourceOptionItem = {
  id: string;
  key: string;
  label: string;
  resourceType: string;
  status: string;
  description?: string;
  downloadUrl?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type EvalResourceOptionsResponse = {
  resourceType: string;
  status?: string | null;
  total: number;
  items: EvalResourceOptionItem[];
};

export type EvalRun = {
  id: string;
  workflow_version_id: string;
  status: string;
  coze_execute_id?: string | null;
  coze_debug_url?: string | null;
  podi_task_id?: string | null;
  result_image_urls_json?: string[] | null;
  result_output_json?: unknown | null;
  error_message?: string | null;
  duration_ms?: number | null;
  billing_unit?: string | null;
  unit_price?: number | null;
  currency?: string | null;
  cost_amount?: number | null;
  submit_status?: string | null;
  callback_status?: string | null;
  final_status?: string | null;
  error_code?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  parameters_json?: Record<string, unknown> | null;
  input_oss_urls_json?: string[] | null;
};

export type EvalRunListResponse = { total: number; items: EvalRun[] };

export type EvalOperationsIssue = {
  severity: 'healthy' | 'warning' | 'critical' | string;
  code: string;
  title: string;
  message: string;
  count: number;
};

export type EvalOperationsRunItem = {
  runId: string;
  workflowId?: string | null;
  workflowName?: string | null;
  category?: string | null;
  status: string;
  ageMinutes: number;
  cozeExecuteId?: string | null;
  podiTaskId?: string | null;
  imageCount: number;
  hasOutput: boolean;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type EvalOperationsHealth = {
  generatedAt: string;
  status: 'healthy' | 'warning' | 'critical' | string;
  staleMinutes: number;
  submitGraceMinutes: number;
  recentHours: number;
  recentRunTotal?: number;
  recentSuccessCount?: number;
  recentFailureCount?: number;
  concurrency?: {
    evalRunMaxWorkers?: number;
    evalComfyuiRunMaxWorkers?: number;
    evalCommercialRunMaxWorkers?: number;
    evalDefaultRunMaxWorkers?: number;
    evalFanoutMaxWorkers?: number;
    abilityTaskMaxWorkers?: number;
    comfyuiQueueBatchSize?: number;
    comfyuiAvailableExecutors?: number;
    comfyuiQueueCapacity?: number;
    comfyuiQueueTotal?: number;
    comfyuiQueueUtilization?: number | null;
  };
  activeWorkflowCount: number;
  totalWorkflowCount: number;
  statusCounts: Record<string, number>;
  recentStatusCounts: Record<string, number>;
  staleRunning: EvalOperationsRunItem[];
  submitStalled: EvalOperationsRunItem[];
  succeededWithoutOutput: EvalOperationsRunItem[];
  recentFailures: EvalOperationsRunItem[];
  errorCounts: Record<string, number>;
  issues: EvalOperationsIssue[];
};

export type ComfyuiQueueStatus = {
  executorId: string;
  baseUrl: string;
  runningCount: number;
  pendingCount: number;
  queueMaxSize?: number | null;
  supported?: boolean;
  message?: string | null;
};

export type ComfyuiQueueSummary = {
  totalRunning: number;
  totalPending: number;
  totalCount: number;
  timestamp?: string | null;
  servers: ComfyuiQueueStatus[];
};

export type SchemaField = {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  description?: string;
  options?: Array<{ label: string; value: string } | string>;
  defaultValue?: string;
};

export type WorkflowDoc = {
  category: string;
  name: string;
  workflow_id: string;
  notes?: string | null;
  output_kind?: string;
  parameters?: SchemaField[];
  outputs?: SchemaField[];
  errors?: string[];
  request?: {
    method?: string;
    path?: string;
    body?: Record<string, unknown>;
  };
};
