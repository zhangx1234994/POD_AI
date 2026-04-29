import { useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Input, Row, Select, Space, Table, Tag, Textarea, Typography } from 'tdesign-react';

import type {
  BillingMonthlySettlementListResponse,
  BillingMonthlySettlementResponse,
  BillingNotificationConfigResponse,
  BillingInvoiceRequestListResponse,
  BillingOverviewResponse,
  BillingUserDetailResponse,
  MonthlySettlementCollectionNotificationListResponse,
  PackageAlertNotificationListResponse,
  PackageGrantPayload,
  PackagePurchaseOrderCreatePayload,
  PackagePurchaseOrderListResponse,
} from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import {
  businessBillingStatusLabel,
  businessBillingStatusTheme,
  businessKeyLabel,
  coreBusinessKeys,
} from './businessLabels';
import { formatPriceValue } from './formatters';

const formatPoints = (value?: number | null) => `${Number(value || 0).toLocaleString('zh-CN')} 点`;

const formatPackageUnits = (value?: number | null, unitName = '次') =>
  `${Number(value || 0).toLocaleString('zh-CN')} ${unitName}`;

const formatSignedPoints = (value?: number | null) => {
  const normalized = Number(value || 0);
  const prefix = normalized > 0 ? '+' : '';
  return `${prefix}${normalized.toLocaleString('zh-CN')} 点`;
};

