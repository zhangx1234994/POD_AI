import { Fragment, useState } from 'react';
import { Alert, Button, Card, Col, Input, Row, Space, Tag, Typography } from 'tdesign-react';
import type {
  AbilityHealthSummaryResponse,
  BusinessCapability,
  BusinessUsageSummaryResponse,
  DashboardMetrics,
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
  coreBusinessKeys,
} from './businessLabels';
import { formatCurrencyTotals, formatDateTime, formatRatePercent } from './formatters';

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
  if (item.issueCode === 'EVAL_SUCCEEDED_WITHOUT_OUTPUT') return { theme: 'warning', text: '无回填' };
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

type OverviewSummary = {
  executors: number;
  activeExecutors: number;
  workflows: number;
  bindings: number;
  apiKeys: number;
  abilities: number;
};

type OverviewNavTarget = 'business' | 'vendor-models' | 'abilities' | 'ability-evals';

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
  const latestWeeklyReport = weeklyReports[0] || null;
  const fullPatrolCommand =
    'python3 backend/scripts/patrol_eval_workflows.py --base-url http://127.0.0.1:8099 --timeout 1800 --report reports/eval_patrol_$(date +%Y%m%d_%H%M%S).json';
  const preflightLatest = releasePreflightLatest || releasePreflightSnapshots[0] || null;
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
  const releaseCronRiskMessages = releaseCronChecks
    .filter((check) => check.status !== 'pass')
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
      .map((item) => item.businessKey),
  );
  const missingCoreBusinessLabels = coreBusinessKeys
    .filter((key) => !activeDefaultBusinessKeys.has(key))
    .map((key) => businessKeyLabel(key));
  const businessFailedCount = Number(businessUsageSummary?.failed || 0);
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
          : businessFailedCount > 0
            ? `失败 ${businessFailedCount}`
            : '入口完整',
      theme: businessPathLoading ? 'default' : missingCoreBusinessLabels.length > 0 ? 'danger' : businessFailedCount > 0 ? 'warning' : 'success',
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
      body: '发版前用测评端或巡检脚本跑真实链路，确认 Coze 到中台再到能力服务的回填闭环。',
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
      title: '业务入口',
      status: businessPathLoading
        ? '加载中'
        : missingCoreBusinessLabels.length > 0
          ? '阻塞'
          : businessFailedCount > 0 || callbackFailedCount > 0
            ? '需处理'
            : '通过',
      detail: businessPathLoading
        ? '正在加载默认版本和最近调用。'
        : missingCoreBusinessLabels.length > 0
          ? `缺少 ${missingCoreBusinessLabels.join('、')} 的 active 默认版本。`
          : businessFailedCount > 0
            ? `近 ${businessUsageSummary?.windowHours || 24} 小时业务失败 ${businessFailedCount} 次。`
            : callbackFailedCount > 0
              ? `当前还有 ${callbackFailedCount} 次回调失败。`
              : '三大主业务默认入口完整，最近无明显失败。',
      theme: businessPathLoading ? 'default' : missingCoreBusinessLabels.length > 0 || businessFailedCount > 0 || callbackFailedCount > 0 ? 'danger' : 'success',
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
  const releaseReadinessTitle = releaseReadinessHasLoading
    ? '正在加载'
    : releaseReadinessBlockers.length > 0
      ? '暂不能上线'
      : releaseReadinessWarnings.length > 0
        ? '待验收确认'
        : '可以上线';
  const releaseReadinessTheme = releaseReadinessHasLoading
    ? 'default'
    : releaseReadinessBlockers.length > 0
      ? 'danger'
      : releaseReadinessWarnings.length > 0
        ? 'warning'
        : 'success';
  const releaseReadinessMessage = releaseReadinessHasLoading
    ? '正在加载业务、门禁和巡检数据，加载完成后再判断。'
    : releaseReadinessBlockers.length > 0
      ? `存在 ${releaseReadinessBlockers.length} 个阻塞项：${releaseReadinessBlockers.map((item) => item.title).join('、')}。处理完成前不要发版。`
      : releaseReadinessWarnings.length > 0
        ? `还需要确认 ${releaseReadinessWarnings.length} 个事项：${releaseReadinessWarnings.map((item) => item.title).join('、')}。确认后再安排线上闭环。`
        : '业务入口、轻量门禁、完整巡检和能力状态都已满足上线前检查要求。';
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
      {guardMessages.length > 0 ? (
        <Alert theme="error" message={`发版守护提醒：${guardMessages.join('；')}。处理完成前不要发版。`} style={{ marginBottom: 16 }} />
      ) : null}
      {releaseCronRiskMessages.length > 0 ? (
        <Alert
          theme="warning"
          message={`定时任务提醒：${releaseCronRiskMessages.join('；')}。这类问题不一定阻塞发版，但需要当天处理或登记原因。`}
          style={{ marginBottom: 16 }}
        />
      ) : null}

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
              <Typography.Text strong>业务上线路径</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  按这个顺序检查：业务入口先稳定，模型和能力再绑定，最后用真实测评确认回填。
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
                        来自 {formatDateTime(latestPatrolRecord.generatedAt)} 的真实工作流巡检，展示每个能力是否完成、是否有结果回填。
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
                      已回填 {latestPatrolOutputReady}
                    </Tag>
                  </Space>
                </Space>
                <div className="max-h-[240px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                      <tr className="text-left">
                        <th className="px-3 py-2">功能</th>
                        <th className="px-3 py-2">状态</th>
                        <th className="px-3 py-2">结果回填</th>
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
                                {item.hasOutput ? `${item.imageCount || 1} 个结果` : '未回填'}
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
            <Tag theme={Number(businessUsageSummary?.failed || 0) > 0 ? 'warning' : 'success'} variant="light">
              {Number(businessUsageSummary?.failed || 0) > 0 ? '存在失败样本' : '近24小时无失败样本'}
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
