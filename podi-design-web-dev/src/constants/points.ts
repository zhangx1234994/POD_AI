// 积分相关的时间常量
export const POINTS_DEDUCTION_ANIMATION_MS = 2000; // 扣减动画时长（ms）
export const POINTS_ADDITION_ANIMATION_MS = 2000; // 增加动画时长（ms）
export const POINTS_MIDNIGHT_GRANT_ANIMATION_MS = 3000; // 临时积分特效显示时长（ms）

export const POINT_CHANGE_TYPES = {
  ALL: 'all',
  // 1 = 积分获得（充值、赠送等）
  GAIN: '1',
  // 2 = 积分消耗（任务执行等）
  CONSUME: '2',
};

export const POINT_TYPES = {
  ALL: 'all',
  // 1 = 临时积分
  TEMP: '1',
  // 2 = 充值积分
  RECHARGE: '2',
};

// mapping for point change types to display labels and styles
export const POINT_CHANGE_LABELS: Record<string, { text: string; color?: string; background?: string }> = {
  [POINT_CHANGE_TYPES.GAIN]: { text: '积分获得', color: 'text-green', background: 'bg-green-500' },
  [POINT_CHANGE_TYPES.CONSUME]: { text: '积分消耗', color: 'text-red', background: 'bg-red-500' },
};

export const POINT_TYPE_LABELS: Record<string, { text: string }> = {
  [POINT_TYPES.TEMP]: { text: '临时积分' },
  [POINT_TYPES.RECHARGE]: { text: '充值积分' },
};

// mapping for operator identifiers to display names (e.g. system operator)
export const OPERATOR_LABELS: Record<string, string> = {
  system: '系统',
};

export const DEFAULT_POINTS_PAGE_SIZE = 20;

export default {
  POINTS_DEDUCTION_ANIMATION_MS,
  POINTS_ADDITION_ANIMATION_MS,
  POINTS_MIDNIGHT_GRANT_ANIMATION_MS,
  POINT_CHANGE_TYPES,
  POINT_TYPES,
  POINT_CHANGE_LABELS,
  POINT_TYPE_LABELS,
  OPERATOR_LABELS,
  DEFAULT_POINTS_PAGE_SIZE,
};
