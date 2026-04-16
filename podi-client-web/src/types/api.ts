export type AbilitySchemaField = {
  name: string;
  label?: string;
  description?: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
  advanced?: boolean;
  defaultValue?: string;
};

export type AbilityPresentation = {
  name?: string;
  summary?: string;
  formIntro?: string;
  expectedOutput?: string;
  surfaces?: {
    client?: boolean;
    coze?: boolean;
    admin?: boolean;
    eval?: boolean;
    advancedOnly?: boolean;
  };
};

export type AbilityInfo = {
  id: string;
  provider: string;
  category: string;
  capabilityKey: string;
  displayName: string;
  description?: string | null;
  inputSchema?: {
    fields?: AbilitySchemaField[];
  } | null;
  metadata?: Record<string, unknown> | null;
  presentation?: AbilityPresentation | null;
};

export type AbilityListResponse = {
  items: AbilityInfo[];
};
