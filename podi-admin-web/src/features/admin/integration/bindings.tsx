import { Alert, Button, Card, Col, Input, InputNumber, Row, Space, Switch, Table, Typography } from 'tdesign-react';
import type { Binding, BindingFormState } from '../../../types/admin';
import { OperationFlowCard, StatusBadge } from '../shared/ui';

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
  const enabledCount = bindings.filter((item) => item.enabled).length;
  const disabledCount = Math.max(0, bindings.length - enabledCount);
  const bindingSummary =
    bindings.length === 0
      ? '当前没有路由策略；业务入口需要先绑定模板和运行线路，才能稳定调度。'
      : disabledCount > 0
        ? `当前共有 ${bindings.length} 条策略，其中 ${disabledCount} 条已停用；发版前确认停用是否符合预期。`
        : `当前 ${enabledCount} 条路由策略均已启用，继续核对优先级和真实命中证据。`;

  return (
    <>
      <OperationFlowCard
        title="路由策略闭环"
        description="把业务入口、工作流模板和运行线路连起来；这里改错会直接影响任务分发。"
        summary={bindingSummary}
        summaryTheme={bindings.length === 0 || disabledCount > 0 ? 'warning' : 'success'}
        steps={[
          {
            key: 'action',
            title: '确认业务入口',
            detail: '业务入口必须能对应真实功能，例如花纹提取、图裂变、扩图或内部动作。',
            action: '入口名称不清楚时先回到业务能力或能力目录确认。',
            done: '入口明确',
          },
          {
            key: 'workflow',
            title: '绑定工作流模板',
            detail: '模板决定实际执行流程版本，不能把测试模板误绑到生产入口。',
            action: '模板变更后先跑能力测试，再放到业务默认版本。',
            done: '模板正确',
          },
          {
            key: 'executor',
            title: '绑定运行线路',
            detail: '运行线路决定任务去哪个服务器或第三方 API，必须可用且标签匹配。',
            action: '线路异常时先修执行节点，不要只调高优先级。',
            done: '线路可用',
          },
          {
            key: 'priority',
            title: '核对优先级和启停',
            detail: '优先级越大越先尝试；停用策略不会参与分发。',
            action: '发版前确认主线路、备用线路和停用策略都符合预期。',
            done: '分发可控',
            theme: disabledCount > 0 ? 'warning' : 'primary',
          },
        ]}
      />

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
