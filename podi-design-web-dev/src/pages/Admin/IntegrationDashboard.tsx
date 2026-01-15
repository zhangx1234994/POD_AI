import { useEffect, useMemo, useState } from 'react';
import { adminIntegrationAPI } from '@/services/adminIntegrationAPI';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';

type Executor = {
  id: string;
  name: string;
  type: string;
  base_url?: string;
  status: string;
  weight: number;
  max_concurrency: number;
  health_status?: string;
  last_heartbeat_at?: string;
  config?: Record<string, any>;
};

type Workflow = {
  id: string;
  action: string;
  name: string;
  version?: string;
  type?: string;
  status?: string;
  definition?: Record<string, any>;
  metadata?: Record<string, any>;
  updated_at?: string;
};

type Binding = {
  id: string;
  action: string;
  workflow_id: string;
  executor_id: string;
  priority: number;
  enabled: boolean;
  metadata?: Record<string, any>;
};

type ApiKey = {
  id: string;
  provider: string;
  name: string;
  status: string;
  daily_quota?: number;
  usage_count?: number;
  expire_at?: string;
};

const emptyExecutor: Partial<Executor> = {
  name: '',
  type: '',
  status: 'inactive',
  weight: 1,
  max_concurrency: 1,
};

const emptyWorkflow: Partial<Workflow> = {
  action: '',
  name: '',
  version: 'v1',
  type: 'generic',
  status: 'inactive',
};

const emptyBinding: Partial<Binding> = {
  action: '',
  workflow_id: '',
  executor_id: '',
  priority: 0,
  enabled: true,
};

const emptyApiKey: Partial<ApiKey> = {
  provider: '',
  name: '',
  status: 'active',
};

function formatDate(input?: string) {
  if (!input) return '—';
  try {
    return new Date(input).toLocaleString();
  } catch {
    return input;
  }
}

