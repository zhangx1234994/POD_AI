import { Alert, Button, Card, Col, Input, InputNumber, Row, Space, Switch, Table, Typography } from 'tdesign-react';
import type { Binding, BindingFormState } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

type BindingRoutesPanelProps = {
  bindings: Binding[];
  bindingForm: BindingFormState;
  onFormChange: (next: BindingFormState) => void;
  onSubmit: () => void;
  onDelete: (id: string) => void;
  onReset: () => void;
};

export function BindingRoutesPanel({
  bindings,
  bindingForm,
  onFormChange,
  onSubmit,
  onDelete,
  onReset,
}: BindingRoutesPanelProps) {
  return (
    <>
      <div style={{ margin: '0 0 12px' }}>
        <Typography.Text theme="secondary">
          例如：花纹提取可以优先走云端 ComfyUI 线路；如果排队或失败，再切到备用线路。百度、火山等第三方能力也可以用多条线路做额度切换。
        </Typography.Text>
      </div>

      <Card bordered style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={4}>
            <Alert theme="info" message="业务入口：告诉系统这是花纹提取、图裂变、扩图，还是某个内部动作。" />
          </Col>
          <Col xs={12} md={4}>
            <Alert theme="info" message="工作流模板：决定实际执行的流程版本，例如旧版裂变、新版裂变或扩图主线。" />
          </Col>
          <Col xs={12} md={4}>
            <Alert theme="info" message="运行线路：决定任务发到哪台服务器或哪个第三方 API，优先级越大越先尝试。" />
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={8}>
          <Card title="策略列表" bordered>
            <Table
              rowKey="id"
              data={bindings as any}
              columns={
                [
                  { colKey: 'action', title: '业务入口', width: 220 },
                  { colKey: 'workflow_id', title: '工作流模板 ID', width: 220 },
                  { colKey: 'executor_id', title: '运行线路 ID', width: 220 },
                  { colKey: 'priority', title: '优先级', width: 100 },
                  {
                    colKey: 'enabled',
                    title: '启用',
                    width: 90,
                    cell: ({ row }: any) => <StatusPill status={row.enabled ? 'ON' : 'OFF'} />,
                  },
                  {
                    colKey: 'op',
                    title: '操作',
                    width: 140,
                    fixed: 'right',
                    cell: ({ row }: any) => (
                      <Space>
                        <Button size="small" variant="text" onClick={() => onFormChange(row)}>
                          编辑
                        </Button>
                        <Button size="small" variant="text" theme="danger" onClick={() => onDelete(row.id)}>
                          删除
                        </Button>
                      </Space>
                    ),
                  },
                ] as any
              }
            />
          </Card>
        </Col>

        <Col xs={12} lg={4}>
          <Card title={bindingForm.id ? '编辑策略' : '新增策略'} bordered>
            <Space direction="vertical" size="medium" style={{ width: '100%' }}>
              <Input
                placeholder="业务入口，例如 pattern.extract"
                value={bindingForm.action || ''}
                onChange={(value) => onFormChange({ ...bindingForm, action: String(value) })}
              />
              <Input
                placeholder="工作流模板 ID"
                value={bindingForm.workflow_id || ''}
                onChange={(value) => onFormChange({ ...bindingForm, workflow_id: String(value) })}
              />
              <Input
                placeholder="运行线路 ID"
                value={bindingForm.executor_id || ''}
                onChange={(value) => onFormChange({ ...bindingForm, executor_id: String(value) })}
              />
              <InputNumber
                placeholder="优先级"
                value={bindingForm.priority ?? 0}
                onChange={(value) => onFormChange({ ...bindingForm, priority: Number(value || 0) })}
              />
              <div>
                <Space align="center">
                  <Switch
                    value={Boolean(bindingForm.enabled ?? true)}
                    onChange={(value) => onFormChange({ ...bindingForm, enabled: Boolean(value) })}
                  />
                  <Typography.Text>启用</Typography.Text>
                </Space>
              </div>
              <Space>
                <Button theme="primary" onClick={onSubmit} style={{ width: 120 }}>
                  保存
                </Button>
                {bindingForm.id ? (
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
