export type EvalWorkflowPresentation = {
  visible?: boolean;
  sortOrder?: number;
  categoryLabel?: string;
  usageHint?: string;
  operationLabel?: string;
  entryMode?: string;
  resultMode?: string;
  supportsBatch?: boolean;
  recommendedRepeatCount?: number;
};

export type EvalWorkflowUsage = {
  singleRunEnabled?: boolean;
  batchEnabled?: boolean;
  docsEnabled?: boolean;
  recommendedEntry?: string;
  supportsAnnotation?: boolean;
  requiresResourceOptions?: boolean;
  resourceOptionTypes?: string[];
};

export type EvalWorkflowDeprecation = {
  isDeprecated?: boolean;
  replacementWorkflowId?: string | null;
  replacementDisplayName?: string | null;
  reason?: string | null;
  retirementMode?: string;
};

export type EvalWorkflowVersion = {
  id: string;
  category: string;
  name: string;
  version: string;
  coze_base_url?: string | null;
  workflow_id: string;
  parameters_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  presentation?: EvalWorkflowPresentation | null;
  usage?: EvalWorkflowUsage | null;
  deprecation?: EvalWorkflowDeprecation | null;
  notes?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type EvalDatasetItem = {
  id: string;
  category: string;
  name: string;
  oss_url: string;
  meta_json?: Record<string, unknown> | null;
  created_by: string;
  created_at: string;
};

export type EvalRun = {
  id: string;
  workflow_version_id: string;
  dataset_item_id?: string | null;
  input_oss_urls_json?: string[] | null;
  parameters_json?: Record<string, unknown> | null;
  status: string;
  coze_execute_id?: string | null;
  coze_debug_url?: string | null;
  podi_task_id?: string | null;
  result_image_urls_json?: string[] | null;
  error_message?: string | null;
  duration_ms?: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type EvalRunListResponse = {
  total: number;
  items: EvalRun[];
};

export type EvalRunPurgeResponse = {
  deleted_runs: number;
  deleted_annotations: number;
};

export type EvalAnnotation = {
  id: string;
  run_id: string;
  rating: number;
  tags_json?: string[] | null;
  comment?: string | null;
  created_by: string;
  created_at: string;
};