function tryParseJSON(value?: string | Record<string, any>) {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

function toJSONString(value?: string | Record<string, any>) {
  if (!value) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

export function IntegrationDashboard() {
  const [executors, setExecutors] = useState<Executor[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(false);

  const [executorForm, setExecutorForm] = useState<Partial<Executor>>(emptyExecutor);
  const [workflowForm, setWorkflowForm] = useState<Partial<Workflow>>(emptyWorkflow);
  const [bindingForm, setBindingForm] = useState<Partial<Binding>>(emptyBinding);
  const [apiKeyForm, setApiKeyForm] = useState<Partial<ApiKey>>(emptyApiKey);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [execRes, wfRes, bindingRes, apiKeyRes] = await Promise.all([
        adminIntegrationAPI.listExecutors(),
        adminIntegrationAPI.listWorkflows(),
        adminIntegrationAPI.listBindings(),
        adminIntegrationAPI.listApiKeys(),
      ]);
      setExecutors(execRes);
      setWorkflows(wfRes);
      setBindings(bindingRes);
      setApiKeys(apiKeyRes);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const summary = useMemo(() => {
    const activeExecutors = executors.filter((ex) => ex.status === 'active').length;
    const expiringKeys = apiKeys.filter((key) => key.expire_at && new Date(key.expire_at).getTime() - Date.now() < 7 * 24 * 3600 * 1000).length;
    return {
      executorCount: executors.length,
      activeExecutors,
      workflowCount: workflows.length,
      bindingCount: bindings.length,
      apiKeyCount: apiKeys.length,
      expiringKeys,
    };
  }, [executors, workflows, bindings, apiKeys]);

  const handleExecutorSubmit = async () => {
    if (!executorForm.name || !executorForm.type) return;
    const payload = {
      ...executorForm,
      config: tryParseJSON(executorForm.config as any),
    };
    if (executorForm.id) {
      await adminIntegrationAPI.updateExecutor(executorForm.id, payload);
    } else {
      await adminIntegrationAPI.createExecutor(payload);
    }
    setExecutorForm(emptyExecutor);
    loadAll();
  };

  const handleWorkflowSubmit = async () => {
    if (!workflowForm.name || !workflowForm.action) return;
    const payload = {
      ...workflowForm,
      definition: tryParseJSON(workflowForm.definition as any),
      metadata: tryParseJSON(workflowForm.metadata as any),
    };
    if (workflowForm.id) {
      await adminIntegrationAPI.updateWorkflow(workflowForm.id, payload);
    } else {
      await adminIntegrationAPI.createWorkflow(payload);
    }
    setWorkflowForm(emptyWorkflow);
    loadAll();
  };

  const handleBindingSubmit = async () => {
    if (!bindingForm.action || !bindingForm.workflow_id || !bindingForm.executor_id) return;
    const payload = { ...bindingForm, metadata: tryParseJSON(bindingForm.metadata as any) };
    if (bindingForm.id) {
      await adminIntegrationAPI.updateBinding(bindingForm.id, payload);
    } else {
      await adminIntegrationAPI.createBinding(payload);
    }
    setBindingForm(emptyBinding);
    loadAll();
  };

  const handleApiKeySubmit = async () => {
    if (!apiKeyForm.provider || !apiKeyForm.name || !apiKeyForm.status) return;
    if (apiKeyForm.id) {
      await adminIntegrationAPI.updateApiKey(apiKeyForm.id, apiKeyForm);
    } else if (apiKeyForm.key) {
      await adminIntegrationAPI.createApiKey(apiKeyForm);
    } else {
      return;
    }
    setApiKeyForm(emptyApiKey);
    loadAll();
  };

  const handleDelete = async (type: 'executor' | 'workflow' | 'binding' | 'apikey', id: string) => {
    const map = {
      executor: adminIntegrationAPI.deleteExecutor,
      workflow: adminIntegrationAPI.deleteWorkflow,
      binding: adminIntegrationAPI.deleteBinding,
      apikey: adminIntegrationAPI.deleteApiKey,
    };
    await map[type](id);
    loadAll();
  };

  const renderSummary = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard title="执行节点" value={summary.executorCount} description={`活跃 ${summary.activeExecutors}`} />
      <MetricCard title="工作流" value={summary.workflowCount} description="版本管理" />
      <MetricCard title="绑定策略" value={summary.bindingCount} description="action -> workflow -> executor" />
      <MetricCard title="API Keys" value={summary.apiKeyCount} description={`即将过期 ${summary.expiringKeys}`} />
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI 集成管理</h1>
          <p className="text-sm text-muted-foreground">查看执行节点、工作流与密钥使用情况，支持创建、编辑与下线。</p>
        </div>
        <Button variant="outline" onClick={loadAll} disabled={loading}>
          {loading ? '刷新中...' : '刷新数据'}
        </Button>
      </div>

      {renderSummary()}

      <Tabs defaultValue="executors">
        <TabsList className="mb-4">
          <TabsTrigger value="executors">执行节点</TabsTrigger>
          <TabsTrigger value="workflows">工作流</TabsTrigger>
          <TabsTrigger value="bindings">分配策略</TabsTrigger>
          <TabsTrigger value="apikeys">API Keys</TabsTrigger>
        </TabsList>

        <TabsContent value="executors" className="space-y-4">
          <SectionHeader title="执行节点" description="管理 ComfyUI/OpenAI/火山等执行端状态，确保任务可用。" />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>节点列表</CardTitle>
                <CardDescription>监控健康状态与并发控制，必要时快速下线。</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>名称</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>并发/权重</TableHead>
                      <TableHead>心跳</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {executors.map((ex) => (
                      <TableRow key={ex.id}>
                        <TableCell>
                          <div className="font-medium">{ex.name}</div>
                          <div className="text-xs text-muted-foreground truncate max-w-[220px]">{ex.base_url || '—'}</div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{ex.type}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={ex.status === 'active' ? 'bg-emerald-600' : 'bg-muted text-foreground'}>{ex.status}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">{ex.max_concurrency} / {ex.weight}</div>
                          {ex.health_status && <span className="text-xs text-muted-foreground">{ex.health_status}</span>}
                        </TableCell>
                        <TableCell className="text-xs">{formatDate(ex.last_heartbeat_at)}</TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button size="sm" variant="ghost" onClick={() => setExecutorForm({ ...ex, config: toJSONString(ex.config) as any })}>编辑</Button>
                          <Button size="sm" variant="ghost" onClick={() => handleDelete('executor', ex.id)}>删除</Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{executorForm.id ? '编辑节点' : '新增节点'}</CardTitle>
                <CardDescription>填写基础信息与配置 JSON（如 token、区域等）。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="名称" value={executorForm.name || ''} onChange={(e) => setExecutorForm({ ...executorForm, name: e.target.value })} />
                <Input placeholder="类型，例如 comfyui/openai" value={executorForm.type || ''} onChange={(e) => setExecutorForm({ ...executorForm, type: e.target.value })} />
                <Input placeholder="Base URL" value={executorForm.base_url || ''} onChange={(e) => setExecutorForm({ ...executorForm, base_url: e.target.value })} />
                <Input placeholder="状态" value={executorForm.status || ''} onChange={(e) => setExecutorForm({ ...executorForm, status: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    type="number"
                    placeholder="权重"
                    value={executorForm.weight ?? 1}
                    onChange={(e) => setExecutorForm({ ...executorForm, weight: Number(e.target.value) || 0 })}
                  />
                  <Input
                    type="number"
                    placeholder="最大并发"
                    value={executorForm.max_concurrency ?? 1}
                    onChange={(e) => setExecutorForm({ ...executorForm, max_concurrency: Number(e.target.value) || 0 })}
                  />
                </div>
                <Textarea
                  placeholder='配置 JSON，如 {"token":"xxx"}'
                  rows={6}
                  value={(executorForm.config as unknown as string) || ''}
                  onChange={(e) => setExecutorForm({ ...executorForm, config: e.target.value as any })}
                />
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={handleExecutorSubmit}>保存</Button>
                  {executorForm.id && (
                    <Button variant="ghost" onClick={() => setExecutorForm(emptyExecutor)}>
                      取消
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="workflows" className="space-y-4">
          <SectionHeader title="工作流" description="维护不同 action 对应的工作流定义（ComfyUI、OpenAI Prompt 等）。" />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>工作流列表</CardTitle>
                <CardDescription>支持多版本共存，按 action 检索。</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Action</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>版本</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>更新时间</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workflows.map((wf) => (
                      <TableRow key={wf.id}>
                        <TableCell>{wf.action}</TableCell>
                        <TableCell>
                          <div className="font-medium">{wf.name}</div>
                        </TableCell>
                        <TableCell>{wf.version}</TableCell>
                        <TableCell>{wf.type}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{wf.status}</Badge>
                        </TableCell>
                        <TableCell className="text-xs">{formatDate(wf.updated_at)}</TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button size="sm" variant="ghost" onClick={() => setWorkflowForm({ ...wf, definition: toJSONString(wf.definition) as any, metadata: toJSONString(wf.metadata) as any })}>
                            编辑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleDelete('workflow', wf.id)}>
                            删除
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{workflowForm.id ? '编辑工作流' : '新增工作流'}</CardTitle>
                <CardDescription>将 ComfyUI JSON 或模型 Prompt 存入 definition。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Action" value={workflowForm.action || ''} onChange={(e) => setWorkflowForm({ ...workflowForm, action: e.target.value })} />
                <Input placeholder="名称" value={workflowForm.name || ''} onChange={(e) => setWorkflowForm({ ...workflowForm, name: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <Input placeholder="版本" value={workflowForm.version || ''} onChange={(e) => setWorkflowForm({ ...workflowForm, version: e.target.value })} />
                  <Input placeholder="类型" value={workflowForm.type || ''} onChange={(e) => setWorkflowForm({ ...workflowForm, type: e.target.value })} />
                </div>
                <Input placeholder="状态" value={workflowForm.status || ''} onChange={(e) => setWorkflowForm({ ...workflowForm, status: e.target.value })} />
                <Textarea
                  placeholder="definition JSON"
                  rows={5}
                  value={(workflowForm.definition as unknown as string) || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, definition: e.target.value as any })}
                />
                <Textarea
                  placeholder="metadata JSON（参数映射、依赖等）"
                  rows={4}
                  value={(workflowForm.metadata as unknown as string) || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, metadata: e.target.value as any })}
                />
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={handleWorkflowSubmit}>保存</Button>
                  {workflowForm.id && (
                    <Button variant="ghost" onClick={() => setWorkflowForm(emptyWorkflow)}>
                      取消
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="bindings" className="space-y-4">
          <SectionHeader title="分配策略" description="将用户动作映射到具体工作流与执行节点，可微调优先级与上下线状态。" />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>绑定列表</CardTitle>
                <CardDescription>按 action 排序，查看当前流量流向。</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Action</TableHead>
                      <TableHead>Workflow</TableHead>
                      <TableHead>Executor</TableHead>
                      <TableHead>优先级</TableHead>
                      <TableHead>启用</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {bindings.map((binding) => (
                      <TableRow key={binding.id}>
                        <TableCell>{binding.action}</TableCell>
                        <TableCell>{binding.workflow_id}</TableCell>
                        <TableCell>{binding.executor_id}</TableCell>
                        <TableCell>{binding.priority}</TableCell>
                        <TableCell>
                          <Badge variant={binding.enabled ? 'default' : 'outline'}>{binding.enabled ? 'ON' : 'OFF'}</Badge>
                        </TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button size="sm" variant="ghost" onClick={() => setBindingForm({ ...binding, metadata: toJSONString(binding.metadata) as any })}>
                            编辑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleDelete('binding', binding.id)}>
                            删除
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{bindingForm.id ? '编辑绑定' : '新增绑定'}</CardTitle>
                <CardDescription>设置 action/工作流/执行节点及优先级。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Action" value={bindingForm.action || ''} onChange={(e) => setBindingForm({ ...bindingForm, action: e.target.value })} />
                <Input placeholder="Workflow ID" value={bindingForm.workflow_id || ''} onChange={(e) => setBindingForm({ ...bindingForm, workflow_id: e.target.value })} />
                <Input placeholder="Executor ID" value={bindingForm.executor_id || ''} onChange={(e) => setBindingForm({ ...bindingForm, executor_id: e.target.value })} />
                <Input
                  type="number"
                  placeholder="优先级（越大越靠前）"
                  value={bindingForm.priority ?? 0}
                  onChange={(e) => setBindingForm({ ...bindingForm, priority: Number(e.target.value) || 0 })}
                />
                <div className="flex items-center justify-between rounded border p-3">
                  <div>
                    <Label className="text-sm">启用</Label>
                    <p className="text-xs text-muted-foreground">关闭后不会再调度到该绑定。</p>
                  </div>
                  <Switch checked={bindingForm.enabled ?? true} onCheckedChange={(checked) => setBindingForm({ ...bindingForm, enabled: checked })} />
                </div>
                <Textarea
                  placeholder="metadata JSON"
                  rows={4}
                  value={(bindingForm.metadata as unknown as string) || ''}
                  onChange={(e) => setBindingForm({ ...bindingForm, metadata: e.target.value as any })}
                />
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={handleBindingSubmit}>保存</Button>
                  {bindingForm.id && (
                    <Button variant="ghost" onClick={() => setBindingForm(emptyBinding)}>
                      取消
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="apikeys" className="space-y-4">
          <SectionHeader title="API Keys" description="集中管理多厂商密钥，追踪配额与过期时间，支持轮换。" />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Key 列表</CardTitle>
                <CardDescription>仅展示 key 名称和状态，实际值请使用复制功能。</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>当日用量</TableHead>
                      <TableHead>过期时间</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeys.map((key) => (
                      <TableRow key={key.id}>
                        <TableCell>{key.provider}</TableCell>
                        <TableCell>{key.name}</TableCell>
                        <TableCell>
                          <Badge variant={key.status === 'active' ? 'default' : 'secondary'}>{key.status}</Badge>
                        </TableCell>
                        <TableCell>
                          {key.usage_count ?? 0}
                          {key.daily_quota ? ` / ${key.daily_quota}` : ''}
                        </TableCell>
                        <TableCell className="text-xs">{formatDate(key.expire_at)}</TableCell>
                        <TableCell className="text-right space-x-2">
                          <Button size="sm" variant="ghost" onClick={() => setApiKeyForm({ ...key })}>
                            编辑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleDelete('apikey', key.id)}>
                            删除
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{apiKeyForm.id ? '编辑 Key' : '新增 Key'}</CardTitle>
                <CardDescription>新增时需填写完整 key；编辑时不展示原始值。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input placeholder="Provider" value={apiKeyForm.provider || ''} onChange={(e) => setApiKeyForm({ ...apiKeyForm, provider: e.target.value })} />
                <Input placeholder="名称" value={apiKeyForm.name || ''} onChange={(e) => setApiKeyForm({ ...apiKeyForm, name: e.target.value })} />
                {!apiKeyForm.id && (
                  <Input placeholder="Key Value" value={apiKeyForm.key || ''} onChange={(e) => setApiKeyForm({ ...apiKeyForm, key: e.target.value })} />
                )}
                <Input placeholder="状态" value={apiKeyForm.status || ''} onChange={(e) => setApiKeyForm({ ...apiKeyForm, status: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    type="number"
                    placeholder="日配额"
                    value={apiKeyForm.daily_quota ?? ''}
                    onChange={(e) => setApiKeyForm({ ...apiKeyForm, daily_quota: e.target.value ? Number(e.target.value) : undefined })}
                  />
                  <Input
                    type="number"
                    placeholder="已用次数"
                    value={apiKeyForm.usage_count ?? ''}
                    onChange={(e) => setApiKeyForm({ ...apiKeyForm, usage_count: e.target.value ? Number(e.target.value) : undefined })}
                  />
                </div>
                <Input
                  type="datetime-local"
                  value={apiKeyForm.expire_at ? new Date(apiKeyForm.expire_at).toISOString().slice(0, 16) : ''}
                  onChange={(e) => setApiKeyForm({ ...apiKeyForm, expire_at: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                />
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={handleApiKeySubmit}>保存</Button>
                  {apiKeyForm.id && (
                    <Button variant="ghost" onClick={() => setApiKeyForm(emptyApiKey)}>
                      取消
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetricCard({ title, value, description }: { title: string; value: number; description?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
      {description && (
        <CardContent>
          <p className="text-sm text-muted-foreground">{description}</p>
        </CardContent>
      )}
    </Card>
  );
}

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div>
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-semibold">{title}</h2>
        <Separator className="flex-1" />
      </div>
      {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
    </div>
  );
}
