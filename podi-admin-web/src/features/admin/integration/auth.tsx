import { Alert, Button, Card, Col, Input, InputNumber, Row, Select, Space, Table, Tag, Textarea, Typography } from 'tdesign-react';

import type {
  AuthScopeSummaryResponse,
  AuthSession,
  AuthUser,
  AuthUserFormState,
  InviteCode,
  InviteCodeCreatePayload,
} from '../../../types/admin';
import { OperationFlowCard, StatusBadge } from '../shared/ui';

export const AuthPanel = ({
  users,
  sessions,
  inviteCodes,
  scopeSummary,
  userForm,
  inviteForm,
  loading,
  error,
  onRefresh,
  onUserFormChange,
  onUserEditSelect,
  onUserSubmit,
  onInviteFormChange,
  onInviteSubmit,
  onInviteDisable,
  onSessionRevoke,
  formatDateTime,
}: {
  users: AuthUser[];
  sessions: AuthSession[];
  inviteCodes: InviteCode[];
  scopeSummary?: AuthScopeSummaryResponse | null;
  userForm: AuthUserFormState;
  inviteForm: InviteCodeCreatePayload;
  loading: boolean;
  error?: string | null;
  onRefresh: () => void;
  onUserFormChange: (next: AuthUserFormState) => void;
  onUserEditSelect: (user: AuthUser) => void;
  onUserSubmit: () => void;
  onInviteFormChange: (next: InviteCodeCreatePayload) => void;
  onInviteSubmit: () => void;
  onInviteDisable: (invite: InviteCode) => void;
  onSessionRevoke: (session: AuthSession) => void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Alert
      theme="info"
      message="第一阶段闭环：管理员生成或失效邀请码，用户用邀请码注册，登录会话可追踪并可踢出。角色暂时仍使用用户表里的 role 字段。"
    />
    <OperationFlowCard
      title="账号权限闭环"
      description="先确认能否上线，再处理业务方范围、邀请码和异常会话。"
      summary={
        scopeSummary
          ? scopeSummary.releaseReady
            ? '当前账号权限满足上线检查，继续保持业务方范围、邀请码和会话可追踪。'
            : `账号权限仍有 ${scopeSummary.blockingRiskCount || 0} 个阻塞、${scopeSummary.warningRiskCount || 0} 个提醒，先处理阻塞项再上线。`
          : '后端暂未返回账号权限检查，先刷新数据；仍为空时检查认证接口和数据库。'
      }
      summaryTheme={scopeSummary?.releaseReady ? 'success' : 'warning'}
      steps={[
        {
          key: 'release-check',
          title: '看上线检查',
          detail: '先看管理员、业务方范围、邀请码和会话追踪是否通过，不先改账号明细。',
          action: '有阻塞时先处理“当前先处理什么”里的风险项。',
          done: '门禁通过',
        },
        {
          key: 'client-scope',
          title: '绑定业务方范围',
          detail: '业务方账号必须明确 tenantId 和 clientId，避免越权调用其他业务。',
          action: '对未绑定业务方的业务账号补范围或停用。',
          done: '范围清楚',
        },
        {
          key: 'invite',
          title: '发放邀请码',
          detail: '只给明确用途和有效期的邀请码，过期或误发的邀请码要及时失效。',
          action: '生成前写清备注，生成后检查可用次数和过期时间。',
          done: '入口受控',
        },
        {
          key: 'sessions',
          title: '清理异常会话',
          detail: '账号停用、权限变化或异常登录后，需要踢出旧会话并保留审计记录。',
          action: '处理离职、临时提权、异常登录账号的会话。',
          done: '可追溯',
        },
      ]}
    />
    {error ? <Alert theme="error" message={error} /> : null}
    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
      <Space breakLine>
        <Tag variant="light">用户 {users.length}</Tag>
        <Tag variant="light">登录会话 {sessions.length}</Tag>
        <Tag variant="light">邀请码 {inviteCodes.length}</Tag>
        <Tag theme="warning" variant="light">多角色表未启用</Tag>
      </Space>
      <Button variant="outline" loading={loading} onClick={onRefresh}>
        刷新
      </Button>
    </Space>
    {scopeSummary ? (
      <Card bordered title="当前先处理什么">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Alert
            theme={scopeSummary.releaseReady ? 'success' : 'warning'}
            message={
              scopeSummary.releaseReady
                ? '账号权限当前满足上线检查：管理员、业务方范围、邀请码和会话追踪都没有明显阻塞。'
                : `账号权限仍需处理：阻塞 ${scopeSummary.blockingRiskCount || 0} 项，提醒 ${scopeSummary.warningRiskCount || 0} 项。`
            }
          />
          <Row gutter={[12, 12]}>
            {(scopeSummary.risks || []).slice(0, 4).map((risk) => (
              <Col key={risk.key} xs={12} lg={(scopeSummary.risks || []).length === 1 ? 12 : 4}>
                <div
                  style={{
                    border: '1px solid var(--td-border-level-1-color)',
                    borderRadius: 12,
                    padding: 12,
                    height: '100%',
                  }}
                >
                  <Space direction="vertical" size={4}>
                    <Tag
                      theme={
                        risk.severity === 'danger'
                          ? 'danger'
                          : risk.severity === 'warning'
                            ? 'warning'
                            : risk.severity === 'success'
                              ? 'success'
                              : 'default'
                      }
                      variant="light"
                    >
                      {risk.title}
                    </Tag>
                    <Typography.Text theme="secondary">{risk.detail}</Typography.Text>
                    {risk.count > 0 ? <Typography.Text theme="secondary">数量：{risk.count}</Typography.Text> : null}
                  </Space>
                </div>
              </Col>
            ))}
          </Row>
          <Table
            size="small"
            rowKey="key"
            data={scopeSummary.checklist || []}
            columns={[
              {
                colKey: 'title',
                title: '上线检查项',
                minWidth: 180,
                cell: ({ row }) => (
                  <Space size={6}>
                    <Tag theme={row.passed ? 'success' : 'warning'} variant="light">
                      {row.passed ? '已通过' : '需处理'}
                    </Tag>
                    <Typography.Text strong>{row.title}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'detail',
                title: '检查口径',
                minWidth: 260,
                cell: ({ row }) => <Typography.Text theme="secondary">{row.detail}</Typography.Text>,
              },
              {
                colKey: 'action',
                title: '没通过时怎么做',
                minWidth: 260,
                cell: ({ row }) => <Typography.Text theme={row.passed ? 'secondary' : 'warning'}>{row.action}</Typography.Text>,
              },
            ]}
            empty={<Typography.Text theme="secondary">暂无上线检查项。</Typography.Text>}
          />
          <Card bordered title="业务 API 权限边界">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text theme="secondary">
                这里确认业务方账号调用业务接口时的隔离规则。业务人员只需要看是否全部“已生效”。
              </Typography.Text>
              <Table
                size="small"
                rowKey="key"
                data={scopeSummary.businessApiPolicy || []}
                columns={[
                  {
                    colKey: 'title',
                    title: '规则',
                    minWidth: 220,
                    cell: ({ row }) => (
                      <Space size={6}>
                        <Tag theme={row.enforced ? 'success' : 'warning'} variant="light">
                          {row.enforced ? '已生效' : '未生效'}
                        </Tag>
                        <Typography.Text strong>{row.title}</Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'detail',
                    title: '实际效果',
                    minWidth: 360,
                    cell: ({ row }) => <Typography.Text theme="secondary">{row.detail}</Typography.Text>,
                  },
                ]}
                empty={<Typography.Text theme="secondary">当前后端未返回业务 API 权限边界，请先更新后端。</Typography.Text>}
              />
            </Space>
          </Card>
          <Card bordered title="角色边界">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text theme="secondary">
                这里说明每类调用方能做什么、不能做什么。发版前需要确认全部“已生效”。
              </Typography.Text>
              <Table
                size="small"
                rowKey="key"
                data={scopeSummary.roleBoundary || []}
                columns={[
                  {
                    colKey: 'title',
                    title: '调用方',
                    minWidth: 180,
                    cell: ({ row }) => (
                      <Space size={6}>
                        <Tag theme={row.enforced ? 'success' : 'warning'} variant="light">
                          {row.enforced ? '已生效' : '未生效'}
                        </Tag>
                        <Typography.Text strong>{row.title}</Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'principal',
                    title: '适用对象',
                    minWidth: 180,
                    cell: ({ row }) => <Typography.Text theme="secondary">{row.principal}</Typography.Text>,
                  },
                  {
                    colKey: 'allowed',
                    title: '允许',
                    minWidth: 300,
                    cell: ({ row }) => <Typography.Text theme="secondary">{row.allowed}</Typography.Text>,
                  },
                  {
                    colKey: 'blocked',
                    title: '不允许',
                    minWidth: 300,
                    cell: ({ row }) => <Typography.Text theme={row.enforced ? 'secondary' : 'warning'}>{row.blocked}</Typography.Text>,
                  },
                ]}
                empty={<Typography.Text theme="secondary">当前后端未返回角色边界，请先更新后端。</Typography.Text>}
              />
            </Space>
          </Card>
        </Space>
      </Card>
    ) : null}
    {scopeSummary ? (
      <Row gutter={[16, 16]}>
        <Col xs={12} lg={5}>
          <Card bordered title="角色分布">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space breakLine>
                <Tag variant="light">用户 {scopeSummary.totals.users}</Tag>
                <Tag variant="light">活跃 {scopeSummary.totals.activeUsers}</Tag>
                <Tag theme={scopeSummary.totals.unscopedClientUsers > 0 ? 'warning' : 'success'} variant="light">
                  业务方未绑定 {scopeSummary.totals.unscopedClientUsers}
                </Tag>
                <Tag variant="light">活跃会话 {scopeSummary.totals.activeSessions}</Tag>
              </Space>
              <Table
                size="small"
                rowKey="role"
                data={scopeSummary.roles || []}
                columns={[
                  { colKey: 'role', title: '角色', cell: ({ row }) => <Tag variant="light">{row.role}</Tag> },
                  { colKey: 'count', title: '用户数', width: 90 },
                  { colKey: 'activeCount', title: '活跃', width: 90 },
                ]}
                empty={<Typography.Text theme="secondary">暂无角色数据。</Typography.Text>}
              />
            </Space>
          </Card>
        </Col>
        <Col xs={12} lg={7}>
          <Card bordered title="业务方范围">
            <Table
              size="small"
              rowKey="scope"
              data={(scopeSummary.tenants || []).map((item, index) => ({
                ...item,
                scope: `${item.tenantId || 'unscoped'}:${item.clientId || 'all'}:${index}`,
              }))}
              columns={[
                {
                  colKey: 'scope',
                  title: '业务方 / 客户端',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.tenantId || '未绑定业务方'}</Typography.Text>
                      <Typography.Text theme="secondary">{row.clientId || '全部客户端'}</Typography.Text>
                    </Space>
                  ),
                },
                { colKey: 'userCount', title: '用户', width: 90 },
                { colKey: 'clientUserCount', title: '业务方账号', width: 120 },
                { colKey: 'activeSessionCount', title: '会话', width: 90 },
              ]}
              empty={<Typography.Text theme="secondary">暂无业务方范围数据。</Typography.Text>}
            />
          </Card>
        </Col>
      </Row>
    ) : null}
    <Card bordered title="调整用户权限">
      <Row gutter={[12, 12]}>
        <Col xs={12} lg={3}>
          <Typography.Text theme="secondary">选择用户</Typography.Text>
          <Select
            value={userForm.userId || ''}
            placeholder="先选择要调整的账号"
            filterable
            options={users.map((user) => ({
              label: `${user.displayName || user.username} · ${user.email}`,
              value: user.id,
            }))}
            onChange={(value) => {
              const selected = users.find((item) => item.id === value);
              if (selected) onUserEditSelect(selected);
            }}
          />
        </Col>
        <Col xs={12} lg={2}>
          <Typography.Text theme="secondary">角色</Typography.Text>
          <Select
            value={userForm.role || 'user'}
            options={[
              { label: '管理员', value: 'admin' },
              { label: '内部用户', value: 'user' },
              { label: '业务方', value: 'client' },
            ]}
            onChange={(value) => onUserFormChange({ ...userForm, role: String(value || 'user') })}
          />
        </Col>
        <Col xs={12} lg={2}>
          <Typography.Text theme="secondary">状态</Typography.Text>
          <Select
            value={userForm.status || 'active'}
            options={[
              { label: '可登录', value: 'active' },
              { label: '已停用', value: 'inactive' },
            ]}
            onChange={(value) => onUserFormChange({ ...userForm, status: String(value || 'active') })}
          />
        </Col>
        <Col xs={12} lg={2}>
          <Typography.Text theme="secondary">业务方标识</Typography.Text>
          <Input
            value={userForm.tenantId || ''}
            placeholder="留空表示未绑定"
            onChange={(value) => onUserFormChange({ ...userForm, tenantId: String(value || '') })}
          />
        </Col>
        <Col xs={12} lg={2}>
          <Typography.Text theme="secondary">客户端标识</Typography.Text>
          <Input
            value={userForm.clientId || ''}
            placeholder="留空表示全部客户端"
            onChange={(value) => onUserFormChange({ ...userForm, clientId: String(value || '') })}
          />
        </Col>
        <Col xs={12} lg={1}>
          <Typography.Text theme="secondary">操作</Typography.Text>
          <Button block theme="primary" loading={loading} disabled={!userForm.userId} onClick={onUserSubmit}>
            保存
          </Button>
        </Col>
        <Col xs={12} lg={3}>
          <Typography.Text theme="secondary">显示名称</Typography.Text>
          <Input
            value={userForm.displayName || ''}
            placeholder="可选"
            onChange={(value) => onUserFormChange({ ...userForm, displayName: String(value || '') })}
          />
        </Col>
        <Col xs={12} lg={9}>
          <Typography.Text theme="secondary">调整说明</Typography.Text>
          <Input
            value={userForm.note || ''}
            placeholder="例如：绑定业务方范围、暂停离职账号、临时提升权限"
            onChange={(value) => onUserFormChange({ ...userForm, note: String(value || '') })}
          />
        </Col>
      </Row>
      <Typography.Text theme="secondary">
        说明：停用账号会同时踢出该账号已有登录会话；系统会阻止管理员把自己停用或降权。
      </Typography.Text>
      {(users.find((item) => item.id === userForm.userId)?.adminAudit || []).length > 0 ? (
        <Table
          size="small"
          rowKey="id"
          data={(users.find((item) => item.id === userForm.userId)?.adminAudit || []).slice(0, 5).map((item, index) => ({
            ...item,
            id: `${item.createdAt || 'audit'}-${index}`,
          }))}
          columns={[
            {
              colKey: 'createdAt',
              title: '调整时间',
              minWidth: 150,
              cell: ({ row }) => formatDateTime(row.createdAt || ''),
            },
            {
              colKey: 'actorUsername',
              title: '操作人',
              width: 120,
              cell: ({ row }) => row.actorUsername || '系统',
            },
            {
              colKey: 'changedFields',
              title: '调整内容',
              minWidth: 180,
              cell: ({ row }) => (row.changedFields || []).join('、') || '仅记录说明',
            },
            {
              colKey: 'note',
              title: '说明',
              minWidth: 220,
              cell: ({ row }) => row.note || '—',
            },
          ]}
        />
      ) : null}
    </Card>
    <Row gutter={[16, 16]}>
      <Col xs={12} lg={4}>
        <Card bordered title="生成邀请码">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text theme="secondary">角色</Typography.Text>
            <Select
              value={inviteForm.role || 'user'}
              options={[
                { label: '管理员', value: 'admin' },
                { label: '内部用户', value: 'user' },
                { label: '业务方', value: 'client' },
              ]}
              onChange={(value) => onInviteFormChange({ ...inviteForm, role: String(value || 'user') })}
            />
            <Typography.Text theme="secondary">业务方标识</Typography.Text>
            <Input
              value={inviteForm.tenantId || ''}
              placeholder="例如 tenant-a，可留空"
              onChange={(value) => onInviteFormChange({ ...inviteForm, tenantId: String(value || '') })}
            />
            <Typography.Text theme="secondary">客户端标识</Typography.Text>
            <Input
              value={inviteForm.clientId || ''}
              placeholder="例如 web-client，可留空"
              onChange={(value) => onInviteFormChange({ ...inviteForm, clientId: String(value || '') })}
            />
            <Typography.Text theme="secondary">可用次数</Typography.Text>
            <InputNumber
              min={1}
              max={100}
              value={inviteForm.maxUses || 1}
              onChange={(value) => onInviteFormChange({ ...inviteForm, maxUses: Number(value || 1) })}
            />
            <Typography.Text theme="secondary">过期时间</Typography.Text>
            <Input
              value={inviteForm.expiresAt || ''}
              placeholder="例如 2026-05-25T00:00:00，可留空"
              onChange={(value) => onInviteFormChange({ ...inviteForm, expiresAt: String(value || '') })}
            />
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Textarea
              autosize={{ minRows: 2, maxRows: 4 }}
              value={inviteForm.note || ''}
              placeholder="说明这个邀请码给谁用"
              onChange={(value) => onInviteFormChange({ ...inviteForm, note: String(value || '') })}
            />
            <Button theme="primary" loading={loading} onClick={onInviteSubmit}>
              生成邀请码
            </Button>
          </Space>
        </Card>
      </Col>
      <Col xs={12} lg={8}>
        <Card bordered title="邀请码">
          <Table
            size="small"
            rowKey="id"
            data={inviteCodes}
            loading={loading}
            empty={<Typography.Text theme="secondary">暂无邀请码。</Typography.Text>}
            columns={[
              {
                colKey: 'code',
                title: '邀请码',
                minWidth: 120,
                cell: ({ row }) => <Typography.Text code>{row.code}</Typography.Text>,
              },
              {
                colKey: 'scope',
                title: '归属',
                minWidth: 180,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.tenantId || '未绑定业务方'}</Typography.Text>
                    <Typography.Text theme="secondary">{row.clientId || '未绑定客户端'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'role',
                title: '角色',
                width: 110,
                cell: ({ row }) => <Tag variant="light">{row.role}</Tag>,
              },
              {
                colKey: 'usage',
                title: '使用',
                width: 120,
                cell: ({ row }) => `${row.usedCount || 0}/${row.maxUses || 1}`,
              },
              {
                colKey: 'status',
                title: '状态',
                width: 120,
                cell: ({ row }) => <StatusBadge status={row.status} />,
              },
              {
                colKey: 'expiresAt',
                title: '过期时间',
                minWidth: 150,
                cell: ({ row }) => formatDateTime(row.expiresAt || ''),
              },
              {
                colKey: 'action',
                title: '操作',
                width: 100,
                cell: ({ row }) =>
                  row.status === 'active' ? (
                    <Button size="small" theme="danger" variant="text" onClick={() => onInviteDisable(row)}>
                      失效
                    </Button>
                  ) : (
                    <Typography.Text theme="secondary">—</Typography.Text>
                  ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
    <Row gutter={[16, 16]}>
      <Col xs={12} lg={7}>
        <Card bordered title="用户">
          <Table
            size="small"
            rowKey="id"
            data={users}
            loading={loading}
            empty={<Typography.Text theme="secondary">暂无用户。</Typography.Text>}
            columns={[
              {
                colKey: 'user',
                title: '用户',
                minWidth: 220,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.displayName || row.username}</Typography.Text>
                    <Typography.Text theme="secondary">{row.email}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'role',
                title: '角色',
                width: 110,
                cell: ({ row }) => <Tag variant="light">{row.role}</Tag>,
              },
              {
                colKey: 'scope',
                title: '业务归属',
                minWidth: 180,
                cell: ({ row }) => (
                  <Typography.Text theme="secondary">
                    {row.tenantId || '—'} · {row.clientId || '—'}
                  </Typography.Text>
                ),
              },
              {
                colKey: 'status',
                title: '状态',
                width: 110,
                cell: ({ row }) => <StatusBadge status={row.status} />,
              },
              {
                colKey: 'lastLoginAt',
                title: '最近登录',
                minWidth: 150,
                cell: ({ row }) => formatDateTime(row.lastLoginAt || ''),
              },
              {
                colKey: 'action',
                title: '操作',
                width: 90,
                cell: ({ row }) => (
                  <Button size="small" variant="text" onClick={() => onUserEditSelect(row)}>
                    调整
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={12} lg={5}>
        <Card bordered title="登录会话">
          <Table
            size="small"
            rowKey="id"
            data={sessions}
            loading={loading}
            empty={<Typography.Text theme="secondary">暂无会话。</Typography.Text>}
            columns={[
              {
                colKey: 'user',
                title: '用户',
                minWidth: 170,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.displayName || row.username || '未知用户'}</Typography.Text>
                    <Typography.Text theme="secondary">{row.email || row.userId || '—'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'status',
                title: '状态',
                width: 100,
                cell: ({ row }) => <StatusBadge status={row.status} />,
              },
              {
                colKey: 'ipAddress',
                title: 'IP',
                minWidth: 130,
                cell: ({ row }) => row.ipAddress || '—',
              },
              {
                colKey: 'expiresAt',
                title: '过期时间',
                minWidth: 150,
                cell: ({ row }) => formatDateTime(row.expiresAt || ''),
              },
              {
                colKey: 'action',
                title: '操作',
                width: 100,
                cell: ({ row }) =>
                  row.status === 'active' ? (
                    <Button size="small" theme="danger" variant="text" onClick={() => onSessionRevoke(row)}>
                      踢出
                    </Button>
                  ) : (
                    <Typography.Text theme="secondary">—</Typography.Text>
                  ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
  </Space>
);
