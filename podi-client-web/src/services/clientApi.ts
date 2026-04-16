import type { AbilityListResponse } from '../types/api';
import { requestJson } from './http';

export type WalletBalance = {
  userId: string;
  balance: number;
  frozenBalance: number;
  currency: string;
};

export type WalletStatistics = {
  totalPoints: number;
  tempPoints: number;
  frozenPoints: number;
  grantedToday: number;
};

export type WalletUsageSummary = {
  userId: string;
  windowDays: number;
  totalExpensePoints: number;
  totalIncomePoints: number;
  expenseCount: number;
  incomeCount: number;
};

export type WalletLedgerItem = {
  id: string;
  changeType: string;
  points: number;
  beforeBalance: number;
  afterBalance: number;
  taskId?: string | null;
  description?: string | null;
  createdAt?: string | null;
};

export type WalletLedgerResponse = {
  userId: string;
  page: number;
  pageSize: number;
  total: number;
  items: WalletLedgerItem[];
};

export type RechargeOrderResponse = {
  orderNo: string;
  userId: string;
  amount: number;
  channel: string;
  status: string;
  createdAt: string;
  paidAt?: string | null;
  failReason?: string | null;
  transactionId?: string | null;
  updatedAt?: string | null;
};

export type AbilityTask = {
  id: string;
  abilityId: string;
  abilityName?: string | null;
  provider: string;
  capabilityKey?: string | null;
  status: string;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  requestPayload?: Record<string, unknown> | null;
  resultPayload?: Record<string, unknown> | null;
};

export type AbilityTaskListResponse = {
  items: AbilityTask[];
};

type AbilityTaskWire = Partial<AbilityTask> & {
  ability_id?: string;
  ability_name?: string | null;
  ability_provider?: string;
  capability_key?: string | null;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
  request_payload?: Record<string, unknown> | null;
  result_payload?: Record<string, unknown> | null;
};

export function normalizeAbilityTask(task: AbilityTaskWire): AbilityTask {
  return {
    id: String(task.id || ''),
    abilityId: String(task.abilityId || task.ability_id || ''),
    abilityName: task.abilityName ?? task.ability_name ?? null,
    provider: String(task.provider || task.ability_provider || ''),
    capabilityKey: task.capabilityKey ?? task.capability_key ?? null,
    status: String(task.status || ''),
    errorMessage: task.errorMessage ?? task.error_message ?? null,
    createdAt: String(task.createdAt || task.created_at || ''),
    updatedAt: String(task.updatedAt || task.updated_at || ''),
    requestPayload:
      (task.requestPayload as Record<string, unknown> | null | undefined) ??
      (task.request_payload as Record<string, unknown> | null | undefined) ??
      null,
    resultPayload: task.resultPayload ?? task.result_payload ?? null,
  };
}

export const clientApi = {
  listAbilities(accessToken?: string) {
    return requestJson<AbilityListResponse>('/api/abilities', {}, accessToken);
  },
  async listAbilityTasks(accessToken: string, limit = 20) {
    const response = await requestJson<{ items?: AbilityTaskWire[] }>(`/api/ability-tasks?limit=${limit}`, {}, accessToken);
    return {
      items: Array.isArray(response.items) ? response.items.map(normalizeAbilityTask) : [],
    };
  },
  getWalletBalance(userId: string) {
    return requestJson<WalletBalance>(`/api/wallet/v1/balance?userId=${encodeURIComponent(userId)}`);
  },
  getWalletStatistics(userId: string) {
    return requestJson<WalletStatistics>(`/api/wallet/v1/statistics?userId=${encodeURIComponent(userId)}`);
  },
  getWalletUsageSummary(userId: string, windowDays = 30) {
    return requestJson<WalletUsageSummary>(
      `/api/wallet/v1/usage-summary?userId=${encodeURIComponent(userId)}&windowDays=${windowDays}`,
    );
  },
  getWalletLedger(userId: string, page = 1, pageSize = 20) {
    return requestJson<WalletLedgerResponse>(
      `/api/wallet/v1/ledger?userId=${encodeURIComponent(userId)}&page=${page}&pageSize=${pageSize}`,
    );
  },
  createRechargeOrder(userId: string, amount: number, channel = 'manual') {
    return requestJson<RechargeOrderResponse>(`/api/wallet/v1/recharge-orders`, {
      method: 'POST',
      body: JSON.stringify({ userId, amount, channel }),
    });
  },
  getRechargeOrder(orderNo: string) {
    return requestJson<RechargeOrderResponse>(`/api/wallet/v1/recharge-orders/${encodeURIComponent(orderNo)}`);
  },
};
