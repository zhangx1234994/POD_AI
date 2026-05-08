import { Card, Col, Row, Space, Tag, Typography } from 'tdesign-react';
import type { SystemConfig } from '../../../types/admin';
import { ActionBar, OperationFlowCard } from '../shared/ui';

function InfoCard({ title, items }: { title: string; items: { label: string; value: string }[] }) {
  return (
    <Card title={title} bordered>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {items.map((item) => (
          <Row key={item.label} gutter={12} align="middle">
            <Col span={10}>
              <Typography.Text theme="secondary">{item.label}</Typography.Text>
            </Col>
            <Col span={14}>
              <Typography.Text>{item.value || '—'}</Typography.Text>
            </Col>
          </Row>
        ))}
      </Space>
    </Card>
  );
}

export function SystemConfigPanel({ systemConfig }: { systemConfig: SystemConfig }) {
  const todoCount = systemConfig.todo_items.length;
  const cozeMissingToken = Boolean(systemConfig.coze && !systemConfig.coze.token_present);
  const configSummary = cozeMissingToken
    ? 'Coze 调用凭证未配置，涉及 Coze 工具箱或工作流调用前必须先补齐。'
    : todoCount > 0
      ? `当前系统配置仍有 ${todoCount} 个待办，先处理高优先级项再发版。`
      : '当前配置快照没有明显待办，可以作为发版前环境核对依据。';

  return (
    <>
      <ActionBar>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <Space direction="vertical" size={4}>
            <Typography.Text strong>运行环境快照</Typography.Text>
            <Typography.Text theme="secondary">本页只展示当前配置快照，变更请在对应模块操作后再回到这里核对。</Typography.Text>
          </Space>
          <Space size="small" style={{ flexWrap: 'wrap' }}>
            <Tag variant="light">数据库：{systemConfig.database.driver || 'default'}</Tag>
            <Tag variant="light" theme="primary">
              存储桶：{systemConfig.oss.bucket}
            </Tag>
            <Tag variant="light" theme={systemConfig.coze?.token_present ? 'success' : 'warning'}>
              Coze 调用凭证 {systemConfig.coze?.token_present ? '已配置' : '未配置'}
            </Tag>
          </Space>
        </Space>
      </ActionBar>

      <OperationFlowCard
        title="环境核对闭环"
        description="本页不直接改配置，只用于发版前确认数据库、OSS、安全参数和 Coze 集成是否符合预期。"
        summary={configSummary}
        summaryTheme={cozeMissingToken || todoCount > 0 ? 'warning' : 'success'}
        steps={[
          {
            key: 'database',
            title: '核对数据库',
            detail: '确认当前连接的数据库类型、主机和连接串，不要把测试库当生产库。',
            action: '发现库不对时先停发版，回到服务器环境变量修正。',
            done: '库正确',
          },
          {
            key: 'oss',
            title: '核对素材存储',
            detail: '确认 OSS bucket、endpoint、对外域名和根目录前缀，避免结果回填到错误位置。',
            action: '内外网地址切换前先确认对外返回仍是公网稳定地址。',
            done: '回填稳定',
          },
          {
            key: 'security',
            title: '核对安全参数',
            detail: '登录、刷新和上传凭证有效期会影响管理端和测评端体验。',
            action: '凭证过短或过长时按安全策略调整后再上线。',
            done: '凭证可控',
          },
          {
            key: 'coze',
            title: '核对 Coze 集成',
            detail: 'Coze 工作台地址、工作流地址和调用凭证决定工具箱链路是否可用。',
            action: '凭证缺失或地址异常时先修 Coze 集成，再跑工具箱 smoke。',
            done: cozeMissingToken ? '待补凭证' : '工具箱可测',
            theme: cozeMissingToken ? 'warning' : 'primary',
          },
        ]}
      />

      <div className={`grid gap-6 ${systemConfig.coze ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
        <InfoCard
          title="数据库"
          items={[
            { label: '服务类型', value: systemConfig.database.backend },
            { label: '驱动', value: systemConfig.database.driver || 'default' },
            { label: '主机', value: systemConfig.database.host || 'local' },
            { label: '连接串', value: systemConfig.database.dsn },
          ]}
        />
        <InfoCard
          title="素材存储/上传"
          items={[
            { label: '存储桶', value: systemConfig.oss.bucket },
            { label: '访问节点', value: systemConfig.oss.endpoint },
            { label: '对外域名', value: systemConfig.oss.public_domain || '未配置' },
            { label: '根目录前缀', value: systemConfig.oss.root_prefix },
          ]}
        />
        <InfoCard
          title="安全参数"
          items={[
            { label: '登录有效期', value: `${systemConfig.security.jwt_access_ttl}s` },
            { label: '刷新有效期', value: `${systemConfig.security.jwt_refresh_ttl}s` },
            { label: '上传凭证有效期', value: `${systemConfig.security.upload_token_ttl}s` },
          ]}
        />
        {systemConfig.coze && (
          <InfoCard
            title="Coze 集成"
            items={[
              { label: '工作台地址', value: systemConfig.coze.base_url || '未配置' },
              { label: '工作流地址', value: systemConfig.coze.loop_base_url || '未配置' },
              { label: '调用凭证', value: systemConfig.coze.token_present ? systemConfig.coze.token_hint || '已配置' : '未配置' },
            ]}
          />
        )}
      </div>

      <Card bordered title="特性开关">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(systemConfig.feature_flags).map(([key, enabled]) => (
            <div key={key} className="podi-overview-stat-item">
              <div className="podi-overview-stat-item__label">{key}</div>
              <div className="podi-overview-stat-item__value" style={{ fontSize: 18 }}>
                {enabled ? '启用' : '关闭'}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card bordered title="待办事项">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {systemConfig.todo_items.length === 0 ? (
            <Typography.Text theme="secondary">当前无待办。</Typography.Text>
          ) : (
            systemConfig.todo_items.map((todo) => (
              <div key={todo.title} className="podi-empty-state">
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>{todo.title}</Typography.Text>
                  <Tag variant="light" theme={todo.severity === 'high' ? 'danger' : todo.severity === 'medium' ? 'warning' : 'default'}>
                    {todo.severity}
                  </Tag>
                </Space>
                <Typography.Text theme="secondary">{todo.description}</Typography.Text>
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  状态：{todo.status}
                </Typography.Text>
              </div>
            ))
          )}
        </Space>
      </Card>
    </>
  );
}
