// ========== 用户相关常量 ==========
import { CheckCircle2, XCircle, Clock, Shield, Trash2, Sparkles, Star } from 'lucide-react';

/** 用户中心页签配置 */
export const USER_CENTER_TABS = [
  { value: 'profile', label: '账号信息' },
  { value: 'linkedPlatforms', label: '平台绑定' },
  { value: 'usageStats', label: '使用统计' },
  { value: 'securitySettings', label: '安全设置' },
];

/** 默认用户信息对象（用于初始化或兜底） */
export const DEFAULT_USER_INFO = {
  id: 0,
  user_id: '',
  username: '未知用户',
  nickname: '请设置昵称',
  email: '未设置邮箱',
  avatar: '',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  role: 'USER',
};

/** 账号状态到 UI 展示配置的映射（包含图标引用） */
export const ACCOUNT_STATUS_UI_MAP = {
  active: {
    label: '正常',
    icon: CheckCircle2,
    textClass: 'text-green-600',
    borderClass: 'border-green-600',
  },
  inactive: {
    label: '未激活',
    icon: XCircle,
    textClass: 'text-slate-700',
    borderClass: 'border-slate-300',
  },
  pending: {
    label: '待处理',
    icon: Clock,
    textClass: 'text-amber-800',
    borderClass: 'border-amber-400',
  },
  suspended: {
    label: '已暂停',
    icon: Shield,
    textClass: 'text-amber-900',
    borderClass: 'border-amber-600',
  },
  banned: {
    label: '封禁',
    icon: XCircle,
    textClass: 'text-rose-800',
    borderClass: 'border-rose-600',
  },
  deleted: {
    label: '已删除',
    icon: Trash2,
    textClass: 'text-slate-600',
    borderClass: 'border-slate-300',
  },
};

/** 会员等级到 UI 展示配置的映射（包含图标引用） */
export const MEMBERSHIP_LEVEL_UI_MAP = {
  vip: {
    label: 'VIP',
    icon: Sparkles,
    textClass: 'text-amber-800',
    borderClass: 'border-amber-400',
    bgClass: 'bg-amber-50',
  },
  regular: {
    label: '普通',
    icon: Star,
    textClass: 'text-slate-700',
    borderClass: 'border-slate-300',
    bgClass: 'bg-slate-50',
  },
};

/** 账号状态别名映射，用于解析各种输入形式 */
export const ACCOUNT_STATUS_ALIAS_MAP = {
  active: 'active',
  normal: 'active',
  正常: 'active',
  inactive: 'inactive',
  未激活: 'inactive',
  pending: 'pending',
  待定: 'pending',
  待处理: 'pending',
  suspended: 'suspended',
  暂停: 'suspended',
  suspended_account: 'suspended',
  banned: 'banned',
  blocked: 'banned',
  封禁: 'banned',
  deleted: 'deleted',
  closed: 'deleted',
  已删除: 'deleted',
} as const; // 使用 as const 保证类型精确

/** 游客用户信息常量 */
export const GUEST_USER_INFO = {
  id: undefined,
  user_id: undefined,
  username: 'guest',
  nickname: 'Guest',
  email: undefined,
  mobile: undefined,
  platform: undefined,
  avatar: undefined,
  createdAt: undefined,
  updatedAt: undefined,
  role: 'USER',
} as const;

export default {
  USER_CENTER_TABS,
  DEFAULT_USER_INFO,
  ACCOUNT_STATUS_UI_MAP,
  MEMBERSHIP_LEVEL_UI_MAP,
  ACCOUNT_STATUS_ALIAS_MAP,
  GUEST_USER_INFO,
};
