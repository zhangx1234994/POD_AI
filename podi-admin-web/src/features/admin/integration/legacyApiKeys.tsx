import { Alert, Button, Card, Col, Input, InputNumber, Row, Select, Space, Table, Tag, Typography } from 'tdesign-react';
import type { ApiKey, ApiKeyFormState } from '../../../types/admin';
import { ActionBar, StatusBadge } from '../shared/ui';
import { apiKeyStatusOptions, providerOptions } from './formOptions';
import { formatDateTime } from './formatters';

const formControlClass =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';

const statusCountLabel = (status: 'active' | 'disabled') => (status === 'active' ? '可用' : '停用');

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

type LegacyApiKeysPanelProps = {
  apiKeys: ApiKey[];
  apiKeyForm: ApiKeyFormState;
  onFormChange: (next: ApiKeyFormState) => void;
  onSubmit: () => void;
  onDelete: (id: number | string) => void;
  onReset: () => void;
  getProviderLabel: (value: string) => string;
};

export function LegacyApiKeysPanel({
  apiKeys,
  apiKeyForm,
  onFormChange,
  onSubmit,
  onDelete,
  onReset,
  getProviderLabel,
}: LegacyApiKeysPanelProps) {
  const activeCount = apiKeys.filter((item) => item.status === 'active').length;
  const disabledCount = apiKeys.filter((item) => item.status === 'disabled').length;

  return (
    <>
      <ActionBar>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <Space direction="vertical" size={4}>
            <Typography.Text strong>旧凭证池总览</Typography.Text>
            <Typography.Text theme="secondary">
              这里只保留旧版服务兼容密钥。OpenAI、KIE、火山等第三方模型密钥后续统一迁到“模型弹药库”。
            </Typography.Text>
          </Space>
          <Space size="small" style={{ flexWrap: 'wrap' }}>
            <Tag variant="light">总数 {apiKeys.length}</Tag>
            <Tag variant="light" theme="success">
              {statusCountLabel('active')} {activeCount}
            </Tag>
            <Tag variant="light" theme="warning">
              {statusCountLabel('disabled')} {disabledCount}
            </Tag>
          </Space>
        </Space>
      </ActionBar>

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={7}>
          <Card bordered title="密钥列表" style={{ width: '100%' }}>
            <Table
              size="small"
              rowKey="id"
              data={apiKeys}
              columns={[
                {
                  colKey: 'provider',
                  title: '厂商',
                  width: 140,
                  cell: ({ row }) => <Typography.Text>{getProviderLabel(row.provider)}</Typography.Text>,
                },
                {
                  colKey: 'name',
                  title: '名称 / 密钥预览',
                  minWidth: 180,
                  ellipsis: true,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.name}</Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {row.key_preview || '***'} · {row.id}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'status',
                  title: '状态',
                  width: 120,
                  cell: ({ row }) => <StatusPill status={row.status} />,
                },
                {
                  colKey: 'quota',
                  title: '配额/用量',
                  width: 140,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {(row.usage_count ?? 0)}/{row.daily_quota ?? '—'}
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'expire_at',
                  title: '过期时间',
                  width: 180,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">{row.expire_at ? formatDateTime(row.expire_at) : '—'}</Typography.Text>
                  ),
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 160,
                  cell: ({ row }) => (
                    <Space size={4}>
                      <Button size="small" variant="text" onClick={() => onFormChange(row)}>
                        编辑
                      </Button>
                      <Button size="small" theme="danger" variant="text" onClick={() => onDelete(row.id)}>
                        删除
                      </Button>
                    </Space>
                  ),
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无密钥，请先新增。</Typography.Text>}
            />
          </Card>
        </Col>

        <Col xs={12} lg={5}>
          <Card bordered title={apiKeyForm.id ? '编辑密钥' : '新增密钥'} style={{ width: '100%' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Alert
                theme="info"
                message="厂商用于区分来源，名称用于内部识别；新增时粘贴完整密钥，编辑模式下不会回显明文。旧凭证池只做兼容，新能力优先使用“模型弹药库”。"
              />

              <Row gutter={[12, 12]}>
                <Col span={6}>
                  <Typography.Text theme="secondary">厂商</Typography.Text>
                  <Select
                    value={apiKeyForm.provider || ''}
                    onChange={(v) => onFormChange({ ...apiKeyForm, provider: String(v) })}
                    options={[
                      { label: '请选择厂商…', value: '' },
                      ...providerOptions
                        .filter((opt) => ['baidu', 'volcengine', 'kie', 'openai', 'aliyun', 'coze'].includes(opt.value))
                        .map((opt) => ({
                          label: `${opt.label} (${opt.value})`,
                          value: opt.value,
                        })),
                    ]}
                  />
                </Col>
                <Col span={6}>
                  <Typography.Text theme="secondary">状态</Typography.Text>
                  <Select
                    value={apiKeyForm.status || 'active'}
                    onChange={(v) => onFormChange({ ...apiKeyForm, status: String(v) })}
                    options={apiKeyStatusOptions.map((item) => ({ ...item }))}
                  />
                </Col>
              </Row>

              <div>
                <Typography.Text theme="secondary">名称</Typography.Text>
                <Input
                  value={apiKeyForm.name || ''}
                  onChange={(v) => onFormChange({ ...apiKeyForm, name: String(v) })}
                  placeholder="例如：KIE-主账号"
                />
              </div>

              {!apiKeyForm.id ? (
                <div>
                  <Typography.Text theme="secondary">密钥值</Typography.Text>
                  <Input
                    type="password"
                    value={apiKeyForm.key || ''}
                    onChange={(v) => onFormChange({ ...apiKeyForm, key: String(v) })}
                  placeholder="粘贴接口密钥（保存后不展示明文）"
                  />
                </div>
              ) : (
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  编辑模式不展示明文密钥；如需更换，请直接粘贴新值并保存。
                </Typography.Text>
              )}

              <Row gutter={[12, 12]}>
                <Col span={6}>
                  <Typography.Text theme="secondary">日配额</Typography.Text>
                  <InputNumber
                    min={0}
                    value={apiKeyForm.daily_quota ?? undefined}
                    onChange={(v) =>
                      onFormChange({ ...apiKeyForm, daily_quota: v === undefined || v === null ? undefined : Number(v) })
                    }
                  />
                </Col>
                <Col span={6}>
                  <Typography.Text theme="secondary">当前用量</Typography.Text>
                  <InputNumber
                    min={0}
                    value={apiKeyForm.usage_count ?? undefined}
                    onChange={(v) =>
                      onFormChange({ ...apiKeyForm, usage_count: v === undefined || v === null ? undefined : Number(v) })
                    }
                  />
                </Col>
              </Row>

              <div>
                <Typography.Text theme="secondary">过期时间（可选）</Typography.Text>
                <input
                  type="datetime-local"
                  value={apiKeyForm.expire_at ? new Date(apiKeyForm.expire_at).toISOString().slice(0, 16) : ''}
                  onChange={(event) =>
                    onFormChange({
                      ...apiKeyForm,
                      expire_at: event.target.value ? new Date(event.target.value).toISOString() : undefined,
                    })
                  }
                  className={formControlClass}
                />
              </div>

              <Space style={{ width: '100%' }}>
                <Button theme="primary" style={{ flex: 1 }} onClick={onSubmit}>
                  保存
                </Button>
                {apiKeyForm.id ? (
                  <Button variant="outline" onClick={onReset}>
                    取消
                  </Button>
                ) : null}
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </>
  );
}
