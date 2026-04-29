import { Card, Col, Row, Space, Tag, Typography } from 'tdesign-react';
import type { SystemConfig } from '../../../types/admin';
import { ActionBar } from '../shared/ui';

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
