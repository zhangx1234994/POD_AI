import axios from 'axios';
import { getToken } from '@/utils/http';
import type {
  AbilityInfo,
  AbilityListResponse,
  AbilityInvokePayload,
  AbilityInvokeResponse,
} from '@/types/ability';

const abilityHttp = axios.create({
  baseURL: '/api/abilities',
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json',
  },
});

abilityHttp.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const abilityApi = {
  async listAbilities(): Promise<AbilityInfo[]> {
    const res = await abilityHttp.get<AbilityListResponse>('');
    return res.data?.items || [];
  },
  async invokeAbility(abilityId: string, payload: AbilityInvokePayload): Promise<AbilityInvokeResponse> {
    const res = await abilityHttp.post<AbilityInvokeResponse>(`/${abilityId}/invoke`, payload);
    return res.data;
  },
};