const formatMoney = (amountCents?: number | null, currency = 'CNY') => {
  const amount = Number(amountCents || 0) / 100;
  const prefix = currency === 'CNY' ? '¥' : `${currency} `;
  return `${prefix}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const isExpenseChangeType = (value?: string | null) => {
  const normalized = String(value || '').toLowerCase();
  return ['consume', 'expense', 'decrease', 'deduct', 'confirm', 'freeze_confirm'].includes(normalized);
};

const formatLedgerPoints = (changeType?: string | null, value?: number | null) => {
  const amount = Number(value || 0);
  const absolute = Math.abs(amount).toLocaleString('zh-CN');
  if (amount < 0 || isExpenseChangeType(changeType)) return `-${absolute} 点`;
  return `+${absolute} 点`;
};

const settlementScopeKey = (tenantId?: string | null, clientId?: string | null, businessKey?: string | null) =>
  [tenantId || '', clientId || '', businessKey || ''].join('|');

const settlementRecordTheme = (status?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (status === 'paid') return 'success';
  if (status === 'cancelled') return 'danger';
  if (status === 'issued') return 'warning';
  return 'default';
};

const collectionLevelTheme = (value?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (value === 'escalate') return 'danger';
  if (value === 'follow_up' || value === 'remind') return 'warning';
  if (value === 'watch') return 'default';
  return 'success';
};

const collectionLevelLabel = (value?: string | null) => {
  if (value === 'escalate') return '升级催收';
  if (value === 'follow_up') return '持续跟进';
  if (value === 'remind') return '提醒付款';
  if (value === 'watch') return '观察中';
  return '无需催收';
};

const notificationStatusMeta = (
  status?: string | null,
): { label: string; theme: 'success' | 'warning' | 'danger' | 'default' } => {
  if (status === 'sent') return { label: '已发送', theme: 'success' };
  if (status === 'failed') return { label: '发送失败', theme: 'danger' };
  if (status === 'no_alerts') return { label: '无预警', theme: 'success' };
  if (status === 'not_sent') return { label: '未发送', theme: 'warning' };
  return { label: '未知', theme: 'default' };
};

const notificationTemplateLabel = (value?: string | null) => {
  if (value === 'client_followup') return '业务方提醒版';
  if (value === 'finance_collection') return '财务催收版';
  return '运营处理版';
};

const notificationNextActionLabel = (value?: string | null) => {
  if (value === 'escalate_collection') return '升级催收';
  if (value === 'confirm_payment_plan') return '确认付款计划';
  if (value === 'remind_payment') return '提醒付款';
  if (value === 'wait_payment') return '继续观察';
  if (value === 'renew_and_topup') return '续期并补量';
  if (value === 'renew_package') return '确认续期';
  if (value === 'topup_package') return '补充额度';
  return '暂无动作';
};

const packagePurchaseStatusTheme = (status?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (status === 'paid') return 'success';
  if (status === 'failed' || status === 'cancelled') return 'danger';
  if (status === 'pending') return 'warning';
  return 'default';
};

const invoiceStatusTheme = (status?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (status === 'issued') return 'success';
  if (status === 'cancelled') return 'danger';
  if (status === 'requested') return 'warning';
  return 'default';
};

const BillingMetricCard = ({ label, value, sub }: { label: string; value: number | string; sub?: string }) => (
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

const daysUntil = (value?: string | null): number | null => {
  if (!value) return null;
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return null;
  return Math.ceil((time - Date.now()) / 86400000);
};

const BillingActionPanel = ({
  overview,
  detail,
  formatDateTime,
}: {
  overview?: BillingOverviewResponse | null;
  detail?: BillingUserDetailResponse | null;
  formatDateTime: (value?: string | null) => string;
}) => {
  const packageItems = detail?.packageBalances.items || [];
  const overviewPackageAlerts = overview?.packageAlerts || [];
  const expiringPackages = packageItems.filter((item) => {
    const days = daysUntil(item.expiresAt);
    return days !== null && days >= 0 && days <= 14;
  });
  const lowPackages = packageItems.filter((item) => {
    const total = Number(item.totalUnits || 0);
    if (total <= 0) return false;
    return Number(item.remainingUnits || 0) <= Math.max(1, total * 0.2);
  });
  const actions: Array<{ theme: 'success' | 'warning' | 'danger' | 'default'; title: string; detail: string }> = [];

  if (Number(overview?.issueCount || 0) > 0) {
    actions.push({
      theme: 'danger',
      title: '先处理异常扣费',
      detail: `${overview?.issueCount || 0} 条样本需要核对，优先处理扣费失败、应扣未扣和失败误扣。`,
    });
  }
  if (overview && Number(overview.totalPackageRemainingUnits || 0) <= 0) {
    actions.push({
      theme: 'warning',
      title: '套餐总余量不足',
      detail: '当前筛选范围内没有可用套餐余量，需要补赠送入口或确认业务是否改走钱包扣费。',
    });
  }
  if (Number(overview?.packageExpiringSoonCount || 0) > 0) {
    actions.push({
      theme: 'warning',
      title: '套餐即将到期',
      detail: `${overview?.packageExpiringSoonCount || 0} 个套餐将在 14 天内到期，先查看套餐预警样本并安排续期或补量。`,
    });
  }
  if (Number(overview?.packageLowBalanceCount || 0) > 0) {
    actions.push({
      theme: 'warning',
      title: '套餐余量偏低',
      detail: `${overview?.packageLowBalanceCount || 0} 个套餐余量低于 20%，需要提前补量，避免业务调用突然失败。`,
    });
  }
  if (overviewPackageAlerts.length > 0 && actions.length === 0) {
    actions.push({
      theme: 'warning',
      title: '存在套餐预警',
      detail: '当前筛选范围内有套餐预警样本，请查看下方清单。',
    });
  }
  if (detail && packageItems.length === 0) {
    actions.push({
      theme: 'warning',
      title: '当前用户无套餐',
      detail: '该用户没有套餐额度，后续套餐赠送/购买入口落地前需要人工确认是否允许继续调用。',
    });
  }
  if (expiringPackages.length > 0) {
    const first = expiringPackages[0];
    actions.push({
      theme: 'warning',
      title: '套餐即将到期',
      detail: `${first.packageName || first.packageKey} 将在 ${formatDateTime(first.expiresAt)} 到期，需提前续期或转钱包扣费。`,
    });
  }
  if (lowPackages.length > 0) {
    const first = lowPackages[0];
    actions.push({
      theme: 'warning',
      title: '套餐余额偏低',
      detail: `${first.packageName || first.packageKey} 剩余 ${formatPackageUnits(first.remainingUnits, first.unitName || '次')}，建议准备补量。`,
    });
  }
  if (actions.length === 0) {
    actions.push({
      theme: 'success',
      title: '账单当前无明显阻塞',
      detail: '异常扣费、套餐余量和到期风险没有明显问题，可继续做业务账单核对。',
    });
  }

  return (
    <Card bordered title="当前先处理什么">
      <Row gutter={[12, 12]}>
        {actions.slice(0, 5).map((item) => (
          <Col key={`${item.title}-${item.detail}`} xs={12} lg={actions.length === 1 ? 12 : 4}>
            <div
              style={{
                border: '1px solid var(--td-border-level-1-color)',
                borderRadius: 12,
                padding: 12,
                height: '100%',
              }}
            >
              <Space direction="vertical" size={4}>
                <Tag theme={item.theme} variant="light">
                  {item.title}
                </Tag>
                <Typography.Text theme="secondary">{item.detail}</Typography.Text>
              </Space>
            </div>
          </Col>
        ))}
      </Row>
    </Card>
  );
};

const BillingNotificationConfigCard = ({
  config,
  loading,
  onSave,
}: {
  config?: BillingNotificationConfigResponse | null;
  loading: boolean;
  onSave: (
    channels: Array<{
      key: string;
      enabled: boolean;
      webhookUrl?: string | null;
      webhookFormat?: string | null;
    }>,
  ) => Promise<void> | void;
}) => {
  const [draft, setDraft] = useState<Record<string, { enabled: boolean; webhookUrl: string; webhookFormat: string }>>({});
  const channels = config?.channels || [];

  useEffect(() => {
    const next: Record<string, { enabled: boolean; webhookUrl: string; webhookFormat: string }> = {};
    channels.forEach((channel) => {
      next[channel.key] = {
        enabled: Boolean(channel.enabled),
        webhookUrl: channel.webhookUrl || '',
        webhookFormat: channel.webhookFormat || 'generic',
      };
    });
    setDraft(next);
  }, [config]);

  const updateDraft = (key: string, patch: Partial<{ enabled: boolean; webhookUrl: string; webhookFormat: string }>) => {
    setDraft((prev) => ({
      ...prev,
      [key]: {
        enabled: Boolean(prev[key]?.enabled),
        webhookUrl: prev[key]?.webhookUrl || '',
        webhookFormat: prev[key]?.webhookFormat || 'generic',
        ...patch,
      },
    }));
  };

  const submit = () => {
    onSave(
      channels.map((channel) => ({
        key: channel.key,
        enabled: Boolean(draft[channel.key]?.enabled),
        webhookUrl: draft[channel.key]?.webhookUrl || '',
        webhookFormat: draft[channel.key]?.webhookFormat || 'generic',
      })),
    );
  };

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>通知渠道配置</Typography.Text>
            <div>
              <Typography.Text theme="secondary">配置套餐预警和月结催收要发到哪里；页面配置优先，环境变量作为兜底。</Typography.Text>
            </div>
          </div>
          <Button size="small" theme="primary" loading={loading} disabled={channels.length === 0} onClick={submit}>
            保存通知渠道
          </Button>
        </Space>
      }
    >
      <Row gutter={[16, 16]}>
        {channels.length === 0 ? (
          <Col span={12}>
            <Typography.Text theme="secondary">正在加载通知渠道配置。</Typography.Text>
          </Col>
        ) : (
          channels.map((channel) => (
            <Col key={channel.key} xs={12} lg={6}>
              <Card bordered>
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{channel.displayName}</Typography.Text>
                    <Tag theme={channel.configured ? 'success' : 'warning'} variant="light">
                      {channel.configured ? '已配置' : '未配置'}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{channel.description || '用于账单相关通知。'}</Typography.Text>
                  <Select
                    size="small"
                    value={draft[channel.key]?.enabled ? 'enabled' : 'disabled'}
                    options={[
                      { label: '启用', value: 'enabled' },
                      { label: '停用', value: 'disabled' },
                    ]}
                    onChange={(value) => updateDraft(channel.key, { enabled: value === 'enabled' })}
                  />
                  <Select
                    size="small"
                    value={draft[channel.key]?.webhookFormat || 'generic'}
                    options={[
                      { label: '通用 Webhook', value: 'generic' },
                      { label: '飞书', value: 'feishu' },
                      { label: '钉钉', value: 'dingtalk' },
                    ]}
                    onChange={(value) => updateDraft(channel.key, { webhookFormat: String(value || 'generic') })}
                  />
                  <Input
                    size="small"
                    value={draft[channel.key]?.webhookUrl || ''}
                    placeholder={channel.source?.startsWith('env:') ? '已通过环境变量配置；填写后会覆盖' : '填写 Webhook 地址'}
                    onChange={(value) => updateDraft(channel.key, { webhookUrl: String(value || '') })}
                  />
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                    来源：{channel.source || 'unset'}
                  </Typography.Text>
                </Space>
              </Card>
            </Col>
          ))
        )}
      </Row>
    </Card>
  );
};

const PackageGrantCard = ({
  detail,
  loading,
  onGrantPackage,
}: {
  detail?: BillingUserDetailResponse | null;
  loading: boolean;
  onGrantPackage: (payload: PackageGrantPayload) => Promise<void> | void;
}) => {
  const [form, setForm] = useState<PackageGrantPayload>({
    packageKey: 'fission-pro',
    packageName: '图裂变套餐',
    businessKey: 'fission',
    units: 100,
    unitName: '次',
    expiresAt: '',
    description: '',
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const updateForm = (patch: Partial<PackageGrantPayload>) => setForm((current) => ({ ...current, ...patch }));

  const submit = async () => {
    if (!detail) {
      setLocalError('请先选择一个用户，再发放套餐。');
      return;
    }
    const packageKey = String(form.packageKey || '').trim();
    const units = Number(form.units || 0);
    if (!packageKey) {
      setLocalError('请填写套餐标识，例如 fission-pro。');
      return;
    }
    if (!Number.isFinite(units) || units <= 0) {
      setLocalError('套餐额度必须大于 0。');
      return;
    }
    setLocalError(null);
    await onGrantPackage({
      ...form,
      packageKey,
      packageName: String(form.packageName || '').trim() || null,
      businessKey: String(form.businessKey || '').trim() || null,
      unitName: String(form.unitName || '').trim() || '次',
      units,
      expiresAt: String(form.expiresAt || '').trim() || null,
      description: String(form.description || '').trim() || null,
    });
  };

  return (
    <Card bordered title="套餐赠送 / 补量">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme="info"
          message="用于内部给业务方补充套餐额度，先解决“能发放、能追踪、能到期提醒”；正式支付购买和企业月结后续再接。"
        />
        {localError ? <Alert theme="error" message={localError} /> : null}
        <Row gutter={[12, 12]}>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">套餐标识</Typography.Text>
            <Input value={form.packageKey} placeholder="例如 fission-pro" onChange={(value) => updateForm({ packageKey: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">套餐名称</Typography.Text>
            <Input value={form.packageName || ''} placeholder="给运营看的名称" onChange={(value) => updateForm({ packageName: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">适用业务</Typography.Text>
            <Select
              value={form.businessKey || ''}
              options={[
                { label: '通用额度', value: '' },
                ...coreBusinessKeys.map((key) => ({ label: businessKeyLabel(key), value: key })),
              ]}
              onChange={(value) => updateForm({ businessKey: String(value || '') })}
            />
          </Col>
          <Col xs={12} sm={3}>
            <Typography.Text theme="secondary">额度</Typography.Text>
            <Input value={String(form.units || '')} placeholder="100" onChange={(value) => updateForm({ units: Number(value || 0) })} />
          </Col>
          <Col xs={12} sm={3}>
            <Typography.Text theme="secondary">单位</Typography.Text>
            <Input value={form.unitName || '次'} placeholder="次" onChange={(value) => updateForm({ unitName: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">到期时间</Typography.Text>
            <Input value={form.expiresAt || ''} placeholder="YYYY-MM-DD，可留空" onChange={(value) => updateForm({ expiresAt: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">发放说明</Typography.Text>
            <Textarea
              autosize={{ minRows: 1, maxRows: 3 }}
              value={form.description || ''}
              placeholder="例如首批赠送、故障补偿、商务测试"
              onChange={(value) => updateForm({ description: String(value || '') })}
            />
          </Col>
        </Row>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary">
            当前用户：{detail ? detail.user.displayName || detail.user.username : '未选择'}
          </Typography.Text>
          <Button theme="primary" loading={loading} disabled={!detail} onClick={submit}>
            发放套餐
          </Button>
        </Space>
      </Space>
    </Card>
  );
};

const PackagePurchaseOrderCard = ({
  detail,
  orders,
  loading,
  onCreateOrder,
  onMarkPaid,
  invoiceRequests,
  onCreateInvoice,
  onMarkInvoiceIssued,
  formatDateTime,
}: {
  detail?: BillingUserDetailResponse | null;
  orders?: PackagePurchaseOrderListResponse | null;
  invoiceRequests?: BillingInvoiceRequestListResponse | null;
  loading: boolean;
  onCreateOrder: (payload: PackagePurchaseOrderCreatePayload) => Promise<void> | void;
  onMarkPaid: (orderId: string) => Promise<void> | void;
  onCreateInvoice: (orderId: string, title: string, taxNo?: string | null, email?: string | null) => Promise<void> | void;
  onMarkInvoiceIssued: (invoiceRequestId: string) => Promise<void> | void;
  formatDateTime: (value?: string | null) => string;
}) => {
  const [form, setForm] = useState<PackagePurchaseOrderCreatePayload>({
    userId: '',
    packageKey: 'fission-pro',
    packageName: '图裂变正式套餐',
    businessKey: 'fission',
    units: 300,
    unitName: '次',
    amountCents: 19900,
    currency: 'CNY',
    channel: 'offline',
    expiresAt: '',
    note: '',
  });
  const [invoiceDraft, setInvoiceDraft] = useState({ title: '', taxNo: '', email: '' });
  const [localError, setLocalError] = useState<string | null>(null);

  const updateForm = (patch: Partial<PackagePurchaseOrderCreatePayload>) =>
    setForm((current) => ({ ...current, ...patch }));

  const submit = async () => {
    if (!detail) {
      setLocalError('请先选择一个用户，再创建购买订单。');
      return;
    }
    const packageKey = String(form.packageKey || '').trim();
    const units = Number(form.units || 0);
    const amountCents = Number(form.amountCents || 0);
    if (!packageKey) {
      setLocalError('请填写套餐标识，例如 fission-pro。');
      return;
    }
    if (!Number.isFinite(units) || units <= 0) {
      setLocalError('购买额度必须大于 0。');
      return;
    }
    if (!Number.isFinite(amountCents) || amountCents < 0) {
      setLocalError('订单金额不能小于 0。');
      return;
    }
    setLocalError(null);
    await onCreateOrder({
      ...form,
      userId: detail.user.id,
      packageKey,
      packageName: String(form.packageName || '').trim() || null,
      businessKey: String(form.businessKey || '').trim() || null,
      unitName: String(form.unitName || '').trim() || '次',
      units,
      amountCents: Math.round(amountCents),
      currency: String(form.currency || 'CNY').trim() || 'CNY',
      channel: String(form.channel || 'offline').trim() || 'offline',
      expiresAt: String(form.expiresAt || '').trim() || null,
      note: String(form.note || '').trim() || null,
    });
  };

  const userOrders = (orders?.items || []).filter((item) => !detail || item.userId === detail.user.id);
  const userInvoices = (invoiceRequests?.items || []).filter((item) => !detail || item.userId === detail.user.id);

  const submitInvoice = async (orderId: string) => {
    const title = String(invoiceDraft.title || '').trim();
    if (!title) {
      setLocalError('请先填写发票抬头。');
      return;
    }
    setLocalError(null);
    await onCreateInvoice(orderId, title, invoiceDraft.taxNo || null, invoiceDraft.email || null);
  };

  return (
    <Card bordered title="套餐购买订单">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme="info"
          message="用于正式购买流程：先创建订单，确认企业转账或线下收款后标记已付款，系统再自动给该用户入账套餐额度。"
        />
        {localError ? <Alert theme="error" message={localError} /> : null}
        <Row gutter={[12, 12]}>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">套餐标识</Typography.Text>
            <Input value={form.packageKey} placeholder="例如 fission-pro" onChange={(value) => updateForm({ packageKey: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">套餐名称</Typography.Text>
            <Input value={form.packageName || ''} placeholder="给业务方看的名称" onChange={(value) => updateForm({ packageName: String(value || '') })} />
          </Col>
          <Col xs={12} sm={6}>
            <Typography.Text theme="secondary">适用业务</Typography.Text>
            <Select
              value={form.businessKey || ''}
              options={[
                { label: '通用额度', value: '' },
                ...coreBusinessKeys.map((key) => ({ label: businessKeyLabel(key), value: key })),
              ]}
              onChange={(value) => updateForm({ businessKey: String(value || '') })}
            />
          </Col>
          <Col xs={12} sm={3}>
            <Typography.Text theme="secondary">购买额度</Typography.Text>
            <Input value={String(form.units || '')} placeholder="300" onChange={(value) => updateForm({ units: Number(value || 0) })} />
          </Col>
          <Col xs={12} sm={3}>
            <Typography.Text theme="secondary">单位</Typography.Text>
            <Input value={form.unitName || '次'} placeholder="次" onChange={(value) => updateForm({ unitName: String(value || '') })} />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">订单金额</Typography.Text>
            <Input
              value={String(Number(form.amountCents || 0) / 100)}
              placeholder="199.00"
              onChange={(value) => updateForm({ amountCents: Math.round(Number(value || 0) * 100) })}
            />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">收款方式</Typography.Text>
            <Select
              value={form.channel || 'offline'}
              options={[
                { label: '线下收款', value: 'offline' },
                { label: '企业转账', value: 'bank_transfer' },
                { label: '手工确认', value: 'manual' },
              ]}
              onChange={(value) => updateForm({ channel: String(value || 'offline') })}
            />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">到期时间</Typography.Text>
            <Input value={form.expiresAt || ''} placeholder="YYYY-MM-DD，可留空" onChange={(value) => updateForm({ expiresAt: String(value || '') })} />
          </Col>
          <Col xs={12}>
            <Typography.Text theme="secondary">订单备注</Typography.Text>
            <Textarea
              autosize={{ minRows: 1, maxRows: 3 }}
              value={form.note || ''}
              placeholder="例如客户已发起转账，待财务确认"
              onChange={(value) => updateForm({ note: String(value || '') })}
            />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">发票抬头</Typography.Text>
            <Input value={invoiceDraft.title} placeholder="公司或个人名称" onChange={(value) => setInvoiceDraft((current) => ({ ...current, title: String(value || '') }))} />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">税号</Typography.Text>
            <Input value={invoiceDraft.taxNo} placeholder="企业发票填写税号" onChange={(value) => setInvoiceDraft((current) => ({ ...current, taxNo: String(value || '') }))} />
          </Col>
          <Col xs={12} sm={4}>
            <Typography.Text theme="secondary">接收邮箱</Typography.Text>
            <Input value={invoiceDraft.email} placeholder="finance@example.com" onChange={(value) => setInvoiceDraft((current) => ({ ...current, email: String(value || '') }))} />
          </Col>
        </Row>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary">
            当前用户：{detail ? detail.user.displayName || detail.user.username : '未选择'}
          </Typography.Text>
          <Button theme="primary" loading={loading} disabled={!detail} onClick={submit}>
            创建购买订单
          </Button>
        </Space>
        <Table
          size="small"
          rowKey="id"
          data={userOrders.slice(0, 8)}
          loading={loading}
          empty={<Typography.Text theme="secondary">当前用户暂无套餐购买订单。</Typography.Text>}
          columns={[
            {
              colKey: 'createdAt',
              title: '时间',
              width: 150,
              cell: ({ row }) => formatDateTime(row.createdAt || ''),
            },
            {
              colKey: 'order',
              title: '订单',
              minWidth: 220,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text code>{row.orderNo}</Typography.Text>
                  <Typography.Text theme="secondary">{row.packageName || row.packageKey}</Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'amount',
              title: '金额 / 额度',
              width: 150,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{formatMoney(row.amountCents, row.currency || 'CNY')}</Typography.Text>
                  <Typography.Text theme="secondary">{formatPackageUnits(row.units, row.unitName || '次')}</Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'status',
              title: '状态',
              width: 120,
              cell: ({ row }) => (
                <Tag theme={packagePurchaseStatusTheme(row.status)} variant="light">
                  {row.statusLabel || row.status}
                </Tag>
              ),
            },
            {
              colKey: 'action',
              title: '付款 / 发票',
              width: 190,
              cell: ({ row }) => {
                const invoice = userInvoices.find(
                  (item) => item.relatedOrderType === 'package_purchase_order' && item.relatedOrderId === row.id,
                );
                if (row.status === 'pending') {
                  return (
                    <Button size="small" theme="primary" variant="outline" loading={loading} onClick={() => onMarkPaid(row.id)}>
                      标记已付款
                    </Button>
                  );
                }
                if (invoice) {
                  return (
                    <Space direction="vertical" size={4}>
                      <Tag theme={invoiceStatusTheme(invoice.status)} variant="light">
                        {invoice.statusLabel || invoice.status}
                      </Tag>
                      {invoice.status === 'requested' ? (
                        <Button size="small" variant="outline" loading={loading} onClick={() => onMarkInvoiceIssued(invoice.id)}>
                          标记已开票
                        </Button>
                      ) : (
                        <Typography.Text theme="secondary">{invoice.invoiceNo || row.paymentReference || '-'}</Typography.Text>
                      )}
                    </Space>
                  );
                }
                return (
                  <Button size="small" variant="outline" loading={loading} onClick={() => submitInvoice(row.id)}>
                    申请发票
                  </Button>
                );
              },
            },
          ]}
        />
      </Space>
    </Card>
  );
};

export const BillingPanel = ({
  month,
  windowDays,
  tenantId,
  clientId,
  businessKey,
  overview,
  monthlySettlement,
  monthlySettlementRecords,
  packageAlertNotifications,
  monthlyCollectionNotifications,
  notificationConfig,
  packagePurchaseOrders,
  invoiceRequests,
  detail,
  selectedUserId,
  loading,
  exporting,
  error,
  onMonthChange,
  onWindowDaysChange,
  onTenantIdChange,
  onClientIdChange,
  onBusinessKeyChange,
  onRefresh,
  onExport,
  onSelectUser,
  onRetryIssue,
  onRefundIssue,
  onGrantPackage,
  onIssueMonthlySettlement,
  onMarkMonthlySettlementPaid,
  onRunPackageAlertNotification,
  onRunMonthlyCollectionNotification,
  onSaveNotificationConfig,
  onCreatePackagePurchaseOrder,
  onMarkPackagePurchaseOrderPaid,
  onCreateInvoiceRequest,
  onMarkInvoiceRequestIssued,
  formatDateTime,
}: {
  month: string;
  windowDays: number;
  tenantId: string;
  clientId: string;
  businessKey: string;
  overview?: BillingOverviewResponse | null;
  monthlySettlement?: BillingMonthlySettlementResponse | null;
  monthlySettlementRecords?: BillingMonthlySettlementListResponse | null;
  packageAlertNotifications?: PackageAlertNotificationListResponse | null;
  monthlyCollectionNotifications?: MonthlySettlementCollectionNotificationListResponse | null;
  notificationConfig?: BillingNotificationConfigResponse | null;
  packagePurchaseOrders?: PackagePurchaseOrderListResponse | null;
  invoiceRequests?: BillingInvoiceRequestListResponse | null;
  detail?: BillingUserDetailResponse | null;
  selectedUserId?: string;
  loading: boolean;
  exporting: boolean;
  error?: string | null;
  onMonthChange: (value: string) => void;
  onWindowDaysChange: (value: number) => void;
  onTenantIdChange: (value: string) => void;
  onClientIdChange: (value: string) => void;
  onBusinessKeyChange: (value: string) => void;
  onRefresh: () => void;
  onExport: () => void;
  onSelectUser: (userId: string) => void;
  onRetryIssue: (runId: string) => void;
  onRefundIssue: (runId: string) => void;
  onGrantPackage: (payload: PackageGrantPayload) => Promise<void> | void;
  onIssueMonthlySettlement: (tenantId?: string | null, clientId?: string | null) => Promise<void> | void;
  onMarkMonthlySettlementPaid: (settlementId: string) => Promise<void> | void;
  onRunPackageAlertNotification: (send: boolean, notificationTemplate?: string) => Promise<void> | void;
  onRunMonthlyCollectionNotification: (send: boolean, notificationTemplate?: string) => Promise<void> | void;
  onSaveNotificationConfig: (
    channels: Array<{
      key: string;
      enabled: boolean;
      webhookUrl?: string | null;
      webhookFormat?: string | null;
    }>,
  ) => Promise<void> | void;
  onCreatePackagePurchaseOrder: (payload: PackagePurchaseOrderCreatePayload) => Promise<void> | void;
  onMarkPackagePurchaseOrderPaid: (orderId: string) => Promise<void> | void;
  onCreateInvoiceRequest: (orderId: string, title: string, taxNo?: string | null, email?: string | null) => Promise<void> | void;
  onMarkInvoiceRequestIssued: (invoiceRequestId: string) => Promise<void> | void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Alert
      theme="info"
      message="当前只保留账单框架：用于成本核对、流水查看和对账导出。充值、支付、正式发票和完整收费体验放到后一阶段，不作为当前主线验收。"
    />
    {error ? <Alert theme="error" message={error} /> : null}
    <BillingActionPanel overview={overview} detail={detail} formatDateTime={formatDateTime} />
    <BillingNotificationConfigCard config={notificationConfig} loading={loading} onSave={onSaveNotificationConfig} />
    <Card bordered>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
        <Space breakLine>
          <Typography.Text theme="secondary">账期</Typography.Text>
          <Input
            style={{ width: 140 }}
            value={month}
            placeholder="YYYY-MM"
            onChange={(value) => onMonthChange(String(value || '').slice(0, 7))}
          />
          <Typography.Text theme="secondary">统计窗口</Typography.Text>
          <Select
            style={{ width: 140 }}
            value={windowDays}
            options={[
              { label: '最近 7 天', value: 7 },
              { label: '最近 30 天', value: 30 },
              { label: '最近 90 天', value: 90 },
            ]}
            onChange={(value) => onWindowDaysChange(Number(value || 30))}
          />
          <Typography.Text theme="secondary">业务</Typography.Text>
          <Select
            style={{ width: 160 }}
            value={businessKey}
            options={[
              { label: '全部业务', value: 'all' },
              ...coreBusinessKeys.map((key) => ({ label: businessKeyLabel(key), value: key })),
            ]}
            onChange={(value) => onBusinessKeyChange(String(value || 'all'))}
          />
          <Typography.Text theme="secondary">业务方</Typography.Text>
          <Input
            style={{ width: 160 }}
            value={tenantId}
            placeholder="tenantId，可留空"
            onChange={(value) => onTenantIdChange(String(value || ''))}
          />
          <Typography.Text theme="secondary">客户端</Typography.Text>
          <Input
            style={{ width: 160 }}
            value={clientId}
            placeholder="clientId，可留空"
            onChange={(value) => onClientIdChange(String(value || ''))}
          />
        </Space>
        <Space>
          <Button variant="outline" loading={loading} onClick={onRefresh}>
            刷新账单
          </Button>
          <Button variant="outline" loading={exporting} disabled={!selectedUserId} onClick={onExport}>
            导出当前用户流水
          </Button>
        </Space>
      </Space>
    </Card>
    <Row gutter={[12, 12]}>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard label="用户数" value={overview?.totalUsers ?? 0} sub="纳入本次对账" />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="异常样本"
          value={overview?.issueCount ?? 0}
          sub={(overview?.issueCount ?? 0) > 0 ? '需要先核对' : '暂无异常'}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="总余额"
          value={formatPoints(overview?.totalBalance)}
          sub={`冻结 ${formatPoints(overview?.totalFrozenBalance)}`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="本月扣费"
          value={formatPoints(overview?.totalExpense)}
          sub={`流水 ${overview?.expenseCount ?? 0} 笔`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="本月入账"
          value={formatPoints(overview?.totalIncome)}
          sub={`流水 ${overview?.incomeCount ?? 0} 笔`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard label="账期净额" value={formatSignedPoints(overview?.totalNet)} sub={overview?.month || month} />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="窗口消耗"
          value={formatPoints(overview?.totalExpensePoints)}
          sub={`最近 ${overview?.windowDays || windowDays} 天`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BillingMetricCard
          label="套餐余量"
          value={formatPackageUnits(overview?.totalPackageRemainingUnits)}
          sub="独立套餐额度"
        />
      </Col>
    </Row>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>异常扣费样本</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                只展示需要人工核对的样本：成功未定价、扣费失败、应扣未扣、失败后仍扣费。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={(overview?.issueCount || 0) > 0 ? 'warning' : 'success'} variant="light">
            {(overview?.issueCount || 0) > 0 ? `${overview?.issueCount} 条需处理` : '暂无异常'}
          </Tag>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={overview?.issues || []}
        loading={loading}
        empty={<Typography.Text theme="secondary">当前筛选下暂无异常扣费样本。</Typography.Text>}
        columns={[
          {
            colKey: 'createdAt',
            title: '时间',
            width: 160,
            cell: ({ row }) => formatDateTime(row.createdAt || ''),
          },
          {
            colKey: 'issue',
            title: '问题',
            minWidth: 220,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text theme="warning">{row.issueLabel}</Typography.Text>
                <Typography.Text theme="secondary">{row.issueType}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'business',
            title: '业务',
            width: 150,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{businessKeyLabel(row.businessKey)}</Typography.Text>
                <Typography.Text theme="secondary">{row.version || '未标记版本'}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'owner',
            title: '归属',
            minWidth: 180,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.userName || row.userId || '未绑定用户'}</Typography.Text>
                <Typography.Text theme="secondary">
                  {row.tenantId || '未绑定业务方'} · {row.clientId || '未绑定客户端'}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'billing',
            title: '费用状态',
            minWidth: 180,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Space size={4}>
                  <Tag theme={businessBillingStatusTheme(row.billingStatus)} variant="light">
                    {businessBillingStatusLabel(row.billingStatus)}
                  </Tag>
                  <Tag
                    theme={row.walletStatus === 'failed' ? 'danger' : row.walletStatus === 'settled' ? 'success' : 'default'}
                    variant="light"
                  >
                    {row.walletStatus === 'settled' ? '已扣费' : row.walletStatus === 'failed' ? '扣费失败' : '未扣费'}
                  </Tag>
                </Space>
                <Typography.Text theme="secondary">
                  成本 {formatPriceValue(row.costAmount || undefined, row.currency || undefined)} · 额度 {row.quotaUnits ?? 0}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'run',
            title: '任务',
            width: 180,
            cell: ({ row }) => <Typography.Text code>{row.runId}</Typography.Text>,
          },
          {
            colKey: 'action',
            title: '操作',
            width: 120,
            cell: ({ row }) => {
              if (row.issueType === 'wallet_failed' || row.issueType === 'wallet_missing') {
                return (
                  <Button size="small" theme="primary" variant="outline" loading={loading} onClick={() => onRetryIssue(row.runId)}>
                    重试扣费
                  </Button>
                );
              }
              if (row.issueType === 'failed_run_charged') {
                return (
                  <Button size="small" theme="danger" variant="outline" loading={loading} onClick={() => onRefundIssue(row.runId)}>
                    退回扣费
                  </Button>
                );
              }
              return <Typography.Text theme="secondary">先补定价</Typography.Text>;
            },
          },
        ]}
      />
    </Card>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>套餐预警样本</Typography.Text>
            <div>
              <Typography.Text theme="secondary">展示快到期和低余量套餐，用于提前续期、补赠送或调整业务计费策略。</Typography.Text>
            </div>
          </div>
          <Space>
            <Button size="small" variant="outline" loading={loading} onClick={() => onRunPackageAlertNotification(false, 'ops_digest')}>
              生成预警记录
            </Button>
            <Button size="small" theme="warning" variant="outline" loading={loading} onClick={() => onRunPackageAlertNotification(true, 'client_followup')}>
              发送外部通知
            </Button>
            <Tag theme={(overview?.packageAlertCount || 0) > 0 ? 'warning' : 'success'} variant="light">
              {(overview?.packageAlertCount || 0) > 0 ? `${overview?.packageAlertCount} 条预警` : '暂无预警'}
            </Tag>
          </Space>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={overview?.packageAlerts || []}
        loading={loading}
        empty={<Typography.Text theme="secondary">当前筛选下暂无套餐到期或低余量预警。</Typography.Text>}
        columns={[
          {
            colKey: 'alert',
            title: '预警',
            width: 150,
            cell: ({ row }) => (
              <Tag theme={row.alertType === 'expiring_soon' ? 'warning' : 'danger'} variant="light">
                {row.alertLabel}
              </Tag>
            ),
          },
          {
            colKey: 'user',
            title: '用户 / 归属',
            minWidth: 220,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.userName || row.userId}</Typography.Text>
                <Typography.Text theme="secondary">
                  {row.tenantId || '未绑定业务方'} · {row.clientId || '未绑定客户端'}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'package',
            title: '套餐',
            minWidth: 220,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.packageName || row.packageKey}</Typography.Text>
                <Typography.Text theme="secondary">
                  {row.businessKey ? businessKeyLabel(row.businessKey) : '通用额度'} · {row.packageKey}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'remaining',
            title: '剩余 / 总量',
            width: 170,
            cell: ({ row }) => (
              <Typography.Text theme={Number(row.remainingUnits || 0) <= Math.max(1, Number(row.totalUnits || 0) * 0.2) ? 'warning' : 'success'}>
                {formatPackageUnits(row.remainingUnits, row.unitName || '次')} / {formatPackageUnits(row.totalUnits, row.unitName || '次')}
              </Typography.Text>
            ),
          },
          {
            colKey: 'expiresAt',
            title: '到期',
            width: 190,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.expiresAt ? formatDateTime(row.expiresAt) : '长期有效'}</Typography.Text>
                {row.daysUntilExpiry !== null && row.daysUntilExpiry !== undefined ? (
                  <Typography.Text theme={Number(row.daysUntilExpiry) <= 7 ? 'warning' : 'secondary'}>剩余 {row.daysUntilExpiry} 天</Typography.Text>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
    </Card>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>套餐预警通知记录</Typography.Text>
            <div>
              <Typography.Text theme="secondary">记录每次生成或发送的套餐到期、低余量提醒，便于确认是否已经通知业务方。</Typography.Text>
            </div>
          </div>
          <Tag theme={(packageAlertNotifications?.total || 0) > 0 ? 'primary' : 'default'} variant="light">
            最近 {packageAlertNotifications?.total || 0} 条
          </Tag>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={packageAlertNotifications?.items || []}
        loading={loading}
        empty={<Typography.Text theme="secondary">暂无套餐预警通知记录。</Typography.Text>}
        columns={[
          {
            colKey: 'createdAt',
            title: '时间',
            width: 170,
            cell: ({ row }) => formatDateTime(row.sentAt || row.createdAt || ''),
          },
          {
            colKey: 'status',
            title: '状态',
            width: 130,
            cell: ({ row }) => {
              const meta = notificationStatusMeta(row.sendStatus);
              return (
                <Tag theme={meta.theme} variant="light">
                  {meta.label}
                </Tag>
              );
            },
          },
          {
            colKey: 'alerts',
            title: '预警内容',
            minWidth: 190,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.alertCount || 0} 条预警</Typography.Text>
                <Typography.Text theme="secondary">
                  到期 {row.expiringSoonCount || 0} · 低余量 {row.lowBalanceCount || 0}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'template',
            title: '模板 / 动作',
            width: 190,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag theme={row.notificationTemplate === 'client_followup' ? 'primary' : 'default'} variant="light">
                  {notificationTemplateLabel(row.notificationTemplate)}
                </Tag>
                <Typography.Text theme="secondary">{notificationNextActionLabel(row.nextAction)}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'webhook',
            title: '外部通知',
            width: 150,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag theme={row.webhookConfigured ? 'success' : 'warning'} variant="light">
                  {row.webhookConfigured ? '已配置' : '未配置'}
                </Tag>
                <Typography.Text theme="secondary">{row.webhookFormat || 'generic'}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'operator',
            title: '操作人',
            width: 150,
            cell: ({ row }) => row.createdByUsername || row.createdByUserId || '系统',
          },
          {
            colKey: 'detail',
            title: '详情',
            minWidth: 260,
            cell: ({ row }) => <Typography.Text theme={row.sendStatus === 'failed' ? 'error' : 'secondary'}>{row.sendDetail || '-'}</Typography.Text>,
          },
        ]}
      />
    </Card>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>企业月结预览</Typography.Text>
            <div>
              <Typography.Text theme="secondary">按业务方和客户端聚合账期金额、套餐余量和风险，先判断哪些客户可以进入月结。</Typography.Text>
            </div>
          </div>
          <Space>
            <Button size="small" variant="outline" loading={loading} onClick={() => onRunMonthlyCollectionNotification(false, 'ops_digest')}>
              生成催收记录
            </Button>
            <Button size="small" theme="warning" variant="outline" loading={loading} onClick={() => onRunMonthlyCollectionNotification(true, 'finance_collection')}>
              发送催收通知
            </Button>
            <Tag theme={(monthlySettlement?.issueGroupCount || 0) > 0 ? 'warning' : 'success'} variant="light">
              {monthlySettlement?.totalGroups || 0} 个归属组
            </Tag>
            <Tag theme={(monthlySettlementRecords?.total || 0) > 0 ? 'primary' : 'default'} variant="light">
              已出账 {monthlySettlementRecords?.total || 0}
            </Tag>
          </Space>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={monthlySettlement?.items || []}
        loading={loading}
        empty={<Typography.Text theme="secondary">当前筛选下暂无可月结客户。</Typography.Text>}
        columns={[
          {
            colKey: 'scope',
            title: '业务方 / 客户端',
            minWidth: 220,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.tenantId || '未绑定业务方'}</Typography.Text>
                <Typography.Text theme="secondary">{row.clientId || '未绑定客户端'} · {row.userCount || 0} 个用户</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'status',
            title: '月结状态',
            width: 150,
            cell: ({ row }) => (
              <Tag
                theme={row.settlementStatus === 'needs_review' ? 'danger' : row.settlementStatus === 'package_warning' ? 'warning' : 'success'}
                variant="light"
              >
                {row.settlementLabel}
              </Tag>
            ),
          },
          {
            colKey: 'expense',
            title: '本月扣费 / 入账',
            width: 170,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text theme={Number(row.totalExpense || 0) > 0 ? 'warning' : 'secondary'}>{formatPoints(row.totalExpense)}</Typography.Text>
                <Typography.Text theme="secondary">入账 {formatPoints(row.totalIncome)}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'net',
            title: '净额 / 余额',
            width: 170,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{formatSignedPoints(row.totalNet)}</Typography.Text>
                <Typography.Text theme="secondary">余额 {formatPoints(row.totalBalance)}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'package',
            title: '套餐',
            width: 180,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{formatPackageUnits(row.totalPackageRemainingUnits)}</Typography.Text>
                <Typography.Text theme={Number(row.packageAlertCount || 0) > 0 ? 'warning' : 'secondary'}>
                  预警 {row.packageAlertCount || 0} 条
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'issues',
            title: '异常',
            width: 120,
            cell: ({ row }) => (
              <Typography.Text theme={Number(row.issueCount || 0) > 0 ? 'warning' : 'secondary'}>{row.issueCount || 0} 条</Typography.Text>
            ),
          },
          {
            colKey: 'action',
            title: '出账',
            width: 150,
            cell: ({ row }) => {
              const businessFilterKey = businessKey === 'all' ? null : businessKey;
              const record = (monthlySettlementRecords?.items || []).find(
                (item) =>
                  settlementScopeKey(item.tenantId, item.clientId, item.businessKey) ===
                  settlementScopeKey(row.tenantId, row.clientId, businessFilterKey),
              );
              if (record) {
                return (
                  <Space direction="vertical" size={4}>
                    <Tag theme={settlementRecordTheme(record.status)} variant="light">
                      {record.statusLabel}
                    </Tag>
                    <Tag theme={collectionLevelTheme(record.collectionLevel)} variant="light">
                      {collectionLevelLabel(record.collectionLevel)}
                    </Tag>
                    <Typography.Text theme="secondary">
                      {record.daysSinceIssued !== null && record.daysSinceIssued !== undefined
                        ? `出账 ${record.daysSinceIssued} 天`
                        : record.collectionAction}
                    </Typography.Text>
                    {record.status === 'issued' ? (
                      <Button size="small" variant="outline" loading={loading} onClick={() => onMarkMonthlySettlementPaid(record.id)}>
                        标记已付款
                      </Button>
                    ) : null}
                  </Space>
                );
              }
              if (Number(row.issueCount || 0) > 0) {
                return <Typography.Text theme="secondary">先处理异常</Typography.Text>;
              }
              return (
                <Button size="small" theme="primary" variant="outline" loading={loading} onClick={() => onIssueMonthlySettlement(row.tenantId, row.clientId)}>
                  生成月结单
                </Button>
              );
            },
          },
        ]}
      />
    </Card>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>月结催收通知记录</Typography.Text>
            <div>
              <Typography.Text theme="secondary">记录每次生成或发送的月结催收提醒，用于确认哪些客户已经进入付款跟进。</Typography.Text>
            </div>
          </div>
          <Tag theme={(monthlyCollectionNotifications?.total || 0) > 0 ? 'primary' : 'default'} variant="light">
            最近 {monthlyCollectionNotifications?.total || 0} 条
          </Tag>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={monthlyCollectionNotifications?.items || []}
        loading={loading}
        empty={<Typography.Text theme="secondary">暂无月结催收通知记录。</Typography.Text>}
        columns={[
          {
            colKey: 'createdAt',
            title: '时间',
            width: 170,
            cell: ({ row }) => formatDateTime(row.sentAt || row.createdAt || ''),
          },
          {
            colKey: 'status',
            title: '状态',
            width: 130,
            cell: ({ row }) => {
              const meta = notificationStatusMeta(row.sendStatus);
              return (
                <Tag theme={meta.theme} variant="light">
                  {meta.label}
                </Tag>
              );
            },
          },
          {
            colKey: 'settlements',
            title: '催收内容',
            minWidth: 210,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.settlementCount || 0} 张月结单</Typography.Text>
                <Typography.Text theme="secondary">
                  提醒 {row.remindCount || 0} · 跟进 {row.followUpCount || 0} · 升级 {row.escalateCount || 0}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'template',
            title: '模板 / 动作',
            width: 190,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag theme={row.notificationTemplate === 'finance_collection' ? 'warning' : 'default'} variant="light">
                  {notificationTemplateLabel(row.notificationTemplate)}
                </Tag>
                <Typography.Text theme="secondary">{notificationNextActionLabel(row.nextAction)}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'webhook',
            title: '外部通知',
            width: 150,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag theme={row.webhookConfigured ? 'success' : 'warning'} variant="light">
                  {row.webhookConfigured ? '已配置' : '未配置'}
                </Tag>
                <Typography.Text theme="secondary">{row.webhookFormat || 'generic'}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'operator',
            title: '操作人',
            width: 150,
            cell: ({ row }) => row.createdByUsername || row.createdByUserId || '系统',
          },
          {
            colKey: 'detail',
            title: '详情',
            minWidth: 260,
            cell: ({ row }) => <Typography.Text theme={row.sendStatus === 'failed' ? 'error' : 'secondary'}>{row.sendDetail || '-'}</Typography.Text>,
          },
        ]}
      />
    </Card>
    <Row gutter={[16, 16]}>
      <Col xs={12} lg={7}>
        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <div>
                <Typography.Text strong>用户账单总览</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">点选用户查看明细和流水。</Typography.Text>
                </div>
              </div>
              <Tag variant="light">账期 {overview?.month || month}</Tag>
            </Space>
          }
        >
          <Table
            size="small"
            rowKey="id"
            data={(overview?.items || []).map((item) => ({ ...item, id: item.user.id }))}
            loading={loading}
            empty={<Typography.Text theme="secondary">暂无账单用户。</Typography.Text>}
            columns={[
              {
                colKey: 'user',
                title: '用户',
                minWidth: 220,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.user.displayName || row.user.username}</Typography.Text>
                    <Typography.Text theme="secondary">{row.user.email || row.user.id}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'scope',
                title: '业务归属',
                minWidth: 160,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.user.tenantId || '未绑定业务方'}</Typography.Text>
                    <Typography.Text theme="secondary">{row.user.clientId || '未绑定客户端'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'balance',
                title: '余额',
                width: 140,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{formatPoints(row.balance)}</Typography.Text>
                    <Typography.Text theme="secondary">冻结 {formatPoints(row.frozenBalance)}</Typography.Text>
                    <Typography.Text theme="secondary">套餐 {formatPackageUnits(row.packageRemainingUnits)}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'month',
                title: '本月账单',
                width: 150,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme={Number(row.expense || 0) > 0 ? 'warning' : 'secondary'}>
                      扣费 {formatPoints(row.expense)}
                    </Typography.Text>
                    <Typography.Text theme="secondary">入账 {formatPoints(row.income)}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'action',
                title: '操作',
                width: 110,
                cell: ({ row }) => (
                  <Button
                    size="small"
                    theme={selectedUserId === row.user.id ? 'primary' : 'default'}
                    variant="outline"
                    onClick={() => onSelectUser(row.user.id)}
                  >
                    查看明细
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={12} lg={5}>
        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <div>
                <Typography.Text strong>用户明细</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">
                    {detail ? `${detail.user.displayName || detail.user.username} · ${detail.user.role}` : '请选择左侧用户'}
                  </Typography.Text>
                </div>
              </div>
              {detail ? <StatusBadge status={detail.user.status} /> : null}
            </Space>
          }
        >
          {detail ? (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Row gutter={[12, 12]}>
                <Col xs={12} sm={6}>
                  <BillingMetricCard
                    label="当前余额"
                    value={formatPoints(detail.balance.balance)}
                    sub={`冻结 ${formatPoints(detail.balance.frozenBalance)}`}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <BillingMetricCard label="本月净额" value={formatSignedPoints(detail.bill.net)} sub={`流水 ${detail.bill.count || 0} 笔`} />
                </Col>
                <Col xs={12} sm={6}>
                  <BillingMetricCard
                    label="窗口扣费"
                    value={formatPoints(detail.usage.totalExpensePoints)}
                    sub={`${detail.usage.expenseCount || 0} 笔扣费`}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <BillingMetricCard
                    label="成本快照"
                    value={formatPoints(detail.costSnapshots.totalPoints)}
                    sub={`${detail.costSnapshots.count || 0} 条`}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <BillingMetricCard
                    label="套餐余量"
                    value={formatPackageUnits(detail.packageBalances.totalRemainingUnits)}
                    sub={`${detail.packageBalances.items.length || 0} 个套餐`}
                  />
                </Col>
              </Row>
              <PackagePurchaseOrderCard
                detail={detail}
                orders={packagePurchaseOrders}
                invoiceRequests={invoiceRequests}
                loading={loading}
                onCreateOrder={onCreatePackagePurchaseOrder}
                onMarkPaid={onMarkPackagePurchaseOrderPaid}
                onCreateInvoice={onCreateInvoiceRequest}
                onMarkInvoiceIssued={onMarkInvoiceRequestIssued}
                formatDateTime={formatDateTime}
              />
              <PackageGrantCard detail={detail} loading={loading} onGrantPackage={onGrantPackage} />
              <Row gutter={[12, 12]}>
                <Col xs={12} sm={6}>
                  <Card bordered title="厂商消耗">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      {(detail.usage.providers || []).slice(0, 5).map((item) => (
                        <Space key={item.key} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Typography.Text>{item.key}</Typography.Text>
                          <Typography.Text theme="secondary">{formatPoints(item.points)} · {item.count} 次</Typography.Text>
                        </Space>
                      ))}
                      {(detail.usage.providers || []).length === 0 ? (
                        <Typography.Text theme="secondary">暂无厂商消耗。</Typography.Text>
                      ) : null}
                    </Space>
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card bordered title="模型消耗">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      {(detail.usage.models || []).slice(0, 5).map((item) => (
                        <Space key={item.key} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Typography.Text>{item.key}</Typography.Text>
                          <Typography.Text theme="secondary">{formatPoints(item.points)} · {item.count} 次</Typography.Text>
                        </Space>
                      ))}
                      {(detail.usage.models || []).length === 0 ? (
                        <Typography.Text theme="secondary">暂无模型消耗。</Typography.Text>
                      ) : null}
                    </Space>
                  </Card>
                </Col>
              </Row>
              <Card bordered title="套餐余额">
                <Table
                  size="small"
                  rowKey="id"
                  data={detail.packageBalances.items || []}
                  loading={loading}
                  empty={<Typography.Text theme="secondary">暂无套餐额度。</Typography.Text>}
                  columns={[
                    {
                      colKey: 'package',
                      title: '套餐',
                      minWidth: 180,
                      cell: ({ row }) => (
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{row.packageName || row.packageKey}</Typography.Text>
                          <Typography.Text theme="secondary">
                            {row.businessKey ? businessKeyLabel(row.businessKey) : '通用额度'}
                          </Typography.Text>
                        </Space>
                      ),
                    },
                    {
                      colKey: 'remaining',
                      title: '剩余',
                      width: 120,
                      cell: ({ row }) => (
                        <Typography.Text theme={Number(row.remainingUnits || 0) > 0 ? 'success' : 'secondary'}>
                          {formatPackageUnits(row.remainingUnits, row.unitName || '次')}
                        </Typography.Text>
                      ),
                    },
                    {
                      colKey: 'used',
                      title: '已用 / 总量',
                      width: 140,
                      cell: ({ row }) =>
                        `${Number(row.usedUnits || 0).toLocaleString('zh-CN')} / ${Number(row.totalUnits || 0).toLocaleString('zh-CN')}`,
                    },
                    {
                      colKey: 'expiresAt',
                      title: '有效期',
                      width: 160,
                      cell: ({ row }) => (row.expiresAt ? formatDateTime(row.expiresAt) : '长期有效'),
                    },
                  ]}
                />
              </Card>
              <Table
                size="small"
                rowKey="id"
                data={detail.ledger.items || []}
                loading={loading}
                empty={<Typography.Text theme="secondary">暂无流水。</Typography.Text>}
                columns={[
                  {
                    colKey: 'createdAt',
                    title: '时间',
                    width: 160,
                    cell: ({ row }) => formatDateTime(row.createdAt || ''),
                  },
                  {
                    colKey: 'changeType',
                    title: '类型',
                    width: 110,
                    cell: ({ row }) => <Tag variant="light">{row.changeType}</Tag>,
                  },
                  {
                    colKey: 'points',
                    title: '点数',
                    width: 110,
                    cell: ({ row }) => (
                      <Typography.Text theme={Number(row.points || 0) < 0 || isExpenseChangeType(row.changeType) ? 'warning' : 'success'}>
                        {formatLedgerPoints(row.changeType, row.points)}
                      </Typography.Text>
                    ),
                  },
                  {
                    colKey: 'desc',
                    title: '说明',
                    minWidth: 180,
                    cell: ({ row }) => (
                      <Space direction="vertical" size={2}>
                        <Typography.Text>{row.description || row.taskId || '—'}</Typography.Text>
                        <Typography.Text theme="secondary">
                          {row.provider || '未记录厂商'} · {row.modelKey || '未记录模型'}
                        </Typography.Text>
                      </Space>
                    ),
                  },
                ]}
              />
            </Space>
          ) : (
            <Typography.Text theme="secondary">左侧暂无可选用户，或账单数据还没有加载。</Typography.Text>
          )}
        </Card>
      </Col>
    </Row>
  </Space>
);
