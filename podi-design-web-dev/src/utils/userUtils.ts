import {
  ACCOUNT_STATUS_UI_MAP,
  MEMBERSHIP_LEVEL_UI_MAP,
  ACCOUNT_STATUS_ALIAS_MAP
} from '@/constants/user';

// 类型别名（不变）
export type AccountStatus = keyof typeof ACCOUNT_STATUS_UI_MAP;
export type MembershipLevel = keyof typeof MEMBERSHIP_LEVEL_UI_MAP;

/**
 * 将原始账号状态值标准化为系统定义的 AccountStatus
 */
export function normalizeAccountStatus(raw?: string): AccountStatus {
  if (!raw) return 'active';
  const key = String(raw).trim().toLowerCase();
  return ACCOUNT_STATUS_ALIAS_MAP[key as keyof typeof ACCOUNT_STATUS_ALIAS_MAP] ??
         (key in ACCOUNT_STATUS_UI_MAP ? (key as AccountStatus) : 'active');
}

/**
 * 将原始会员等级值标准化为系统定义的 MembershipLevel
 */
export function normalizeMembershipLevel(raw?: string): MembershipLevel {
  if (!raw) return 'regular';
  const key = String(raw).trim().toLowerCase();
  if (key.includes('vip') || key === 'admin') return 'vip';
  if (['regular', '普通', 'user'].includes(key)) return 'regular';
  return 'regular';
}

export default {
  normalizeAccountStatus,
  normalizeMembershipLevel,
}
