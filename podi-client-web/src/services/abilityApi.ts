import type { AbilityInvokeResponse } from '../types/ability';
import type { UploadResult } from '../types/media';
import { requestJson } from './http';
import { normalizeAbilityTask, type AbilityTask } from './clientApi';

export type AbilityInvokePayload = {
  inputs?: Record<string, unknown>;
  imageUrl?: string;
  images?: Array<{ url?: string; ossUrl?: string; name?: string }>;
};

export const abilityApi = {
  invoke(abilityId: string, payload: AbilityInvokePayload, accessToken: string) {
    return requestJson<AbilityInvokeResponse>(`/api/abilities/${abilityId}/invoke`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }, accessToken);
  },
  async createTask(abilityId: string, payload: AbilityInvokePayload, accessToken: string) {
    const response = await requestJson<Record<string, unknown>>(`/api/ability-tasks`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, abilityId }),
    }, accessToken);
    return normalizeAbilityTask(response);
  },
  async getTask(taskId: string, accessToken: string) {
    const response = await requestJson<Record<string, unknown>>(`/api/ability-tasks/${taskId}`, {}, accessToken);
    return normalizeAbilityTask(response);
  },
};

export function uploadsToImages(uploads: UploadResult[]) {
  return uploads.map((item) => ({
    url: item.url,
    ossUrl: item.url,
    name: item.name,
  }));
}
