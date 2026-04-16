export type AbilityAsset = {
  ossUrl?: string | null;
  sourceUrl?: string | null;
  base64?: string | null;
  type?: string | null;
  description?: string | null;
};

export type AbilityInvokeResponse = {
  abilityId: string;
  provider: string;
  status: string;
  requestId: string;
  logId?: number | null;
  durationMs?: number | null;
  images?: AbilityAsset[] | null;
  videos?: AbilityAsset[] | null;
  texts?: string[] | null;
  assets?: AbilityAsset[] | null;
  metadata?: Record<string, unknown> | null;
  raw?: Record<string, unknown> | null;
};

