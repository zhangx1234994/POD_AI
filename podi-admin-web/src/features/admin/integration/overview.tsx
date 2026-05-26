import { Fragment, useState } from 'react';
import { Alert, Button, Card, Col, Input, Row, Space, Tag, Typography } from 'tdesign-react';
import type {
  AbilityHealthSummaryResponse,
  BusinessCapability,
  BusinessUsageSummaryResponse,
  DashboardMetrics,
  DashboardStrategyIndicator,
  HealthWatchStatusResponse,
  HealthWatchUnitStatus,
  ReleaseDecisionRecordResponse,
  ReleasePreflightCheck,
  ReleasePatrolRecordResponse,
  ReleasePreflightResponse,
  StrategySnapshotResponse,
  WeeklyReportResponse,
} from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import {
  businessCapabilityLatestRunLabel,
  businessCapabilityRunMetricsLabel,
  businessKeyLabel,
  canonicalBusinessKey,
  coreBusinessKeys,
} from './businessLabels';
import { buildCoreBusinessReleaseEvidenceRows } from './businessReleaseEvidence';
import { formatCurrencyTotals, formatDateTime, formatRatePercent } from './formatters';
import { moduleGuides } from './moduleGuides';
import { integrationNavItems, type IntegrationNavId } from './navigation';

function MetricCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <Card bordered className="podi-metric-card">
      <Space direction="vertical" size="small">
        <Typography.Text theme="secondary">{label}</Typography.Text>
        <Typography.Title level="h2" style={{ margin: 0 }}>
          {value}
        </Typography.Title>
        {sub ? <Typography.Text theme="secondary">{sub}</Typography.Text> : null}
      </Space>
    </Card>
  );
}

type PatrolFailedItem = {
  name: string;
  workflowId: string;
  runId: string;
  status: string;
  podiTaskId: string;
  error: string;
};

type PatrolHealthEvidence = PatrolFailedItem & {
  finalStatus: string;
  callbackStatus: string;
  cozeExecuteId: string;
  imageCount: number;
  hasOutput: boolean;
  issueCode: string;
  healthStatus: string;
};

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function patrolText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
}

function patrolNumber(record: ReleasePatrolRecordResponse, key: string): number {
  const value = record.summary?.[key];
  return typeof value === 'number' ? value : 0;
}

function patrolFailedItems(record: ReleasePatrolRecordResponse): PatrolFailedItem[] {
  const rawItems = record.summary?.failedItems;
  if (!Array.isArray(rawItems)) return [];
  const items: PatrolFailedItem[] = [];
  for (const rawItem of rawItems) {
    if (!isPlainRecord(rawItem)) continue;
    const item = rawItem as Record<string, unknown>;
    const failedItem = {
      name: patrolText(item.name),
      workflowId: patrolText(item.workflowId),
      runId: patrolText(item.runId),
      status: patrolText(item.status),
      podiTaskId: patrolText(item.podiTaskId),
      error: patrolText(item.error),
    };
    if (failedItem.name || failedItem.workflowId || failedItem.runId || failedItem.podiTaskId || failedItem.error) {
      items.push(failedItem);
    }
  }
  return items;
}

function patrolHealthEvidence(record: ReleasePatrolRecordResponse): PatrolHealthEvidence[] {
  const rawItems = record.summary?.abilityHealthEvidence;
  if (!Array.isArray(rawItems)) return [];
  const items: PatrolHealthEvidence[] = [];
  for (const rawItem of rawItems) {
    if (!isPlainRecord(rawItem)) continue;
    const item = rawItem as Record<string, unknown>;
    const imageCountValue = item.imageCount;
    const imageCount = typeof imageCountValue === 'number' ? imageCountValue : Number(imageCountValue || 0) || 0;
    const hasOutputValue = item.hasOutput;
    const evidence = {
      name: patrolText(item.name),
      workflowId: patrolText(item.workflowId),
      runId: patrolText(item.runId),
      status: patrolText(item.status),
      finalStatus: patrolText(item.finalStatus),
      callbackStatus: patrolText(item.callbackStatus),
      cozeExecuteId: patrolText(item.cozeExecuteId),
      podiTaskId: patrolText(item.podiTaskId),
      imageCount,
      hasOutput: typeof hasOutputValue === 'boolean' ? hasOutputValue : imageCount > 0,
      issueCode: patrolText(item.issueCode) || 'UNKNOWN',
      healthStatus: patrolText(item.healthStatus) || 'unknown',
      error: patrolText(item.error),
    };
    if (evidence.name || evidence.workflowId || evidence.runId || evidence.podiTaskId || evidence.issueCode) {
      items.push(evidence);
    }
  }
  return items;
}

function patrolHealthTag(item: PatrolHealthEvidence): { theme: 'success' | 'danger' | 'warning' | 'default'; text: string } {
  if (item.issueCode === 'OK' || item.healthStatus === 'healthy') return { theme: 'success', text: '通过' };
  if (item.issueCode === 'EVAL_SUCCEEDED_WITHOUT_OUTPUT') return { theme: 'warning', text: '无结果' };
  return { theme: 'danger', text: '失败' };
}

function weeklyReportStatusLabel(status: string): string {
  if (status === 'sent') return '已发送';
  if (status === 'failed') return '发送失败';
  if (status === 'not_sent') return '仅生成';
  return status || '未知';
}

function weeklyReportStatusTheme(status: string): 'success' | 'danger' | 'default' {
  if (status === 'sent') return 'success';
  if (status === 'failed') return 'danger';
  return 'default';
}

function releasePreflightCheckLabel(status: string): string {
  if (status === 'pass') return '正常';
  if (status === 'warn') return '提醒';
  if (status === 'fail') return '异常';
  return status || '未知';
}

function releasePreflightCheckTheme(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'pass') return 'success';
  if (status === 'warn') return 'warning';
  if (status === 'fail') return 'danger';
  return 'default';
}

function healthWatchStatusLabel(status: string): string {
  if (status === 'healthy') return '正常';
  if (status === 'running') return '运行中';
  if (status === 'failed') return '异常';
  if (status === 'disabled') return '未启用';
  if (status === 'unavailable') return '未安装';
  return status || '未知';
}

function healthWatchStatusTheme(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'healthy') return 'success';
  if (status === 'running') return 'warning';
  if (status === 'failed' || status === 'disabled') return 'danger';
  if (status === 'unavailable') return 'default';
  return 'default';
}

function releaseDecisionStatusLabel(status: string): string {
  if (status === 'approved') return '确认可上线';
  if (status === 'deferred') return '暂缓上线';
  if (status === 'blocked') return '阻塞上线';
  return status || '未知';
}

function releaseDecisionStatusTheme(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'approved') return 'success';
  if (status === 'deferred') return 'warning';
  if (status === 'blocked') return 'danger';
  return 'default';
}

function releasePreflightCheckByName(
  snapshot: ReleasePreflightResponse | null,
  name: string,
): ReleasePreflightCheck | null {
  return snapshot?.checks?.find((check) => check.name === name) || null;
}

function strategyIndicatorStatusLabel(status?: string): string {
  if (status === 'healthy') return '达标';
  if (status === 'warning') return '需关注';
  if (status === 'critical') return '阻塞';
  return status || '待判断';
}

function strategyIndicatorTheme(status?: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'healthy') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'critical') return 'danger';
  return 'default';
}

function strategyIndicatorAlertTheme(status?: string): 'success' | 'warning' | 'error' | 'info' {
  if (status === 'healthy') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'critical') return 'error';
  return 'info';
}

function businessReleaseGateStatusLabel(status?: string | null): string {
  if (status === 'ready') return '可上线';
  if (status === 'warning') return '需复核';
  if (status === 'blocked') return '暂不能上线';
  return '未判断';
}

function businessAcceptanceLabel(status?: string | null): string {
  if (status === 'passed') return '验收通过';
  if (status === 'failed') return '验收失败';
  if (status === 'warning') return '有风险';
  if (status === 'waived') return '暂不验收';
  return '未验收';
}

function businessAcceptanceTheme(status?: string | null): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'passed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'warning') return 'warning';
  return 'default';
}

function readinessIssueTarget(title: string): OverviewNavTarget {
  if (title.includes('主业务') || title.includes('业务')) return 'business';
  if (title.includes('模型')) return 'vendor-models';
  if (title.includes('能力')) return 'abilities';
  if (title.includes('账单') || title.includes('计费') || title.includes('成本')) return 'billing';
  if (title.includes('巡检') || title.includes('评测')) return 'ability-evals';
  return 'overview';
}

type OverviewSummary = {
  executors: number;
  activeExecutors: number;
  workflows: number;
  bindings: number;
  apiKeys: number;
  abilities: number;
};

type OverviewNavTarget = IntegrationNavId;

type OverviewPanelProps = {
  dashboardMetrics?: DashboardMetrics | null;
  pendingQueueTotal: number;
  businessUsageSummary?: BusinessUsageSummaryResponse | null;
  coreBusinessOverviewItems: BusinessCapability[];
  abilityHealthSummary?: AbilityHealthSummaryResponse | null;
  vendorModelCount: number;
  vendorKeyCount: number;
  vendorUsageFailed: number;
  vendorGovernanceIssueCount: number;
  strategySnapshots: StrategySnapshotResponse[];
  strategySnapshotLoading: boolean;
  strategySnapshotError?: string | null;
  weeklyReports: WeeklyReportResponse[];
  weeklyReportLoading: boolean;
  weeklyReportError?: string | null;
  releasePreflightLatest?: ReleasePreflightResponse | null;
  releasePreflightSnapshots: ReleasePreflightResponse[];
  releasePreflightLoading: boolean;
  releasePreflightError?: string | null;
  healthWatchStatus?: HealthWatchStatusResponse | null;
  healthWatchLoading: boolean;
  healthWatchError?: string | null;
  releasePatrolRecords: ReleasePatrolRecordResponse[];
  releasePatrolLoading: boolean;
  releasePatrolError?: string | null;
  releaseDecisionRecords: ReleaseDecisionRecordResponse[];
  releaseDecisionLoading: boolean;
  releaseDecisionError?: string | null;
  summary: OverviewSummary;
  loading: boolean;
  onRefresh: () => void;
  onCreateStrategySnapshot: () => void;
  onRefreshStrategySnapshots: () => void;
  onRunWeeklyReport: (send: boolean) => void;
  onRefreshWeeklyReports: () => void;
  onRunReleasePreflight: () => void;
  onRefreshReleasePreflight: () => void;
  onRefreshHealthWatchStatus: () => void;
  onCreateReleasePatrolRecord: (status: 'passed' | 'failed') => void;
  onImportReleasePatrolReport: (reportPath: string) => void;
  onRefreshReleasePatrolRecords: () => void;
  onCreateReleaseDecisionRecord: (payload: {
    status: 'approved' | 'deferred' | 'blocked';
    title: string;
    note?: string;
    summary?: Record<string, unknown>;
  }) => void;
  onRefreshReleaseDecisionRecords: () => void;
  onCopyText?: (value: string) => void;
  onOpenEvalRun?: (runId: string) => void;
  onNavigate?: (target: OverviewNavTarget) => void;
};

