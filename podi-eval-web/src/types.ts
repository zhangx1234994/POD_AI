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
    entryMode?: string;
    resultMode?: string;
    supportsBatch?: boolean;
    recommendedRepeatCount?: number;
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
