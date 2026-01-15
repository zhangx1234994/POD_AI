export type AbilitySchemaFieldOption =
  | string
  | {
      label: string;
      value: string;
    };

export type AbilitySchemaField = {
  name: string;
  type: 'text' | 'textarea' | 'select' | 'number' | 'switch' | 'image';
  label: string;
  description?: string;
  placeholder?: string;
  default?: string | number | boolean;
  defaultValue?: string | number | boolean;
  required?: boolean;
  options?: AbilitySchemaFieldOption[];
};

export type AbilitySchema = {
  fields?: AbilitySchemaField[];
};

export type AbilityMetadata = Record<string, unknown> & {
  api_type?: string;
  workflow_key?: string;
  model_id?: string;
  requires_image_input?: boolean;
  supports_multiple_outputs?: boolean;
  max_output_images?: number;
};

export interface AbilityInfo {
  id: string;
  provider: string;
  category: string;
  capabilityKey: string;
  displayName: string;
  description?: string | null;
  status: string;
  executorId?: string | null;
  defaultParams?: Record<string, unknown> | null;
  inputSchema?: AbilitySchema | null;
  metadata?: AbilityMetadata | null;
  requiresImage?: boolean;
  supportsMultipleImages?: boolean;
  maxOutputImages?: number | null;
}

export interface AbilityListResponse {
  items: AbilityInfo[];
}

export interface AbilityInvokeImage {
  name?: string;
  url?: string;
  ossUrl?: string;
  base64?: string;
}

export interface AbilityInvokePayload {
  executorId?: string;
  inputs?: Record<string, unknown>;
  imageUrl?: string;
  imageBase64?: string;
  images?: AbilityInvokeImage[];
  metadata?: Record<string, unknown>;
  callbackUrl?: string;
  callbackHeaders?: Record<string, string>;
}

export interface AbilityOutputAsset {
  ossUrl?: string | null;
  sourceUrl?: string | null;
  base64?: string | null;
  type?: string | null;
  description?: string | null;
  tag?: string | null;
}

export interface AbilityInvokeResponse {
  abilityId: string;
  provider: string;
  status: string;
  requestId: string;
  logId?: number | null;
  durationMs?: number | null;
  images?: AbilityOutputAsset[] | null;
  videos?: AbilityOutputAsset[] | null;
  texts?: string[] | null;
  assets?: AbilityOutputAsset[] | null;
  metadata?: Record<string, unknown> | null;
  raw?: Record<string, unknown> | null;
}