export function OverviewPanel({
  dashboardMetrics,
  pendingQueueTotal,
  businessUsageSummary,
  coreBusinessOverviewItems,
  abilityHealthSummary,
  vendorModelCount,
  vendorKeyCount,
  vendorUsageFailed,
  vendorGovernanceIssueCount,
  strategySnapshots,
  strategySnapshotLoading,
  strategySnapshotError,
  weeklyReports,
  weeklyReportLoading,
  weeklyReportError,
  releasePreflightLatest,
  releasePreflightSnapshots,
  releasePreflightLoading,
  releasePreflightError,
  healthWatchStatus,
  healthWatchLoading,
  healthWatchError,
  releasePatrolRecords,
  releasePatrolLoading,
  releasePatrolError,
  releaseDecisionRecords,
  releaseDecisionLoading,
  releaseDecisionError,
  summary,
  loading,
  onRefresh,
  onCreateStrategySnapshot,
  onRefreshStrategySnapshots,
  onRunWeeklyReport,
  onRefreshWeeklyReports,
  onRunReleasePreflight,
  onRefreshReleasePreflight,
  onRefreshHealthWatchStatus,
  onCreateReleasePatrolRecord,
  onImportReleasePatrolReport,
  onRefreshReleasePatrolRecords,
  onCreateReleaseDecisionRecord,
  onRefreshReleaseDecisionRecords,
  onCopyText,
  onOpenEvalRun,
  onNavigate,
}: OverviewPanelProps) {
  const [releasePatrolReportPath, setReleasePatrolReportPath] = useState('');
  const [releaseDecisionNote, setReleaseDecisionNote] = useState('');
  const strategySummary = dashboardMetrics?.strategy_summary;
  const strategyNorthStar = strategySummary?.north_star || null;
  const strategyIndicators: DashboardStrategyIndicator[] = strategySummary?.indicators || [];
  const latestWeeklyReport = weeklyReports[0] || null;
  const fullPatrolCommand =
    'python3 backend/scripts/patrol_eval_workflows.py --base-url http://127.0.0.1:8099 --timeout 1800 --report reports/eval_patrol_$(date +%Y%m%d_%H%M%S).json';
  const preflightLatest = releasePreflightLatest || releasePreflightSnapshots[0] || null;
  const healthWatchItems = healthWatchStatus?.items || [];
  const healthWatchUnsupported = healthWatchStatus?.supported === false;
  const healthWatchProblemItems = healthWatchUnsupported
    ? []
    : healthWatchItems.filter((item) => ['failed', 'disabled', 'unavailable'].includes(item.status));
  const healthWatchRunningItems = healthWatchItems.filter((item) => item.status === 'running');
  const healthWatchSummaryTheme =
    healthWatchUnsupported
      ? 'warning'
      : healthWatchProblemItems.length > 0
        ? 'danger'
        : healthWatchRunningItems.length > 0
          ? 'warning'
          : healthWatchItems.length > 0
            ? 'success'
            : 'default';
  const healthWatchSummaryText =
    healthWatchUnsupported
      ? '本地不可读'
      : healthWatchProblemItems.length > 0
      ? `异常 ${healthWatchProblemItems.length}`
      : healthWatchRunningItems.length > 0
        ? `运行中 ${healthWatchRunningItems.length}`
        : healthWatchItems.length > 0
          ? '守护正常'
          : '待检查';
  const latestPatrolRecord = releasePatrolRecords[0] || null;
  const latestPatrolEvidence = latestPatrolRecord ? patrolHealthEvidence(latestPatrolRecord) : [];
  const latestPatrolFailedEvidence = latestPatrolEvidence.filter((item) => item.issueCode !== 'OK' && item.healthStatus !== 'healthy');
  const latestPatrolOutputReady = latestPatrolEvidence.filter((item) => item.hasOutput).length;
  const latestReleaseDecision = releaseDecisionRecords[0] || null;
  const preflightBlocked = Number(preflightLatest?.blockingCount || 0);
  const preflightWarnings = Number(preflightLatest?.warningCount || 0);
  const releaseCronChecks = [
    releasePreflightCheckByName(preflightLatest, 'weekly_report_cron'),
    releasePreflightCheckByName(preflightLatest, 'billing_collection_cron'),
  ].filter((check): check is ReleasePreflightCheck => Boolean(check));
  const releaseCoreChecks = [
    releasePreflightCheckByName(preflightLatest, 'business_capability_governance'),
    releasePreflightCheckByName(preflightLatest, 'auth_scope_summary'),
    releasePreflightCheckByName(preflightLatest, 'internal_tasks_get'),
    releasePreflightCheckByName(preflightLatest, 'comfyui_queue_summary'),
  ].filter((check): check is ReleasePreflightCheck => Boolean(check));
  const releaseCronRiskMessages = releaseCronChecks
    .filter((check) => check.status !== 'pass')
    .map((check) => `${check.title}：${check.detail || '需要处理'}`);
  const releaseCoreFailedMessages = releaseCoreChecks
    .filter((check) => check.status === 'fail')
    .map((check) => `${check.title}：${check.detail || '需要处理'}`);
  const releaseCoreWarningMessages = releaseCoreChecks
    .filter((check) => check.status === 'warn')
    .map((check) => `${check.title}：${check.detail || '需要处理'}`);
  const preflightTheme = !preflightLatest
    ? 'default'
    : preflightBlocked > 0
      ? 'danger'
      : preflightWarnings > 0
        ? 'warning'
        : 'success';
  const preflightLabel = !preflightLatest
    ? '未巡检'
    : preflightBlocked > 0
      ? `阻塞 ${preflightBlocked}`
      : preflightWarnings > 0
        ? `提醒 ${preflightWarnings}`
        : '可发版';
  const guardMessages = [
    preflightBlocked > 0 ? `轻量门禁存在 ${preflightBlocked} 个阻塞项` : '',
    latestPatrolRecord?.status === 'failed' ? `最近完整巡检失败：${latestPatrolRecord.note || latestPatrolRecord.reportPath || '请查看巡检报告'}` : '',
  ].filter(Boolean);
  const activeDefaultBusinessKeys = new Set(
    coreBusinessOverviewItems
      .filter((item) => item.isDefault && item.status === 'active')
      .map((item) => canonicalBusinessKey(item.businessKey)),
  );
  const coreBusinessReleaseRows = buildCoreBusinessReleaseEvidenceRows({
    capabilities: coreBusinessOverviewItems,
    summary: businessUsageSummary,
  });
  const coreBusinessReleaseBlockedRows = coreBusinessReleaseRows.filter((row) => row.theme === 'danger');
  const coreBusinessReleaseWarningRows = coreBusinessReleaseRows.filter((row) => row.theme === 'warning');
  const missingCoreBusinessLabels = coreBusinessKeys
    .filter((key) => !activeDefaultBusinessKeys.has(key))
    .map((key) => businessKeyLabel(key));
  const businessFailedCount = Number(businessUsageSummary?.failed || 0);
  const businessUnresolvedIssueCount = Number(
    (businessUsageSummary?.unresolvedIssues || []).reduce((total, bucket) => total + Number(bucket.total || 0), 0),
  );
  const businessPathLoading = loading && coreBusinessOverviewItems.length === 0;
  const vendorPathLoading = loading && vendorModelCount === 0 && vendorKeyCount === 0;
  const abilityPathLoading = loading && !abilityHealthSummary && Number(summary.abilities || 0) === 0;
  const abilityRiskCount =
    Number(abilityHealthSummary?.failed || 0) +
    Number(abilityHealthSummary?.degraded || 0) +
    Number(abilityHealthSummary?.needsTestCount || 0);
  const operationPathItems: Array<{
    step: string;
    title: string;
    body: string;
    status: string;
    theme: 'success' | 'warning' | 'danger' | 'default';
    action: string;
    target: OverviewNavTarget;
  }> = [
    {
      step: '1',
      title: '先定业务入口',
      body: '确认花纹提取、图裂变、扩图都有 active 默认版本，业务方只认这里的稳定入口。',
      status: businessPathLoading
        ? '加载中'
          : missingCoreBusinessLabels.length > 0
            ? `缺 ${missingCoreBusinessLabels.join('、')}`
          : businessUnresolvedIssueCount > 0
            ? `待确认 ${businessUnresolvedIssueCount}`
            : '入口完整',
      theme: businessPathLoading
        ? 'default'
        : missingCoreBusinessLabels.length > 0
          ? 'danger'
          : businessUnresolvedIssueCount > 0
            ? 'warning'
            : 'success',
      action: '进入业务能力',
      target: 'business',
    },
    {
      step: '2',
      title: '再看模型弹药',
      body: '检查商业模型、密钥、出网和最近失败样本；模型不稳定时不要绑定到业务默认版本。',
      status: vendorPathLoading
        ? '加载中'
        : vendorKeyCount <= 0
          ? '缺密钥'
          : vendorGovernanceIssueCount > 0
            ? `问题 ${vendorGovernanceIssueCount}`
            : vendorUsageFailed > 0
              ? `失败 ${vendorUsageFailed}`
              : `模型 ${vendorModelCount}`,
      theme: vendorPathLoading ? 'default' : vendorKeyCount <= 0 ? 'warning' : vendorGovernanceIssueCount > 0 || vendorUsageFailed > 0 ? 'warning' : 'success',
      action: '检查模型弹药库',
      target: 'vendor-models',
    },
    {
      step: '3',
      title: '核对原子能力',
      body: '确认能力分类、输入字段、默认线路和最近健康状态；底层细节不要暴露给业务方。',
      status: abilityPathLoading
        ? '加载中'
        : abilityHealthSummary
          ? abilityRiskCount > 0
            ? `需处理 ${abilityRiskCount}`
            : '能力正常'
          : `能力 ${summary.abilities || 0}`,
      theme: abilityPathLoading ? 'default' : abilityRiskCount > 0 ? 'warning' : 'success',
      action: '查看能力目录',
      target: 'abilities',
    },
    {
      step: '4',
      title: '最后做真实测评',
      body: '发版前用测评端或巡检脚本跑真实链路，确认 Coze 到中台再到能力服务的结果入库闭环。',
      status: latestPatrolRecord ? (latestPatrolRecord.status === 'passed' ? '最近通过' : '最近失败') : '待巡检',
      theme: latestPatrolRecord?.status === 'failed' ? 'danger' : latestPatrolRecord?.status === 'passed' ? 'success' : 'default',
      action: '进入能力评测',
      target: 'ability-evals',
    },
  ];
  const operationPathLoading = operationPathItems.some((item) => item.status === '加载中');
  const operationPathHasBlocker = operationPathItems.some((item) => item.theme === 'danger');
  const operationPathHasWarning = operationPathItems.some((item) => item.theme === 'warning');
  const callbackFailedCount = Number(businessUsageSummary?.callbackFailed || 0);
  const releaseReadinessItems: Array<{
    title: string;
    status: string;
    detail: string;
    theme: 'success' | 'warning' | 'danger' | 'default';
  }> = [
    {
      title: '主业务上线证据',
      status: businessPathLoading
        ? '加载中'
        : coreBusinessReleaseBlockedRows.length > 0
          ? `阻塞 ${coreBusinessReleaseBlockedRows.length}`
          : coreBusinessReleaseWarningRows.length > 0
            ? `需确认 ${coreBusinessReleaseWarningRows.length}`
            : '通过',
      detail: businessPathLoading
        ? '正在加载三条主业务的默认版本、验收和最近样本。'
        : coreBusinessReleaseBlockedRows.length > 0
          ? coreBusinessReleaseBlockedRows
              .slice(0, 3)
              .map((row) => `${businessKeyLabel(row.businessKey)}：${row.reason}`)
              .join('；')
          : coreBusinessReleaseWarningRows.length > 0
            ? coreBusinessReleaseWarningRows
                .slice(0, 3)
                .map((row) => `${businessKeyLabel(row.businessKey)}：${row.reason}`)
                .join('；')
            : '三条主业务默认版本均具备上线证据。',
      theme: businessPathLoading
        ? 'default'
        : coreBusinessReleaseBlockedRows.length > 0
          ? 'danger'
          : coreBusinessReleaseWarningRows.length > 0
            ? 'warning'
            : 'success',
    },
    {
      title: '业务入口',
      status: businessPathLoading
        ? '加载中'
        : missingCoreBusinessLabels.length > 0
          ? '阻塞'
          : businessUnresolvedIssueCount > 0 || callbackFailedCount > 0
            ? '需处理'
            : '通过',
      detail: businessPathLoading
        ? '正在加载默认版本和最近调用。'
        : missingCoreBusinessLabels.length > 0
          ? `缺少 ${missingCoreBusinessLabels.join('、')} 的 active 默认版本。`
          : businessUnresolvedIssueCount > 0
            ? `近 ${businessUsageSummary?.windowHours || 24} 小时还有 ${businessUnresolvedIssueCount} 条失败未确认恢复。`
            : callbackFailedCount > 0
              ? `当前还有 ${callbackFailedCount} 次回调失败。`
              : '三大主业务默认入口完整，最近无明显失败。',
      theme: businessPathLoading
        ? 'default'
        : missingCoreBusinessLabels.length > 0 || businessUnresolvedIssueCount > 0 || callbackFailedCount > 0
          ? 'danger'
          : 'success',
    },
    {
      title: '轻量门禁',
      status: !preflightLatest ? '待运行' : preflightBlocked > 0 ? '阻塞' : preflightWarnings > 0 ? '提醒' : '通过',
      detail: !preflightLatest
        ? '上线前需要先运行轻量门禁。'
        : preflightBlocked > 0
          ? `${preflightBlocked} 个阻塞项需要处理。`
          : preflightWarnings > 0
            ? `${preflightWarnings} 个提醒项，需确认是否可接受。`
            : `最近检查通过：${formatDateTime(preflightLatest.generatedAt)}`,
      theme: !preflightLatest ? 'warning' : preflightBlocked > 0 ? 'danger' : preflightWarnings > 0 ? 'warning' : 'success',
    },
    {
      title: '自检守护',
      status: healthWatchUnsupported
        ? '本地不可读'
        : healthWatchProblemItems.length > 0
        ? '阻塞'
        : healthWatchRunningItems.length > 0
          ? '运行中'
          : healthWatchItems.length > 0
            ? '通过'
            : '待检查',
      detail: healthWatchUnsupported
        ? '当前是本地或非 systemd 环境，不作为本地阻塞；上线前仍需在 114 服务器确认定时巡检。'
        : healthWatchProblemItems.length > 0
        ? healthWatchProblemItems.slice(0, 2).map((item) => `${item.title}：${item.summary}`).join('；')
        : healthWatchRunningItems.length > 0
          ? `当前有 ${healthWatchRunningItems.length} 个自检任务正在执行，稍后刷新确认结果。`
          : healthWatchItems.length > 0
            ? '业务轻量自检、真实巡检和评测健康守护均已纳入页面检查。'
            : '尚未读取到线上自检守护状态，上线前需要确认 114 定时巡检是否运行。',
      theme: healthWatchUnsupported
        ? 'warning'
        : healthWatchProblemItems.length > 0
        ? 'danger'
        : healthWatchRunningItems.length > 0 || healthWatchItems.length === 0
          ? 'warning'
          : 'success',
    },
    {
      title: '完整巡检',
      status: !latestPatrolRecord ? '待登记' : latestPatrolRecord.status === 'passed' ? '通过' : '阻塞',
      detail: !latestPatrolRecord
        ? '上线前需要跑一次真实工作流巡检，并登记结果。'
        : latestPatrolRecord.status === 'passed'
          ? `最近完整巡检通过：${formatDateTime(latestPatrolRecord.generatedAt)}`
          : latestPatrolRecord.note || latestPatrolRecord.reportPath || '最近完整巡检失败，请先查看报告。',
      theme: !latestPatrolRecord ? 'warning' : latestPatrolRecord.status === 'passed' ? 'success' : 'danger',
    },
    {
      title: '模型与能力',
      status: vendorGovernanceIssueCount > 0 || vendorUsageFailed > 0 || abilityRiskCount > 0 ? '提醒' : '通过',
      detail:
        vendorGovernanceIssueCount > 0 || vendorUsageFailed > 0 || abilityRiskCount > 0
          ? `模型问题 ${vendorGovernanceIssueCount}，模型调用失败 ${vendorUsageFailed}，能力需处理 ${abilityRiskCount}。`
          : '模型弹药库和能力目录当前没有明显阻塞。',
      theme: vendorGovernanceIssueCount > 0 || vendorUsageFailed > 0 || abilityRiskCount > 0 ? 'warning' : 'success',
    },
  ];
  const releaseReadinessHasLoading = releaseReadinessItems.some((item) => item.status === '加载中');
  const releaseReadinessBlockers = releaseReadinessItems.filter((item) => item.theme === 'danger');
  const releaseReadinessWarnings = releaseReadinessItems.filter((item) => item.theme === 'warning');
  const baseReleaseReadinessTitle = releaseReadinessHasLoading
    ? '正在加载'
    : releaseReadinessBlockers.length > 0
      ? '发版需处理'
      : releaseReadinessWarnings.length > 0
        ? '待验收确认'
        : '可以上线';
  const baseReleaseReadinessTheme = releaseReadinessHasLoading
    ? 'default'
    : releaseReadinessBlockers.length > 0
      ? 'danger'
      : releaseReadinessWarnings.length > 0
        ? 'warning'
        : 'success';
  const baseReleaseReadinessMessage = releaseReadinessHasLoading
    ? '正在加载业务、门禁和巡检数据，加载完成后再判断。'
    : releaseReadinessBlockers.length > 0
      ? `发版门禁还有 ${releaseReadinessBlockers.length} 个事项：${releaseReadinessBlockers.map((item) => item.title).join('、')}。这表示上线前要补证据，不等同于当前业务不可用。`
      : releaseReadinessWarnings.length > 0
        ? `还需要确认 ${releaseReadinessWarnings.length} 个事项：${releaseReadinessWarnings.map((item) => item.title).join('、')}。确认后再安排线上闭环。`
        : '业务入口、轻量门禁、完整巡检和能力状态都已满足上线前检查要求。';
  const latestReleaseDecisionApproved =
    !releaseReadinessHasLoading &&
    releaseReadinessBlockers.length === 0 &&
    latestReleaseDecision?.status === 'approved';
  const releaseReadinessTitle = latestReleaseDecisionApproved ? '已确认可上线' : baseReleaseReadinessTitle;
  const releaseReadinessTheme = latestReleaseDecisionApproved
    ? releaseReadinessWarnings.length > 0
      ? 'warning'
      : 'success'
    : baseReleaseReadinessTheme;
  const releaseReadinessMessage = latestReleaseDecisionApproved
    ? releaseReadinessWarnings.length > 0
      ? `已登记可上线，仍有 ${releaseReadinessWarnings.length} 个非阻断提醒：${releaseReadinessWarnings
          .map((item) => item.title)
          .join('、')}。这些提醒进入后续治理，不阻塞本次发布。`
      : '已登记可上线，业务入口、轻量门禁、完整巡检和能力状态都已满足上线前检查要求。'
    : baseReleaseReadinessMessage;
  const releaseAttentionItems = releaseReadinessBlockers.length > 0 ? releaseReadinessBlockers : releaseReadinessWarnings;
  const businessTotal = Number(strategySummary?.business_total || businessUsageSummary?.total || 0);
  const strategyRiskCount = Number(strategySummary?.risk_count || 0);
  const billingPendingCount = Number(strategySummary?.billing_pending || strategySummary?.unpriced || 0);
  const walletRiskCount = Number(strategySummary?.wallet_failed || 0);
  const callbackRiskCount = Number(strategySummary?.callback_failed || callbackFailedCount || 0);
  const queueRiskCount = Number(pendingQueueTotal || 0);
  const backendLogRegressionCheck = releasePreflightCheckByName(preflightLatest, 'backend_log_regression');
  const comfyuiQueueSummaryCheck = releasePreflightCheckByName(preflightLatest, 'comfyui_queue_summary');
  const todayFailedCount = Number(dashboardMetrics?.today.failed || 0);
  const stabilitySignals: Array<{
    key: string;
    title: string;
    status: string;
    detail: string;
    action: string;
    target: OverviewNavTarget;
    theme: 'success' | 'warning' | 'danger' | 'default';
  }> = [
    {
      key: 'health-watch',
      title: '自检守护',
      status: healthWatchUnsupported
        ? '本地不可读'
        : healthWatchProblemItems.length > 0
          ? `异常 ${healthWatchProblemItems.length}`
          : healthWatchRunningItems.length > 0
            ? `运行中 ${healthWatchRunningItems.length}`
            : healthWatchItems.length > 0
              ? '正常'
              : '待检查',
      detail: healthWatchUnsupported
        ? '本地环境无法读取 systemd，发布前在 114 确认。'
        : healthWatchProblemItems.length > 0
          ? healthWatchProblemItems.slice(0, 2).map((item) => `${item.title}：${item.summary || '异常'}`).join('；')
          : healthWatchRunningItems.length > 0
            ? '守护任务正在执行，等待完成后刷新。'
            : healthWatchItems.length > 0
              ? '定时自检、真实巡检和评测健康已纳入观察。'
              : '尚未读取守护状态，先刷新或到 114 查看。',
      action: '看守护状态',
      target: 'overview',
      theme: healthWatchUnsupported
        ? 'warning'
        : healthWatchProblemItems.length > 0
          ? 'danger'
          : healthWatchRunningItems.length > 0 || healthWatchItems.length === 0
            ? 'warning'
            : 'success',
    },
    {
      key: 'backend-pool',
      title: '后端连接池',
      status: backendLogRegressionCheck ? releasePreflightCheckLabel(backendLogRegressionCheck.status) : '待扫描',
      detail: backendLogRegressionCheck
        ? backendLogRegressionCheck.detail || 'release smoke 已扫描近期 backend journal。'
        : '运行轻量门禁后会扫描 QueuePool 和 finalize loop 回归日志。',
      action: '运行轻量门禁',
      target: 'overview',
      theme: backendLogRegressionCheck ? releasePreflightCheckTheme(backendLogRegressionCheck.status) : 'warning',
    },
    {
      key: 'business-runs',
      title: '业务运行',
      status:
        businessUnresolvedIssueCount > 0
          ? `未恢复 ${businessUnresolvedIssueCount}`
          : callbackRiskCount > 0
            ? `回调失败 ${callbackRiskCount}`
            : todayFailedCount > 0
              ? `今日失败 ${todayFailedCount}`
              : '无明显异常',
      detail:
        businessUnresolvedIssueCount > 0
          ? `近 ${businessUsageSummary?.windowHours || 24} 小时仍有失败未确认恢复。`
          : callbackRiskCount > 0
            ? '业务方可能收不到结果，先核对回调地址和重试记录。'
            : todayFailedCount > 0
              ? '今日存在失败样本，确认是否已被后续成功覆盖。'
              : '当前窗口业务运行没有明确阻塞。',
      action: '看业务运行',
      target: 'business',
      theme: businessUnresolvedIssueCount > 0 || callbackRiskCount > 0 ? 'danger' : todayFailedCount > 0 ? 'warning' : 'success',
    },
    {
      key: 'comfyui-queue',
      title: 'ComfyUI 队列',
      status: comfyuiQueueSummaryCheck
        ? releasePreflightCheckLabel(comfyuiQueueSummaryCheck.status)
        : queueRiskCount > 0
          ? `排队 ${queueRiskCount}`
          : '待门禁',
      detail: comfyuiQueueSummaryCheck
        ? comfyuiQueueSummaryCheck.detail || '队列、下发和 backend running 状态已检查。'
        : queueRiskCount > 0
          ? '当前有排队任务，确认 4090/5090/158 线路是否在消化。'
          : '运行轻量门禁后可看到队列和回填收敛状态。',
      action: '看 ComfyUI',
      target: 'comfyui-management',
      theme: comfyuiQueueSummaryCheck
        ? releasePreflightCheckTheme(comfyuiQueueSummaryCheck.status)
        : queueRiskCount > 0
          ? 'warning'
          : 'default',
    },
  ];
  const stabilityDangerSignals = stabilitySignals.filter((item) => item.theme === 'danger');
  const stabilityWarningSignals = stabilitySignals.filter((item) => item.theme === 'warning' || item.theme === 'default');
  const stabilityAlertTheme =
    stabilityDangerSignals.length > 0 ? 'error' : stabilityWarningSignals.length > 0 ? 'warning' : 'success';
  const stabilitySummaryTitle =
    stabilityDangerSignals.length > 0
      ? `需处理 ${stabilityDangerSignals.length} 项`
      : stabilityWarningSignals.length > 0
        ? `需确认 ${stabilityWarningSignals.length} 项`
        : '当前稳定';
  const stabilitySummaryMessage =
    stabilityDangerSignals.length > 0
      ? stabilityDangerSignals.map((item) => item.title).join('、')
      : stabilityWarningSignals.length > 0
        ? stabilityWarningSignals.map((item) => item.title).join('、')
        : '自检、连接池日志、业务运行和 ComfyUI 队列没有明显异常。';
  const executivePillars: Array<{
    key: string;
    title: string;
    status: string;
    detail: string;
    action: string;
    target: OverviewNavTarget;
    theme: 'success' | 'warning' | 'danger' | 'default';
  }> = [
    {
      key: 'release',
      title: '上线',
      status: releaseReadinessTitle,
      detail: releaseReadinessMessage,
      action: '查看上线结论',
      target: 'ability-evals',
      theme: releaseReadinessTheme,
    },
    {
      key: 'business',
      title: '业务',
      status: missingCoreBusinessLabels.length > 0 ? `缺 ${missingCoreBusinessLabels.length} 个入口` : `主业务 ${activeDefaultBusinessKeys.size}/3`,
      detail:
        missingCoreBusinessLabels.length > 0
          ? `先补齐 ${missingCoreBusinessLabels.join('、')} 的默认版本。`
          : businessUnresolvedIssueCount > 0
            ? `近 ${businessUsageSummary?.windowHours || 24} 小时仍有 ${businessUnresolvedIssueCount} 条失败未确认恢复。`
            : businessTotal > 0
              ? `近 ${strategySummary?.window_hours || businessUsageSummary?.windowHours || 24} 小时已有 ${businessTotal} 次业务调用。`
              : '当前窗口暂无业务调用，发版前仍需跑真实巡检。',
      action: '看业务能力',
      target: 'business',
      theme: missingCoreBusinessLabels.length > 0 || businessUnresolvedIssueCount > 0 ? 'danger' : businessTotal > 0 ? 'success' : 'warning',
    },
    {
      key: 'ability',
      title: '能力',
      status: abilityRiskCount > 0 ? `需处理 ${abilityRiskCount}` : `能力 ${summary.abilities || 0}`,
      detail:
        abilityRiskCount > 0
          ? '能力健康存在异常、降级或需要复测，先处理后再绑定到主业务。'
          : vendorGovernanceIssueCount > 0
            ? `模型弹药库还有 ${vendorGovernanceIssueCount} 个治理问题。`
            : '原子能力和模型治理当前没有明显阻塞。',
      action: abilityRiskCount > 0 ? '看能力目录' : '看模型弹药',
      target: abilityRiskCount > 0 ? 'abilities' : 'vendor-models',
      theme: abilityRiskCount > 0 || vendorGovernanceIssueCount > 0 ? 'warning' : 'success',
    },
    {
      key: 'cost',
      title: '成本',
      status: billingPendingCount > 0 || walletRiskCount > 0 ? '需核对' : '框架正常',
      detail:
        billingPendingCount > 0
          ? `还有 ${billingPendingCount} 条业务结果未完成定价或计费确认。`
          : walletRiskCount > 0
            ? `扣费流水失败 ${walletRiskCount} 条，需要核对账单。`
            : `本窗口成本 ${formatCurrencyTotals(strategySummary?.cost_by_currency)}，额度 ${strategySummary?.quota_units || 0}。`,
      action: '看账单框架',
      target: 'billing',
      theme: billingPendingCount > 0 || walletRiskCount > 0 ? 'warning' : 'success',
    },
    {
      key: 'risk',
      title: '风险',
      status: strategyRiskCount > 0 || callbackRiskCount > 0 ? `风险 ${strategyRiskCount || callbackRiskCount}` : queueRiskCount > 0 ? `排队 ${queueRiskCount}` : '无明显风险',
      detail:
        strategyRiskCount > 0
          ? '业务失败、回调失败、未定价或扣费问题会集中计入风险。'
          : callbackRiskCount > 0
            ? `回调失败 ${callbackRiskCount} 次，需要确认业务方能否收到结果。`
            : queueRiskCount > 0
              ? '当前还有任务排队，观察是否能被两台 ComfyUI 能力机及时消化。'
              : '当前没有明显风险信号，继续保持自检和巡检节奏。',
      action: '看接口任务',
      target: 'business',
      theme: strategyRiskCount > 0 || callbackRiskCount > 0 ? 'danger' : queueRiskCount > 0 ? 'warning' : 'success',
    },
  ];
  const featureExposureItems: Array<{
    key: string;
    title: string;
    group: string;
    status: string;
    detail: string;
    target: OverviewNavTarget;
    theme: 'success' | 'warning' | 'danger' | 'default';
    stage: '核心入口' | '治理入口' | '运维入口' | '雏形入口';
  }> = [
    {
      key: 'business',
      title: '业务能力与版本',
      group: '业务',
      status: missingCoreBusinessLabels.length > 0 ? `缺 ${missingCoreBusinessLabels.length}` : '已暴露',
      detail: '花纹提取、图裂变、扩图的默认版本、灰度、回滚和验收入口。',
      target: 'business',
      theme: missingCoreBusinessLabels.length > 0 ? 'danger' : 'success',
      stage: '核心入口',
    },
    {
      key: 'business-runs',
      title: '业务运行闭环',
      group: '业务',
      status: businessTotal > 0 ? `${businessTotal} 次调用` : '待巡检',
      detail: '查看业务调用、版本命中、执行节点、结果入库、回调和计费证据。',
      target: 'business',
      theme: businessTotal > 0 ? 'success' : 'warning',
      stage: '核心入口',
    },
    {
      key: 'api-exposure',
      title: '接口调用',
      group: '业务',
      status: '已暴露',
      detail: '业务 API 文档、API Key、调用清单和 Coze 工具箱入口分开查看。',
      target: 'api-exposure',
      theme: 'success',
      stage: '核心入口',
    },
    {
      key: 'evals',
      title: '能力评测',
      group: '业务',
      status: latestPatrolRecord?.status === 'passed' ? '最近通过' : latestPatrolRecord?.status === 'failed' ? '最近失败' : '待巡检',
      detail: '测评工作流、样例提交、结果入库和人工评分入口。',
      target: 'ability-evals',
      theme: latestPatrolRecord?.status === 'failed' ? 'danger' : latestPatrolRecord?.status === 'passed' ? 'success' : 'warning',
      stage: '核心入口',
    },
    {
      key: 'models',
      title: '模型弹药库',
      group: '能力',
      status: vendorGovernanceIssueCount > 0 ? `风险 ${vendorGovernanceIssueCount}` : `模型 ${vendorModelCount}`,
      detail: '第三方模型、密钥、出网、计价、验收和模型类型总览。',
      target: 'vendor-models',
      theme: vendorGovernanceIssueCount > 0 ? 'warning' : 'success',
      stage: '治理入口',
    },
    {
      key: 'abilities',
      title: '原子能力目录',
      group: '能力',
      status: abilityRiskCount > 0 ? `需处理 ${abilityRiskCount}` : `能力 ${summary.abilities || 0}`,
      detail: '图片、视频、文字、图像理解等原子能力的表单、健康、模板和成本。',
      target: 'abilities',
      theme: abilityRiskCount > 0 ? 'warning' : 'success',
      stage: '治理入口',
    },
    {
      key: 'ability-logs',
      title: '处理步骤',
      group: '能力',
      status: Number(dashboardMetrics?.today.failed || 0) > 0 ? `今日失败 ${dashboardMetrics?.today.failed || 0}` : '已暴露',
      detail: 'VL、模型、ComfyUI 等后台处理步骤，用于从业务任务下钻排障。',
      target: 'ability-logs',
      theme: Number(dashboardMetrics?.today.failed || 0) > 0 ? 'warning' : 'success',
      stage: '治理入口',
    },
    {
      key: 'comfyui',
      title: 'ComfyUI 纳管',
      group: '运行',
      status: summary.activeExecutors < summary.executors ? `${summary.activeExecutors}/${summary.executors} 可用` : '已暴露',
      detail: '服务器、队列、任务、模型/LoRA、轻 Agent、资源差异和修复任务。',
      target: 'comfyui-management',
      theme: summary.activeExecutors < summary.executors ? 'warning' : 'success',
      stage: '运维入口',
    },
    {
      key: 'executors',
      title: '运行线路',
      group: '运行',
      status: pendingQueueTotal > 0 ? `排队 ${pendingQueueTotal}` : '已暴露',
      detail: '执行节点、并发、权重、健康状态和线路配置。',
      target: 'executors',
      theme: pendingQueueTotal > 0 ? 'warning' : 'success',
      stage: '运维入口',
    },
    {
      key: 'billing',
      title: '账单与套餐',
      group: '商业',
      status: billingPendingCount > 0 || walletRiskCount > 0 ? '需核对' : '雏形已露出',
      detail: '成本核对、套餐、月结、催收、发票和用户账务雏形；正式收费后继续加强。',
      target: 'billing',
      theme: billingPendingCount > 0 || walletRiskCount > 0 ? 'warning' : 'default',
      stage: '雏形入口',
    },
    {
      key: 'auth',
      title: '账号权限',
      group: '系统',
      status: '已暴露',
      detail: '管理员、业务方只读、服务 Token、邀请码和角色边界。',
      target: 'auth',
      theme: 'success',
      stage: '治理入口',
    },
    {
      key: 'release',
      title: '发版自检',
      group: '系统',
      status: releaseReadinessTitle,
      detail: '轻量门禁、完整巡检、上线结论登记、周报和事故防复发守护。',
      target: 'overview',
      theme: releaseReadinessTheme,
      stage: '核心入口',
    },
    {
      key: 'workflow-builder',
      title: '高级编排观察',
      group: '高级',
      status: '高级入口',
      detail: 'Coze 编排观察和底层工作流调试入口；普通用户默认不从这里开始。',
      target: 'workflow-builder',
      theme: 'default',
      stage: '运维入口',
    },
  ];
  const featureLedgerStatus: Record<IntegrationNavId, { status: string; theme: 'success' | 'warning' | 'danger' | 'default' }> = {
    overview: { status: releaseReadinessTitle, theme: releaseReadinessTheme },
    business: {
      status: missingCoreBusinessLabels.length > 0 ? `缺 ${missingCoreBusinessLabels.length}` : '主业务已露出',
      theme: missingCoreBusinessLabels.length > 0 ? 'danger' : 'success',
    },
    'api-exposure': { status: '文档已对齐', theme: 'success' },
    'ability-evals': {
      status:
        latestPatrolRecord?.status === 'passed' ? '最近通过' : latestPatrolRecord?.status === 'failed' ? '最近失败' : '待巡检',
      theme: latestPatrolRecord?.status === 'failed' ? 'danger' : latestPatrolRecord?.status === 'passed' ? 'success' : 'warning',
    },
    'vendor-models': {
      status: vendorGovernanceIssueCount > 0 ? `风险 ${vendorGovernanceIssueCount}` : `模型 ${vendorModelCount}`,
      theme: vendorGovernanceIssueCount > 0 ? 'warning' : 'success',
    },
    apikeys: {
      status: vendorKeyCount > 0 ? `${vendorKeyCount} 个密钥` : '兼容入口',
      theme: vendorKeyCount > 0 ? 'success' : 'default',
    },
    abilities: {
      status: abilityRiskCount > 0 ? `需处理 ${abilityRiskCount}` : `能力 ${summary.abilities || 0}`,
      theme: abilityRiskCount > 0 ? 'warning' : 'success',
    },
    executors: {
      status: summary.executors > 0 ? `${summary.activeExecutors}/${summary.executors} 可用` : '待配置',
      theme: summary.executors > 0 && summary.activeExecutors < summary.executors ? 'warning' : summary.executors > 0 ? 'success' : 'default',
    },
    'comfyui-management': {
      status: summary.activeExecutors < summary.executors ? '需关注' : '已纳管',
      theme: summary.activeExecutors < summary.executors ? 'warning' : 'success',
    },
    bindings: { status: '高级入口', theme: 'default' },
    'workflow-builder': { status: '高级入口', theme: 'default' },
    'ability-logs': {
      status: Number(dashboardMetrics?.today.failed || 0) > 0 ? `今日失败 ${dashboardMetrics?.today.failed || 0}` : '可追踪',
      theme: Number(dashboardMetrics?.today.failed || 0) > 0 ? 'warning' : 'success',
    },
    billing: {
      status: billingPendingCount > 0 || walletRiskCount > 0 ? '需核对' : '雏形已露出',
      theme: billingPendingCount > 0 || walletRiskCount > 0 ? 'warning' : 'default',
    },
    monitor: {
      status: pendingQueueTotal > 0 ? `排队 ${pendingQueueTotal}` : '队列正常',
      theme: pendingQueueTotal > 0 ? 'warning' : 'success',
    },
    logs: { status: '排障入口', theme: 'default' },
    auth: { status: '边界已露出', theme: 'success' },
    system: { status: '配置快照', theme: 'default' },
  };
  const featureLedgerItems = integrationNavItems.map((item) => ({
    id: item.id,
    label: item.label,
    group: item.group || 'other',
    groupLabel: item.groupLabel || '其他',
    description: item.description || '',
    advanced: 'advanced' in item ? Boolean(item.advanced) : false,
    guide: moduleGuides[item.id],
    status: featureLedgerStatus[item.id].status,
    theme: featureLedgerStatus[item.id].theme,
  }));
  const featureLedgerGroups = featureLedgerItems.reduce<
    Array<{ key: string; label: string; items: typeof featureLedgerItems }>
  >((groups, item) => {
    const group = groups.find((candidate) => candidate.key === item.group);
    if (group) {
      group.items.push(item);
    } else {
      groups.push({ key: item.group, label: item.groupLabel, items: [item] });
    }
    return groups;
  }, []);
  const operatorFocusItems: Array<{
    key: string;
    priority: string;
    title: string;
    detail: string;
    action: string;
    target: OverviewNavTarget;
    theme: 'success' | 'warning' | 'danger' | 'default';
  }> = [];
  releaseReadinessBlockers.slice(0, 3).forEach((item, index) => {
    operatorFocusItems.push({
      key: `release-blocker-${index}`,
      priority: '发版前处理',
      title: item.title,
      detail: item.detail,
      action: '去处理',
      target: readinessIssueTarget(item.title),
      theme: 'warning',
    });
  });
  if (operatorFocusItems.length < 5) {
    releaseReadinessWarnings.slice(0, 5 - operatorFocusItems.length).forEach((item, index) => {
      operatorFocusItems.push({
        key: `release-warning-${index}`,
        priority: '上线前确认',
        title: item.title,
        detail: item.detail,
        action: '去确认',
        target: readinessIssueTarget(item.title),
        theme: 'warning',
      });
    });
  }
  if (operatorFocusItems.length < 5 && businessUnresolvedIssueCount > 0) {
    operatorFocusItems.push({
      key: 'business-failed',
      priority: '上线前确认',
      title: '业务失败样本',
      detail: `近 ${businessUsageSummary?.windowHours || strategySummary?.window_hours || 24} 小时仍有 ${businessUnresolvedIssueCount} 条失败未确认恢复，先看 runId 详情。`,
      action: '看业务运行',
      target: 'business',
      theme: 'warning',
    });
  }
  if (operatorFocusItems.length < 5 && callbackRiskCount > 0) {
    operatorFocusItems.push({
      key: 'callback-risk',
      priority: '上线前确认',
      title: '回调失败',
      detail: `回调失败 ${callbackRiskCount} 次，业务方可能收不到结果，需要先重试或确认回调地址。`,
      action: '看接口任务',
      target: 'business',
      theme: 'warning',
    });
  }
  if (operatorFocusItems.length < 5 && queueRiskCount > 0) {
    operatorFocusItems.push({
      key: 'queue-risk',
      priority: '观察中',
      title: '任务排队',
      detail: `当前排队 ${queueRiskCount} 个任务，确认两台 ComfyUI 能力机是否都在消化队列。`,
      action: '看运行线路',
      target: 'executors',
      theme: 'warning',
    });
  }
  if (operatorFocusItems.length === 0) {
    operatorFocusItems.push({
      key: 'all-clear',
      priority: '可继续推进',
      title: '当前没有明确阻塞',
      detail: '继续保持发版前门禁、三条主业务真实巡检和 Coze 工具箱抽测，不要只看页面存活。',
      action: '看上线结论',
      target: 'overview',
      theme: 'success',
    });
  }
  const submitReleaseDecision = (status: 'approved' | 'deferred' | 'blocked') => {
    const note = releaseDecisionNote.trim();
    const title =
      status === 'approved'
        ? `确认可上线：${releaseReadinessTitle}`
        : status === 'blocked'
          ? `阻塞上线：${releaseReadinessTitle}`
          : `暂缓上线：${releaseReadinessTitle}`;
    onCreateReleaseDecisionRecord({
      status,
      title,
      note: note || releaseReadinessMessage,
      summary: {
        readinessTitle: releaseReadinessTitle,
        readinessMessage: releaseReadinessMessage,
        blockers: releaseReadinessBlockers.map((item) => ({ title: item.title, status: item.status, detail: item.detail })),
        warnings: releaseReadinessWarnings.map((item) => ({ title: item.title, status: item.status, detail: item.detail })),
        preflightId: preflightLatest?.id || null,
        patrolId: latestPatrolRecord?.id || null,
      },
    });
    setReleaseDecisionNote('');
  };

  return (
    <>
      <Card bordered className="podi-executive-overview-card">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>线上稳定性与封版判断</Typography.Text>
              <div>
                <Typography.Text theme="secondary">先判断线上是否稳定，再判断能不能封版、卡在哪里。</Typography.Text>
              </div>
            </div>
            <Button size="small" variant="outline" loading={loading} onClick={onRefresh}>
              刷新总览
            </Button>
          </Space>
          <Alert theme={stabilityAlertTheme} message={`线上观察：${stabilitySummaryTitle}。${stabilitySummaryMessage}`} />
          <div className="podi-stability-signal-grid">
            {stabilitySignals.map((signal) => (
              <button
                key={signal.key}
                type="button"
                className={`podi-stability-signal podi-stability-signal--${signal.theme}`}
                onClick={() => onNavigate?.(signal.target)}
              >
                <span className="podi-stability-signal__topline">
                  <span>{signal.title}</span>
                  <Tag theme={signal.theme} variant="light" size="small">
                    {signal.status}
                  </Tag>
                </span>
                <span className="podi-stability-signal__detail">{signal.detail}</span>
                <span className="podi-stability-signal__action">{signal.action}</span>
              </button>
            ))}
          </div>
          <Alert
            theme={
              releaseReadinessTheme === 'danger'
                ? 'error'
                : releaseReadinessTheme === 'warning'
                  ? 'warning'
                  : releaseReadinessTheme === 'success'
                    ? 'success'
                    : 'info'
            }
            message={`封版结论：${releaseReadinessTitle}。${releaseReadinessMessage}`}
          />
          {releaseAttentionItems.length > 0 ? (
            <div className="podi-operator-focus-list">
              {releaseAttentionItems.slice(0, 5).map((item, index) => (
              <button
                key={`${item.title}-${item.status}-${index}`}
                type="button"
                className={`podi-operator-focus-item podi-operator-focus-item--${item.theme}`}
                onClick={() => onNavigate?.(readinessIssueTarget(item.title))}
              >
                <span className="podi-operator-focus-item__index">{index + 1}</span>
                <span className="podi-operator-focus-item__body">
                  <span className="podi-operator-focus-item__topline">
                    <Tag theme={item.theme} variant="light" size="small">
                      {item.status}
                    </Tag>
                    <span>去处理</span>
                  </span>
                  <span className="podi-operator-focus-item__title">{item.title}</span>
                  <span className="podi-operator-focus-item__detail">{item.detail}</span>
                </span>
              </button>
              ))}
            </div>
          ) : (
            <Alert theme="success" message="当前没有封版阻断项；下一步跑真实链路巡检并登记结果。" />
          )}
        </Space>
      </Card>

      <Card bordered className="podi-feature-map-card">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>平台功能入口地图</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  已开发能力统一在这里暴露入口；不要求用户先理解导航分组或高级模块开关。
                </Typography.Text>
              </div>
            </div>
            <Tag theme="primary" variant="light">
              {featureExposureItems.length} 个入口
            </Tag>
          </Space>
          <div className="podi-feature-map-grid">
            {featureExposureItems.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`podi-feature-map-item podi-feature-map-item--${item.theme}`}
                onClick={() => onNavigate?.(item.target)}
              >
                <span className="podi-feature-map-item__topline">
                  <span>{item.group}</span>
                  <Tag theme={item.theme} variant="light" size="small">
                    {item.status}
                  </Tag>
                </span>
                <span className="podi-feature-map-item__title">{item.title}</span>
                <span className="podi-feature-map-item__detail">{item.detail}</span>
                <span className="podi-feature-map-item__footer">{item.stage} · 点击进入</span>
              </button>
            ))}
          </div>
        </Space>
      </Card>

      <details className="podi-feature-ledger-collapse">
        <summary>
          <span>
            功能暴露台账
            <small>侧栏 {featureLedgerItems.length} 个一级入口的使用对象、先看什么和下一步动作</small>
          </span>
          <Tag theme="primary" variant="light">
            点击展开
          </Tag>
        </summary>
        <Card bordered className="podi-feature-ledger-card">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
              <div>
                <Typography.Text strong>功能暴露台账</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">
                    侧栏每个一级入口都必须说明“谁使用、先看什么、下一步做什么”。后续新增功能先补这里，再做深层页面。
                  </Typography.Text>
                </div>
              </div>
              <Tag theme="primary" variant="light">
                {featureLedgerItems.length} 个页面
              </Tag>
            </Space>
            <div className="podi-feature-ledger-groups">
              {featureLedgerGroups.map((group) => (
                <section key={group.key} className="podi-feature-ledger-group">
                  <div className="podi-feature-ledger-group__header">
                    <Typography.Text strong>{group.label}</Typography.Text>
                    <Tag variant="light">{group.items.length} 项</Tag>
                  </div>
                  <div className="podi-feature-ledger-list">
                    {group.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`podi-feature-ledger-item podi-feature-ledger-item--${item.theme}`}
                        onClick={() => onNavigate?.(item.id)}
                      >
                        <span className="podi-feature-ledger-item__topline">
                          <span>
                            {item.label}
                            {item.advanced ? <small>高级</small> : null}
                          </span>
                          <Tag theme={item.theme} variant="light" size="small">
                            {item.status}
                          </Tag>
                        </span>
                        <span className="podi-feature-ledger-item__desc">{item.description}</span>
                        <span className="podi-feature-ledger-item__meta">使用对象：{item.guide.audience}</span>
                        <span className="podi-feature-ledger-item__meta">先看：{item.guide.firstLook}</span>
                        <span className="podi-feature-ledger-item__meta">下一步：{item.guide.nextAction}</span>
                        {item.guide.riskHint ? <span className="podi-feature-ledger-item__risk">风险：{item.guide.riskHint}</span> : null}
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </Space>
        </Card>
      </details>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>上线结论</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  这里汇总业务入口、轻量门禁、完整巡检、模型与能力状态，直接判断是否能进入线上闭环。
                </Typography.Text>
              </div>
            </div>
            <Tag theme={releaseReadinessTheme} variant="light">
              {releaseReadinessTitle}
            </Tag>
          </Space>
          <Alert
            theme={
              releaseReadinessTheme === 'danger'
                ? 'error'
                : releaseReadinessTheme === 'default'
                  ? 'info'
                  : releaseReadinessTheme
            }
            message={releaseReadinessMessage}
          />
          <Card bordered size="small" className="podi-release-evidence-card">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                <div>
                  <Typography.Text strong>三条主业务上线证据</Typography.Text>
                  <div>
                    <Typography.Text theme="secondary">
                      默认版本、验收记录、最近真实样本和门禁原因集中在这里；不用再跳到业务页逐个拼判断。
                    </Typography.Text>
                  </div>
                </div>
                <Button size="small" variant="outline" onClick={() => onNavigate?.('business')}>
                  打开业务版本
                </Button>
              </Space>
              <div className="podi-release-evidence-grid">
                {coreBusinessReleaseRows.map((row) => (
                  <Card key={row.businessKey} bordered size="small" className={`podi-release-evidence-item podi-release-evidence-item--${row.theme}`}>
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                        <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                        <Tag theme={row.theme} variant="light">
                          {row.defaultItem?.releaseGate?.label || row.status || businessReleaseGateStatusLabel(row.defaultItem?.releaseGate?.status)}
                        </Tag>
                      </Space>
                      <Typography.Text>
                        {row.defaultItem ? `${row.defaultItem.version} · ${row.defaultItem.displayName}` : '未设置默认版本'}
                      </Typography.Text>
                      <Space size={6} breakLine>
                        <Tag theme={businessAcceptanceTheme(row.defaultItem?.latestAcceptance?.status)} variant="light" size="small">
                          {businessAcceptanceLabel(row.defaultItem?.latestAcceptance?.status)}
                        </Tag>
                        {row.defaultItem?.latestRun ? <StatusBadge status={row.defaultItem.latestRun.status} /> : <Tag variant="light" size="small">暂无样本</Tag>}
                        {row.outputCount > 0 ? (
                          <Tag theme="success" variant="light" size="small">
                            输出 {row.outputCount}
                          </Tag>
                        ) : null}
                      </Space>
                      <Typography.Text theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'secondary'}>
                        {row.reason}
                      </Typography.Text>
                      <Typography.Text theme="secondary">
                        {row.defaultItem?.latestAcceptance?.createdAt
                          ? `验收时间：${formatDateTime(row.defaultItem.latestAcceptance.createdAt)}`
                          : row.defaultItem?.latestRun?.createdAt || row.defaultItem?.latestRun?.created_at
                            ? `最近样本：${formatDateTime(row.defaultItem.latestRun.createdAt || row.defaultItem.latestRun.created_at)}`
                            : '还没有验收或真实样本时间'}
                      </Typography.Text>
                    </Space>
                  </Card>
                ))}
              </div>
            </Space>
          </Card>
          <Row gutter={[12, 12]}>
            {releaseReadinessItems.map((item) => (
              <Col key={item.title} xs={12} sm={6} lg={3}>
                <Card bordered size="small" style={{ height: '100%' }}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Tag theme={item.theme} variant="light">
                        {item.status}
                      </Tag>
                    </Space>
                    <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
          <Space size="small" style={{ flexWrap: 'wrap' }}>
            <Button size="small" theme="primary" loading={releasePreflightLoading} onClick={onRunReleasePreflight}>
              运行轻量门禁
            </Button>
            <Button size="small" variant="outline" onClick={() => onCopyText?.(fullPatrolCommand)}>
              复制完整巡检命令
            </Button>
            <Button size="small" variant="outline" onClick={() => onNavigate?.('business')}>
              检查业务入口
            </Button>
            <Button size="small" variant="outline" onClick={() => onNavigate?.('ability-evals')}>
              进入能力评测
            </Button>
          </Space>
          {releaseDecisionError ? <Alert theme="error" message={releaseDecisionError} /> : null}
          <Card bordered size="small">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                <div>
                  <Typography.Text strong>上线结论登记</Typography.Text>
                  <div>
                    <Typography.Text theme="secondary">
                      把本次判断落成记录，后续复盘能看到当时的门禁、巡检和人工说明。
                    </Typography.Text>
                  </div>
                </div>
                {latestReleaseDecision ? (
                  <Tag theme={releaseDecisionStatusTheme(latestReleaseDecision.status)} variant="light">
                    最近：{releaseDecisionStatusLabel(latestReleaseDecision.status)}
                  </Tag>
                ) : (
                  <Tag theme="default" variant="light">暂无登记</Tag>
                )}
              </Space>
              {latestReleaseDecision ? (
                <Typography.Text theme="secondary">
                  {formatDateTime(latestReleaseDecision.generatedAt)} · {latestReleaseDecision.title}
                  {latestReleaseDecision.note ? ` · ${latestReleaseDecision.note}` : ''}
                </Typography.Text>
              ) : null}
              <Input
                value={releaseDecisionNote}
                onChange={(value) => setReleaseDecisionNote(String(value))}
                placeholder="可选：写清楚本次为什么可上线、为什么暂缓，或还差什么"
              />
              <Space size="small" style={{ flexWrap: 'wrap' }}>
                <Button
                  size="small"
                  theme="success"
                  loading={releaseDecisionLoading}
                  disabled={releaseReadinessHasLoading || releaseReadinessBlockers.length > 0}
                  onClick={() => submitReleaseDecision('approved')}
                >
                  登记可上线
                </Button>
                <Button
                  size="small"
                  variant="outline"
                  loading={releaseDecisionLoading}
                  disabled={releaseReadinessHasLoading}
                  onClick={() => submitReleaseDecision('deferred')}
                >
                  登记暂缓
                </Button>
                <Button
                  size="small"
                  theme="danger"
                  variant="outline"
                  loading={releaseDecisionLoading}
                  disabled={releaseReadinessHasLoading}
                  onClick={() => submitReleaseDecision('blocked')}
                >
                  登记阻塞
                </Button>
                <Button size="small" variant="text" loading={releaseDecisionLoading} onClick={onRefreshReleaseDecisionRecords}>
                  刷新登记
                </Button>
              </Space>
            </Space>
          </Card>
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>线上自检守护</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  展示 114 上的业务轻量自检、真实巡检和评测健康定时器，确认“事故后防复发”机制是否真的在运行。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Tag theme={healthWatchSummaryTheme} variant="light">{healthWatchSummaryText}</Tag>
              <Button size="small" variant="outline" loading={healthWatchLoading} onClick={onRefreshHealthWatchStatus}>
                刷新守护状态
              </Button>
            </Space>
          </Space>
          {healthWatchError ? <Alert theme="error" message={healthWatchError} /> : null}
          {healthWatchStatus && !healthWatchStatus.supported ? (
            <Alert theme="warning" message="当前是本地或非 systemd 环境，无法读取线上定时巡检；这不是业务故障。上线前到 114 服务器确认守护状态即可。" />
          ) : null}
          {!healthWatchUnsupported && healthWatchStatus?.issues?.length ? (
            <Alert theme="warning" message={`需要处理：${healthWatchStatus.issues.slice(0, 3).join('；')}`} />
          ) : null}
          {healthWatchItems.length > 0 ? (
            <div className="max-h-[320px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                  <tr className="text-left">
                    <th className="px-3 py-2">守护项</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">上次 / 下次</th>
                    <th className="px-3 py-2">结论</th>
                  </tr>
                </thead>
                <tbody>
                  {healthWatchItems.map((item: HealthWatchUnitStatus) => (
                    <tr key={item.unit} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2">
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{item.title}</Typography.Text>
                          <Typography.Text theme="secondary">{item.unit}</Typography.Text>
                        </Space>
                      </td>
                      <td className="px-3 py-2">
                        <Tag theme={healthWatchStatusTheme(item.status)} variant="light">
                          {healthWatchStatusLabel(item.status)}
                        </Tag>
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {item.kind === 'timer'
                          ? `上次 ${item.lastTrigger || '—'} / 下次 ${item.nextElapse || '—'}`
                          : `结果 ${item.result || '—'} / exit ${item.execMainStatus ?? '—'}`}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.summary || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Typography.Text theme="secondary">
              暂无定时自检状态。点击“刷新守护状态”，或确认后端已包含 `/api/admin/dashboard/health-watch/status`。
            </Typography.Text>
          )}
          {healthWatchStatus?.generatedAt ? (
            <Typography.Text theme="secondary">状态读取时间：{formatDateTime(healthWatchStatus.generatedAt)}</Typography.Text>
          ) : null}
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>业务上线路径</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  按这个顺序检查：业务入口先稳定，模型和能力再绑定，最后用真实测评确认结果入库。
                </Typography.Text>
              </div>
            </div>
            <Tag
              theme={operationPathLoading ? 'default' : operationPathHasBlocker ? 'danger' : operationPathHasWarning ? 'warning' : 'success'}
              variant="light"
            >
              {operationPathLoading ? '正在加载' : operationPathHasBlocker ? '存在阻塞' : operationPathHasWarning ? '需要处理' : '路径清晰'}
            </Tag>
          </Space>
          <Row gutter={[12, 12]}>
            {operationPathItems.map((item) => (
              <Col key={item.step} xs={12} md={3}>
                <Card bordered size="small" style={{ height: '100%' }}>
                  <Space direction="vertical" size="small" style={{ width: '100%', height: '100%', justifyContent: 'space-between' }}>
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Tag theme="primary" variant="light">
                          {item.step}
                        </Tag>
                        <Tag theme={item.theme} variant="light">
                          {item.status}
                        </Tag>
                      </Space>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Typography.Text theme="secondary">{item.body}</Typography.Text>
                    </Space>
                    <Button size="small" variant="outline" onClick={() => onNavigate?.(item.target)}>
                      {item.action}
                    </Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Typography.Text strong>统计看板</Typography.Text>
          <Typography.Text theme="secondary">今日任务与系统队列总览（用于快速判断“是否异常堆积”）。</Typography.Text>
          <div className="podi-overview-stat-grid">
            <div className="podi-overview-stat-item">
              <div className="podi-overview-stat-item__label">今日新增</div>
              <div className="podi-overview-stat-item__value">{dashboardMetrics?.today.created ?? 0}</div>
            </div>
            <div className="podi-overview-stat-item">
              <div className="podi-overview-stat-item__label">今日完成</div>
              <div className="podi-overview-stat-item__value">{dashboardMetrics?.today.completed ?? 0}</div>
            </div>
            <div className="podi-overview-stat-item">
              <div className="podi-overview-stat-item__label">今日失败</div>
              <div className="podi-overview-stat-item__value">{dashboardMetrics?.today.failed ?? 0}</div>
            </div>
            <div className="podi-overview-stat-item">
              <div className="podi-overview-stat-item__label">队列等待</div>
              <div className="podi-overview-stat-item__value">{pendingQueueTotal}</div>
            </div>
          </div>
          <Card bordered size="small">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                <div>
                  <Typography.Text strong>战略指标快照</Typography.Text>
                  <div>
                    <Typography.Text theme="secondary">
                      近 {strategySummary?.window_hours || 24} 小时业务 API、计费和回调风险，用于周报和发版前判断。
                    </Typography.Text>
                  </div>
                </div>
                <Space>
                  <Tag theme={(strategySummary?.risk_count || 0) > 0 ? 'warning' : 'success'} variant="light">
                    {(strategySummary?.risk_count || 0) > 0 ? `风险 ${strategySummary?.risk_count || 0}` : '无明显风险'}
                  </Tag>
                  <Button size="small" variant="outline" loading={strategySnapshotLoading} onClick={onRefreshStrategySnapshots}>
                    刷新历史
                  </Button>
                  <Button size="small" theme="primary" variant="outline" loading={strategySnapshotLoading} onClick={onCreateStrategySnapshot}>
                    保存本周快照
                  </Button>
                </Space>
              </Space>
              {strategySnapshotError ? <Alert theme="error" message={strategySnapshotError} /> : null}
              <Card bordered size="small" className="podi-strategy-north-star">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                    <div>
                      <Typography.Text strong>{strategyNorthStar?.title || '北极星：成功业务交付'}</Typography.Text>
                      <div>
                        <Typography.Text theme="secondary">
                          这个指标只看业务最终是否成功交付，不看底层任务是否“表面成功”。
                        </Typography.Text>
                      </div>
                    </div>
                    <Space>
                      <Typography.Title level="h3" style={{ margin: 0 }}>
                        {strategyNorthStar?.value || '暂无数据'}
                      </Typography.Title>
                      <Tag theme={strategyIndicatorTheme(strategyNorthStar?.status)} variant="light">
                        {strategyIndicatorStatusLabel(strategyNorthStar?.status)}
                      </Tag>
                    </Space>
                  </Space>
                  <Alert
                    theme={strategyIndicatorAlertTheme(strategyNorthStar?.status)}
                    message={strategyNorthStar?.detail || '尚未生成战略指标，请先保存一次快照。'}
                  />
                  <Typography.Text theme="secondary">
                    下一步：{strategyNorthStar?.action || '先跑三大主业务真实巡检，确认有成功样本。'}
                  </Typography.Text>
                </Space>
              </Card>
              <Row gutter={[12, 12]}>
                <Col xs={12} sm={4}>
                  <MetricCard
                    label="业务调用"
                    value={strategySummary?.business_total || 0}
                    sub={`成功率 ${formatRatePercent(strategySummary?.success_rate)}`}
                  />
                </Col>
                <Col xs={12} sm={4}>
                  <MetricCard label="可计费" value={strategySummary?.billable || 0} sub={`待定价 ${strategySummary?.unpriced || 0}`} />
                </Col>
                <Col xs={12} sm={4}>
                  <MetricCard
                    label="业务成本"
                    value={formatCurrencyTotals(strategySummary?.cost_by_currency)}
                    sub={`${strategySummary?.quota_units || 0} 额度`}
                  />
                </Col>
                <Col xs={12} sm={4}>
                  <MetricCard label="扣费流水" value={strategySummary?.wallet_settled || 0} sub={`失败 ${strategySummary?.wallet_failed || 0}`} />
                </Col>
                <Col xs={12} sm={4}>
                  <MetricCard
                    label="回调失败"
                    value={strategySummary?.callback_failed || 0}
                    sub={`未配置 ${strategySummary?.callback_missing || 0}`}
                  />
                </Col>
                <Col xs={12} sm={4}>
                  <MetricCard label="业务失败" value={strategySummary?.business_failed || 0} sub={`不计费 ${strategySummary?.no_charge || 0}`} />
                </Col>
              </Row>
              {strategyIndicators.length > 0 ? (
                <div className="podi-strategy-kpi-grid">
                  {strategyIndicators.map((item) => (
                    <Card key={item.key} bordered size="small" className="podi-strategy-kpi-card">
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                          <Typography.Text strong>{item.title}</Typography.Text>
                          <Tag theme={strategyIndicatorTheme(item.status)} variant="light">
                            {strategyIndicatorStatusLabel(item.status)}
                          </Tag>
                        </Space>
                        <Typography.Title level="h4" style={{ margin: 0 }}>
                          {item.value}
                        </Typography.Title>
                        <Typography.Text theme="secondary">目标：{item.target}</Typography.Text>
                        <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                        <Typography.Text>下一步：{item.action}</Typography.Text>
                      </Space>
                    </Card>
                  ))}
                </div>
              ) : null}
              {strategySnapshots.length > 0 ? (
                <div className="max-h-[220px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                      <tr className="text-left">
                        <th className="px-3 py-2">快照时间</th>
                        <th className="px-3 py-2">统计窗口</th>
                        <th className="px-3 py-2">业务调用</th>
                        <th className="px-3 py-2">成功率</th>
                        <th className="px-3 py-2">风险</th>
                        <th className="px-3 py-2">成本</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategySnapshots.map((snapshot) => (
                        <tr key={snapshot.id} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2 text-slate-900 dark:text-white">{formatDateTime(snapshot.generatedAt)}</td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">近 {snapshot.windowHours} 小时</td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{snapshot.summary.business_total || 0}</td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                            {formatRatePercent(snapshot.summary.success_rate)}
                          </td>
                          <td className="px-3 py-2">
                            <Tag theme={(snapshot.summary.risk_count || 0) > 0 ? 'warning' : 'success'} variant="light">
                              {snapshot.summary.risk_count || 0}
                            </Tag>
                          </td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                            {formatCurrencyTotals(snapshot.summary.cost_by_currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Typography.Text theme="secondary">暂无历史快照。点击“保存本周快照”后，这里会保留最近趋势。</Typography.Text>
              )}
            </Space>
          </Card>
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>周报通知</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  生成近 7 天战略周报并保留记录；外部通知必须由服务器环境变量配置，页面不会填写 webhook 地址。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Tag theme={weeklyReportStatusTheme(latestWeeklyReport?.sendStatus || '')} variant="light">
                {latestWeeklyReport ? weeklyReportStatusLabel(latestWeeklyReport.sendStatus) : '未生成'}
              </Tag>
              <Button size="small" variant="outline" loading={weeklyReportLoading} onClick={onRefreshWeeklyReports}>
                刷新记录
              </Button>
              <Button size="small" theme="primary" variant="outline" loading={weeklyReportLoading} onClick={() => onRunWeeklyReport(false)}>
                生成周报
              </Button>
              <Button size="small" theme="primary" loading={weeklyReportLoading} onClick={() => onRunWeeklyReport(true)}>
                生成并发送
              </Button>
            </Space>
          </Space>
          {weeklyReportError ? <Alert theme="error" message={weeklyReportError} /> : null}
          <Row gutter={[12, 12]}>
            <Col xs={12} sm={4}>
              <MetricCard
                label="最近周报"
                value={latestWeeklyReport ? weeklyReportStatusLabel(latestWeeklyReport.sendStatus) : '未生成'}
                sub={latestWeeklyReport ? formatDateTime(latestWeeklyReport.generatedAt) : '点击生成周报'}
              />
            </Col>
            <Col xs={12} sm={4}>
              <MetricCard
                label="统计窗口"
                value={latestWeeklyReport ? `近 ${latestWeeklyReport.windowHours} 小时` : '近 7 天'}
                sub={latestWeeklyReport?.reportPath || '生成后会保存本地报告文件'}
              />
            </Col>
            <Col xs={12} sm={4}>
              <MetricCard
                label="通知配置"
                value={latestWeeklyReport?.webhookConfigured ? '已配置' : '未配置'}
                sub={latestWeeklyReport?.sendDetail || '未配置时只保留本地周报'}
              />
            </Col>
          </Row>
          {weeklyReports.length > 0 ? (
            <div className="max-h-[220px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                  <tr className="text-left">
                    <th className="px-3 py-2">生成时间</th>
                    <th className="px-3 py-2">发送状态</th>
                    <th className="px-3 py-2">业务调用</th>
                    <th className="px-3 py-2">成功率</th>
                    <th className="px-3 py-2">风险</th>
                    <th className="px-3 py-2">报告文件</th>
                  </tr>
                </thead>
                <tbody>
                  {weeklyReports.map((report) => (
                    <tr key={report.id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-900 dark:text-white">{formatDateTime(report.generatedAt)}</td>
                      <td className="px-3 py-2">
                        <Tag theme={weeklyReportStatusTheme(report.sendStatus)} variant="light">
                          {weeklyReportStatusLabel(report.sendStatus)}
                        </Tag>
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{report.summary.business_total || 0}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {formatRatePercent(report.summary.success_rate)}
                      </td>
                      <td className="px-3 py-2">
                        <Tag theme={(report.summary.risk_count || 0) > 0 ? 'warning' : 'success'} variant="light">
                          {report.summary.risk_count || 0}
                        </Tag>
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{report.reportPath || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Typography.Text theme="secondary">暂无周报记录。点击“生成周报”后，这里会显示最近状态。</Typography.Text>
          )}
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>发布前门禁</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  默认跑轻量巡检：后端健康、工具箱 OpenAPI、内部任务查询、ComfyUI 队列、能力健康摘要；不自动触发付费工作流。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Tag theme={preflightTheme} variant="light">{preflightLabel}</Tag>
              <Button size="small" variant="outline" loading={releasePreflightLoading} onClick={onRefreshReleasePreflight}>
                刷新记录
              </Button>
              <Button size="small" theme="primary" loading={releasePreflightLoading} onClick={onRunReleasePreflight}>
                运行轻量门禁
              </Button>
            </Space>
          </Space>
          {releasePreflightError ? <Alert theme="error" message={releasePreflightError} /> : null}
          <Row gutter={[12, 12]}>
            <Col xs={12} sm={4}>
              <MetricCard
                label="最近结论"
                value={preflightLatest ? preflightLabel : '未巡检'}
                sub={preflightLatest ? `时间 ${formatDateTime(preflightLatest.generatedAt)}` : '点击运行轻量门禁'}
              />
            </Col>
            <Col xs={12} sm={4}>
              <MetricCard
                label="阻塞项"
                value={preflightLatest?.blockingCount ?? 0}
                sub={preflightLatest?.canRelease ? '没有阻塞' : '需要处理后再发版'}
              />
            </Col>
            <Col xs={12} sm={4}>
              <MetricCard
                label="提醒项"
                value={preflightLatest?.warningCount ?? 0}
                sub={preflightLatest?.baseUrl ? `检查地址 ${preflightLatest.baseUrl}` : '轻量风险提示'}
              />
            </Col>
          </Row>
          {preflightLatest ? (
            releaseCoreChecks.length > 0 ? (
              <Card bordered size="small">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                    <div>
                      <Typography.Text strong>核心上线门禁</Typography.Text>
                      <div>
                        <Typography.Text theme="secondary">
                          优先看业务默认版本、账号权限、Coze 查询入口和 ComfyUI 队列；这些失败就不要更新服务。
                        </Typography.Text>
                      </div>
                    </div>
                    <Tag
                      theme={releaseCoreFailedMessages.length > 0 ? 'danger' : releaseCoreWarningMessages.length > 0 ? 'warning' : 'success'}
                      variant="light"
                    >
                      {releaseCoreFailedMessages.length > 0
                        ? `阻塞 ${releaseCoreFailedMessages.length}`
                        : releaseCoreWarningMessages.length > 0
                          ? `提醒 ${releaseCoreWarningMessages.length}`
                          : '关键链路正常'}
                    </Tag>
                  </Space>
                  <Row gutter={[12, 12]}>
                    {releaseCoreChecks.map((check) => (
                      <Col xs={12} sm={6} key={`${preflightLatest.id}-${check.name}-core`}>
                        <Card bordered size="small">
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                              <Typography.Text strong>{check.title}</Typography.Text>
                              <Tag theme={releasePreflightCheckTheme(check.status)} variant="light">
                                {releasePreflightCheckLabel(check.status)}
                              </Tag>
                            </Space>
                            <Typography.Text theme="secondary">{check.detail || '暂无运行详情'}</Typography.Text>
                            {check.suggestion ? <Typography.Text theme="secondary">处理建议：{check.suggestion}</Typography.Text> : null}
                          </Space>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </Space>
              </Card>
            ) : (
              <Alert
                theme="warning"
                message="本次轻量门禁没有返回业务能力和账号权限检查，请确认后端已经更新到包含核心上线门禁的版本。"
              />
            )
          ) : null}
          {preflightLatest ? (
            releaseCronChecks.length > 0 ? (
              <Card bordered size="small">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                    <div>
                      <Typography.Text strong>定时任务守护</Typography.Text>
                      <div>
                        <Typography.Text theme="secondary">
                          单独盯住周报和账单催收，避免后台任务停了但页面业务仍然看似正常。
                        </Typography.Text>
                      </div>
                    </div>
                    <Tag theme={releaseCronRiskMessages.length > 0 ? 'warning' : 'success'} variant="light">
                      {releaseCronRiskMessages.length > 0 ? `提醒 ${releaseCronRiskMessages.length}` : '运行正常'}
                    </Tag>
                  </Space>
                  <Row gutter={[12, 12]}>
                    {releaseCronChecks.map((check) => (
                      <Col xs={12} sm={6} key={`${preflightLatest.id}-${check.name}-cron`}>
                        <Card bordered size="small">
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                              <Typography.Text strong>{check.title}</Typography.Text>
                              <Tag theme={releasePreflightCheckTheme(check.status)} variant="light">
                                {releasePreflightCheckLabel(check.status)}
                              </Tag>
                            </Space>
                            <Typography.Text theme="secondary">{check.detail || '暂无运行详情'}</Typography.Text>
                            {check.suggestion ? <Typography.Text theme="secondary">处理建议：{check.suggestion}</Typography.Text> : null}
                          </Space>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </Space>
              </Card>
            ) : (
              <Alert
                theme="warning"
                message="本次轻量门禁没有返回定时任务守护结果，请确认后端已经更新到包含周报和账单催收检查的版本。"
              />
            )
          ) : null}
          {preflightLatest?.checks?.length ? (
            <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                  <tr className="text-left">
                    <th className="px-3 py-2">检查项</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">结果</th>
                    <th className="px-3 py-2">建议</th>
                  </tr>
                </thead>
                <tbody>
                  {preflightLatest.checks.map((check) => (
                    <tr key={`${preflightLatest.id}-${check.name}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-900 dark:text-white">{check.title}</td>
                      <td className="px-3 py-2">
                        <Tag theme={releasePreflightCheckTheme(check.status)} variant="light">
                          {releasePreflightCheckLabel(check.status)}
                        </Tag>
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{check.detail || '—'}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{check.suggestion || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Typography.Text theme="secondary">暂无门禁记录。运行一次轻量门禁后，这里会保留最近检查结果。</Typography.Text>
          )}
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>完整巡检确认</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  完整巡检会真实提交所有启用的测评工作流，可能产生模型和 GPU 成本；这里不自动执行，只提供命令和结果登记。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Button size="small" variant="outline" loading={releasePatrolLoading} onClick={onRefreshReleasePatrolRecords}>
                刷新记录
              </Button>
              <Button size="small" variant="outline" onClick={() => onCopyText?.(fullPatrolCommand)}>
                复制命令
              </Button>
              <Button size="small" theme="success" loading={releasePatrolLoading} onClick={() => onCreateReleasePatrolRecord('passed')}>
                记录为通过
              </Button>
              <Button size="small" theme="danger" variant="outline" loading={releasePatrolLoading} onClick={() => onCreateReleasePatrolRecord('failed')}>
                记录为失败
              </Button>
            </Space>
          </Space>
          <Alert
            theme="warning"
            message="执行前先确认当前发布版本、服务地址和样例图；失败时不要只重跑，先查看报告里的工作流、任务编号、错误摘要。"
          />
          {releasePatrolError ? <Alert theme="error" message={releasePatrolError} /> : null}
          <pre className="overflow-auto rounded-2xl bg-slate-950 p-3 text-xs text-slate-100">{fullPatrolCommand}</pre>
          {latestPatrolRecord && latestPatrolEvidence.length > 0 ? (
            <Card bordered size="small" className="bg-slate-50/70 dark:bg-slate-950/40">
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                  <div>
                    <Typography.Text strong>最近巡检健康证据</Typography.Text>
                    <div>
                      <Typography.Text theme="secondary">
                        来自 {formatDateTime(latestPatrolRecord.generatedAt)} 的真实工作流巡检，展示每个能力是否完成、是否有结果入库。
                      </Typography.Text>
                    </div>
                  </div>
                  <Space size={6} breakLine>
                    <Tag theme="default" variant="light">总数 {latestPatrolEvidence.length}</Tag>
                    <Tag theme="success" variant="light">通过 {latestPatrolEvidence.length - latestPatrolFailedEvidence.length}</Tag>
                    <Tag theme={latestPatrolFailedEvidence.length > 0 ? 'danger' : 'success'} variant="light">
                      失败 {latestPatrolFailedEvidence.length}
                    </Tag>
                    <Tag theme={latestPatrolOutputReady === latestPatrolEvidence.length ? 'success' : 'warning'} variant="light">
                      已入库 {latestPatrolOutputReady}
                    </Tag>
                  </Space>
                </Space>
                <div className="max-h-[240px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                      <tr className="text-left">
                        <th className="px-3 py-2">功能</th>
                        <th className="px-3 py-2">状态</th>
                        <th className="px-3 py-2">结果入库</th>
                        <th className="px-3 py-2">任务编号</th>
                        <th className="px-3 py-2">问题</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latestPatrolEvidence.slice(0, 20).map((item, index) => {
                        const tag = patrolHealthTag(item);
                        return (
                          <tr key={`${item.workflowId || item.runId || index}`} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="px-3 py-2">
                              <Space direction="vertical" size={2}>
                                <Typography.Text>{item.name || '未命名工作流'}</Typography.Text>
                                <Typography.Text theme="secondary">{item.workflowId || '无 workflowId'}</Typography.Text>
                              </Space>
                            </td>
                            <td className="px-3 py-2">
                              <Tag theme={tag.theme} variant="light">{tag.text}</Tag>
                            </td>
                            <td className="px-3 py-2">
                              <Tag theme={item.hasOutput ? 'success' : 'warning'} variant="light">
                                {item.hasOutput ? `${item.imageCount || 1} 个结果` : '未入库'}
                              </Tag>
                            </td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                              {item.podiTaskId || item.runId || item.cozeExecuteId || '—'}
                            </td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                              {item.issueCode === 'OK' ? '—' : item.error || item.issueCode}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {latestPatrolEvidence.length > 20 ? (
                  <Typography.Text theme="secondary">仅展示前 20 条；完整明细以巡检报告为准。</Typography.Text>
                ) : null}
              </Space>
            </Card>
          ) : latestPatrolRecord ? (
            <Alert
              theme="warning"
              message="最近巡检记录没有逐条健康证据。请导入新版巡检脚本生成的报告，报告中需要包含 items 明细。"
            />
          ) : null}
          <Space align="center" style={{ width: '100%', flexWrap: 'wrap' }}>
            <Input
              value={releasePatrolReportPath}
              onChange={(value) => setReleasePatrolReportPath(String(value))}
              placeholder="填写巡检报告路径，例如 reports/eval_patrol_20260429_120000.json"
              style={{ minWidth: 360, flex: 1 }}
            />
            <Button
              size="small"
              theme="primary"
              loading={releasePatrolLoading}
              disabled={!releasePatrolReportPath.trim()}
              onClick={() => onImportReleasePatrolReport(releasePatrolReportPath)}
            >
              导入报告并判断
            </Button>
          </Space>
          {releasePatrolRecords.length > 0 ? (
            <div className="max-h-[220px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                  <tr className="text-left">
                    <th className="px-3 py-2">记录时间</th>
                    <th className="px-3 py-2">结论</th>
                    <th className="px-3 py-2">失败项</th>
                    <th className="px-3 py-2">报告</th>
                    <th className="px-3 py-2">备注</th>
                  </tr>
                </thead>
                <tbody>
                  {releasePatrolRecords.map((record) => {
                    const failedItems = patrolFailedItems(record);
                    const failedCount = patrolNumber(record, 'failedOrUnfinished');
                    return (
                      <Fragment key={record.id}>
                        <tr className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2 text-slate-900 dark:text-white">{formatDateTime(record.generatedAt)}</td>
                          <td className="px-3 py-2">
                            <Tag theme={record.status === 'passed' ? 'success' : record.status === 'failed' ? 'danger' : 'default'} variant="light">
                              {record.status === 'passed' ? '通过' : record.status === 'failed' ? '失败' : record.status}
                            </Tag>
                          </td>
                          <td className="px-3 py-2">
                            <Tag theme={failedCount > 0 || failedItems.length > 0 ? 'danger' : 'success'} variant="light">
                              {failedCount > 0 || failedItems.length > 0 ? `${failedCount || failedItems.length} 个` : '无'}
                            </Tag>
                          </td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{record.reportPath || '—'}</td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{record.note || '—'}</td>
                        </tr>
                        {failedItems.length > 0 ? (
                          <tr className="border-t border-slate-100 bg-rose-50/60 dark:border-slate-800 dark:bg-rose-950/20">
                            <td colSpan={5} className="px-3 py-3">
                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                <Typography.Text strong>失败项排障</Typography.Text>
                                {failedItems.map((item, index) => {
                                  const title = item.name || item.workflowId || `失败项 ${index + 1}`;
                                  const identity = [
                                    item.workflowId ? `工作流 ${item.workflowId}` : '',
                                    item.runId ? `runId ${item.runId}` : '',
                                    item.podiTaskId ? `taskId ${item.podiTaskId}` : '',
                                  ]
                                    .filter(Boolean)
                                    .join(' · ');
                                  return (
                                    <div
                                      key={`${record.id}-${index}-${item.workflowId || item.runId || item.podiTaskId || title}`}
                                      className="rounded-xl border border-rose-200/80 bg-white p-3 dark:border-rose-900/60 dark:bg-slate-950"
                                    >
                                      <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                                          <div>
                                            <Typography.Text strong>{title}</Typography.Text>
                                            <div>
                                              <Typography.Text theme="secondary">{identity || '缺少任务标识'}</Typography.Text>
                                            </div>
                                          </div>
                                          <Space size={4}>
                                            {item.runId ? (
                                              <Button size="small" variant="outline" onClick={() => onOpenEvalRun?.(item.runId)}>
                                                去测评记录
                                              </Button>
                                            ) : null}
                                            {item.runId ? (
                                              <Button size="small" variant="outline" onClick={() => onCopyText?.(item.runId)}>
                                                复制 runId
                                              </Button>
                                            ) : null}
                                            {item.podiTaskId ? (
                                              <Button size="small" variant="outline" onClick={() => onCopyText?.(item.podiTaskId)}>
                                                复制 taskId
                                              </Button>
                                            ) : null}
                                            {item.error ? (
                                              <Button size="small" variant="outline" onClick={() => onCopyText?.(item.error)}>
                                                复制错误
                                              </Button>
                                            ) : null}
                                          </Space>
                                        </Space>
                                        <Typography.Text theme="secondary">
                                          状态：{item.status || '未知'}；错误：{item.error || '报告未返回错误详情'}
                                        </Typography.Text>
                                      </Space>
                                    </div>
                                  );
                                })}
                              </Space>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Typography.Text theme="secondary">暂无完整巡检记录。执行脚本并确认结果后，可以在这里登记本次结论。</Typography.Text>
          )}
        </Space>
      </Card>

      <Card bordered style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>主业务状态</Typography.Text>
              <div>
                <Typography.Text theme="secondary">先看花纹提取、图裂变、扩图是否可用；辅助能力放到后续页面处理。</Typography.Text>
              </div>
            </div>
            <Tag theme={businessUnresolvedIssueCount > 0 ? 'warning' : 'success'} variant="light">
              {businessUnresolvedIssueCount > 0 ? `待确认 ${businessUnresolvedIssueCount}` : '没有未收口失败'}
            </Tag>
          </Space>
          <Row gutter={[12, 12]}>
            {coreBusinessOverviewItems.map((item) => (
              <Col key={item.id} xs={12} md={4}>
                <Card bordered size="small">
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text strong>{businessKeyLabel(item.businessKey)}</Typography.Text>
                      <StatusBadge status={item.status} />
                    </Space>
                    <Typography.Text>{item.displayName}</Typography.Text>
                    <Typography.Text theme="secondary">
                      默认版本：{item.version} · 发布时间：{formatDateTime(item.releaseTime || item.createdAt)}
                    </Typography.Text>
                    <Typography.Text theme={Number(item.runMetrics?.failed || 0) > 0 ? 'warning' : 'secondary'}>
                      {businessCapabilityRunMetricsLabel(item)}
                    </Typography.Text>
                    <Typography.Text theme={item.latestRun?.error ? 'error' : 'secondary'}>
                      最近调用：{businessCapabilityLatestRunLabel(item)}
                    </Typography.Text>
                  </Space>
                </Card>
              </Col>
            ))}
            {coreBusinessOverviewItems.length === 0 ? (
              <Col span={12}>
                <Typography.Text theme="secondary">暂未加载业务能力数据。请刷新，或进入“业务能力”检查默认版本配置。</Typography.Text>
              </Col>
            ) : null}
          </Row>
        </Space>
      </Card>

      <Card bordered>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text theme="secondary">控制台</Typography.Text>
              <Typography.Title level="h3" style={{ margin: '6px 0 0' }}>
                AI 集成管理控制台
              </Typography.Title>
              <Typography.Text theme="secondary">独立系统，聚合业务能力、模型 API、原子能力和执行资源，支持链路自检。</Typography.Text>
            </div>
            <Space>
              <Button variant="outline" loading={loading} onClick={onRefresh}>
                刷新数据
              </Button>
            </Space>
          </Space>
        </Space>
      </Card>
      <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="运行线路" value={summary.executors} sub={`可用 ${summary.activeExecutors}`} />
        <MetricCard label="工作流模板" value={summary.workflows} sub="版本与类型" />
        <MetricCard label="路由策略" value={summary.bindings} sub="能力入口到线路" />
        <MetricCard label="历史密钥" value={summary.apiKeys} sub="即将到期请注意" />
        <MetricCard label="能力目录" value={summary.abilities || 0} sub="厂商 × 功能" />
      </div>
    </>
  );
}
