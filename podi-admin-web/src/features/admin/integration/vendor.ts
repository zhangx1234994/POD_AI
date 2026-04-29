import type { VendorGovernanceSummaryResponse } from '../../../types/admin';

type VendorGovernanceProviderRow = VendorGovernanceSummaryResponse['providers'][number];

const vendorIssueLabels: Record<string, string> = {
  VENDOR_API_KEY_MISSING: '缺少可用密钥',
  VENDOR_API_KEY_QUOTA_EXHAUSTED: '密钥配额已用完',
  VENDOR_API_KEY_QUOTA_NEAR_LIMIT: '密钥配额接近上限',
  VENDOR_MODEL_COST_POLICY_MISSING: '模型缺少计价',
  VENDOR_API_UNCOSTED_SUCCESS_CALLS: '成功调用未计费',
  VENDOR_API_RECENT_FAILURES: '最近调用失败',
  VENDOR_API_TASK_FAILURES: '异步任务失败',
  VENDOR_API_TASKS_QUEUED: '任务排队中',
  VENDOR_API_TASKS_RUNNING_LONG: '长时间运行',
  VENDOR_PROVIDER_REGISTRY_UNAVAILABLE: '厂商清单不可用',
  VENDOR_KEY_STATUS_UNAVAILABLE: '密钥状态不可用',
  VENDOR_USAGE_SUMMARY_UNAVAILABLE: '调用统计不可用',
  VENDOR_GOVERNANCE_DB_UNAVAILABLE: '中台目录读取失败',
  VENDOR_API_EXECUTOR_UNAVAILABLE: '能力服务不可达',
  VENDOR_API_TIMEOUT: '能力服务超时',
};

export const getVendorIssueLabel = (issue: string) => {
  const code = String(issue || '').split(':')[0];
  return vendorIssueLabels[code] || issue || '需要检查';
};

export const getVendorProviderState = (row: VendorGovernanceProviderRow) => {
  const issues = row.issues || [];
  if (issues.some((item) => item.startsWith('VENDOR_API_KEY_MISSING'))) {
    return { label: '缺密钥', theme: 'danger' as const };
  }
  if (issues.some((item) => item.startsWith('VENDOR_API_KEY_QUOTA_EXHAUSTED'))) {
    return { label: '配额用完', theme: 'danger' as const };
  }
  if (
    issues.some(
      (item) =>
        item.startsWith('VENDOR_MODEL_COST_POLICY_MISSING') ||
        item.startsWith('VENDOR_API_UNCOSTED_SUCCESS_CALLS'),
    )
  ) {
    return { label: '计费缺口', theme: 'warning' as const };
  }
  if (issues.length > 0) {
    return { label: '需检查', theme: 'warning' as const };
  }
  if (row.runtimeKeyConfigured) {
    return { label: '可调用', theme: 'success' as const };
  }
  return { label: '未配置', theme: 'warning' as const };
};
