import { Col, Dialog, Input, Row, Select, Space, Switch, Textarea, Tooltip, Typography } from 'tdesign-react';
import type { AbilityFormState, Executor, VendorModel, Workflow } from '../../../types/admin';
import { abilityTypeOptions, categoryOptions, providerOptions, statusOptions } from './formOptions';

type SelectOption = {
  label: string;
  value: string | number;
};

const formControlClass =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';

export function AbilityEditorDialog({
  visible,
  form,
  executors,
  workflows,
  vendorModels,
  vendorModelOptions,
  comfyExecutors,
  routingPolicy,
  fallbackToDefault,
  allowedExecutors,
  requiredTags,
  loraDefault,
  loraOptions,
  loraAllowedFiles,
  loraAllowedTags,
  loraAllowedBaseModels,
  baseModelOptions,
  loraPolicy,
  onClose,
  onSubmit,
  onFormChange,
  onRoutingPolicyChange,
  onFallbackToDefaultChange,
  onAllowedExecutorsChange,
  onRequiredTagsChange,
  onLoraDefaultChange,
  onLoraAllowedFilesChange,
  onLoraAllowedTagsChange,
  onLoraAllowedBaseModelsChange,
  onLoraPolicyChange,
}: {
  visible: boolean;
  form: AbilityFormState;
  executors: Executor[];
  workflows: Workflow[];
  vendorModels: VendorModel[];
  vendorModelOptions: SelectOption[];
  comfyExecutors: Executor[];
  routingPolicy: string;
  fallbackToDefault: boolean;
  allowedExecutors: string[];
  requiredTags: string;
  loraDefault: string;
  loraOptions: SelectOption[];
  loraAllowedFiles: string[];
  loraAllowedTags: string;
  loraAllowedBaseModels: string[];
  baseModelOptions: string[];
  loraPolicy: string;
  onClose: () => void;
  onSubmit: () => Promise<void> | void;
  onFormChange: (form: AbilityFormState) => void;
  onRoutingPolicyChange: (value: string) => void;
  onFallbackToDefaultChange: (value: boolean) => void;
  onAllowedExecutorsChange: (value: string[]) => void;
  onRequiredTagsChange: (value: string) => void;
  onLoraDefaultChange: (value: string) => void;
  onLoraAllowedFilesChange: (value: string[]) => void;
  onLoraAllowedTagsChange: (value: string) => void;
  onLoraAllowedBaseModelsChange: (value: string[]) => void;
  onLoraPolicyChange: (value: string) => void;
}) {
  return (
    <Dialog
      header={form.id ? '编辑能力' : '新增能力'}
      visible={visible}
      width={760}
      onClose={onClose}
      onConfirm={async () => {
        await onSubmit();
      }}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Row gutter={[12, 12]}>
          <Col span={6}>
            <Typography.Text theme="secondary">厂商</Typography.Text>
            <Select
              value={form.provider || providerOptions[0].value}
              onChange={(value) => onFormChange({ ...form, provider: String(value) })}
              options={providerOptions}
            />
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">能力类型</Typography.Text>
            <Select
              value={form.ability_type || abilityTypeOptions[0].value}
              onChange={(value) => onFormChange({ ...form, ability_type: String(value) })}
              options={abilityTypeOptions}
            />
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">能力分类</Typography.Text>
            <Select
              value={form.category || categoryOptions[0].value}
              onChange={(value) => onFormChange({ ...form, category: String(value) })}
              options={categoryOptions}
            />
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">状态</Typography.Text>
            <Select
              value={form.status || statusOptions[0].value}
              onChange={(value) => onFormChange({ ...form, status: String(value) })}
              options={statusOptions}
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col span={12}>
            <Typography.Text theme="secondary">能力标识</Typography.Text>
            <Input
              value={form.capability_key || ''}
              onChange={(value) => onFormChange({ ...form, capability_key: String(value) })}
              placeholder="例如 quality_upgrade"
            />
          </Col>
          <Col span={12}>
            <Typography.Text theme="secondary">展示名称</Typography.Text>
            <Input
              value={form.display_name || ''}
              onChange={(value) => onFormChange({ ...form, display_name: String(value) })}
              placeholder="例如 百度无损放大"
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col span={6}>
            <Typography.Text theme="secondary">版本</Typography.Text>
            <Input
              value={form.version || 'v1'}
              onChange={(value) => onFormChange({ ...form, version: String(value) })}
              placeholder="例如 v1"
            />
          </Col>
        </Row>

        <div>
          <Typography.Text theme="secondary">描述（选填）</Typography.Text>
          <Input
            value={form.description || ''}
            onChange={(value) => onFormChange({ ...form, description: String(value) })}
            placeholder="一句话说明用途"
          />
        </div>

        <Row gutter={[12, 12]}>
          <Col span={12}>
            <Typography.Text theme="secondary">默认节点（可选）</Typography.Text>
            <Select
              value={form.executor_id || ''}
              onChange={(value) => onFormChange({ ...form, executor_id: String(value) || undefined })}
              options={[
                { label: '自动匹配', value: '' },
                ...executors.map((executor) => ({
                  label: `${executor.name} · ${executor.type}`,
                  value: executor.id,
                })),
              ]}
              placeholder="自动匹配"
            />
          </Col>
          <Col span={12}>
            <Typography.Text theme="secondary">关联工作流（可选）</Typography.Text>
            <Select
              value={form.workflow_id || ''}
              onChange={(value) => onFormChange({ ...form, workflow_id: String(value) || undefined })}
              options={[
                { label: '未绑定', value: '' },
                ...workflows.map((workflow) => ({
                  label: `${workflow.name} · ${workflow.version || workflow.type}`,
                  value: workflow.id,
                })),
              ]}
              placeholder="未绑定"
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col span={12}>
            <Typography.Text theme="secondary">绑定模型（可选，来自模型弹药库）</Typography.Text>
            <Select
              value={form.vendor_model_id || 0}
              onChange={(value) => {
                const nextId = Number(value) || null;
                const selected = vendorModels.find((item) => item.id === nextId);
                onFormChange({
                  ...form,
                  vendor_model_id: nextId,
                  provider: selected?.provider || form.provider,
                });
              }}
              options={[
                { label: '不绑定模型', value: 0 },
                ...vendorModelOptions.map((item) => ({ label: item.label, value: item.value })),
              ]}
              placeholder="不绑定模型"
            />
            <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
              绑定后，业务配方可直接引用这个模型配置，减少手填模型名和能力边界。
            </Typography.Text>
          </Col>
        </Row>

        {form.provider === 'comfyui' ? (
          <div className="rounded-2xl border border-slate-200/70 bg-slate-50/40 p-4 dark:border-slate-800 dark:bg-slate-950/40">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text strong>ComfyUI 路由策略（面向非技术同学的配置）</Typography.Text>
              <Typography.Text theme="secondary">
                这些字段会写入 ability.metadata，用于控制“哪些节点可用、如何分配、是否允许回退默认节点”。
              </Typography.Text>

              <Row gutter={[12, 12]}>
                <Col span={12}>
                  <Typography.Text theme="secondary">路由策略 routing_policy</Typography.Text>
                  <Select
                    value={routingPolicy}
                    onChange={(value) => onRoutingPolicyChange(String(value) || 'auto')}
                    options={[
                      { label: '自动（默认：跟随系统设置）', value: 'auto' },
                      { label: '按队列最短（queue）', value: 'queue' },
                      { label: '按权重随机（weight）', value: 'weight' },
                      { label: '轮询（round_robin）', value: 'round_robin' },
                      { label: '固定第一个（fixed）', value: 'fixed' },
                    ]}
                  />
                  <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                    建议：对性能敏感可用 weight/round_robin，想避开排队可用 queue。
                  </Typography.Text>
                </Col>
                <Col span={12}>
                  <Space align="center" size="small">
                    <Typography.Text theme="secondary">回退到默认节点</Typography.Text>
                    <Tooltip content="当没有符合条件的节点时，是否允许系统回退到默认/绑定节点。">
                      <Typography.Text theme="secondary">?</Typography.Text>
                    </Tooltip>
                  </Space>
                  <div style={{ marginTop: 8 }}>
                    <Switch value={fallbackToDefault} onChange={(value) => onFallbackToDefaultChange(Boolean(value))} />
                  </div>
                  <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                    关闭后：不匹配即报错，适合严格分机的生产能力。
                  </Typography.Text>
                </Col>
              </Row>

              <div>
                <Typography.Text theme="secondary">允许运行节点（多选）</Typography.Text>
                {comfyExecutors.length > 0 ? (
                  <select
                    multiple
                    value={allowedExecutors}
                    onChange={(event) =>
                      onAllowedExecutorsChange(Array.from(event.target.selectedOptions).map((option) => option.value))
                    }
                    className="mt-2 h-32 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                  >
                    {comfyExecutors.map((executor) => (
                      <option key={`ability-executor-${executor.id}`} value={executor.id}>
                        {executor.name} · {executor.base_url || executor.type}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-slate-700 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                    还没有 ComfyUI 执行节点，请先在“执行节点”里新增。
                  </div>
                )}
                <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                  不选表示“允许系统自动匹配所有 ComfyUI 节点”。
                </Typography.Text>
              </div>

              <div>
                <Typography.Text theme="secondary">要求标签（required_tags，可多选）</Typography.Text>
                <Input
                  value={requiredTags}
                  onChange={(value) => onRequiredTagsChange(String(value))}
                  placeholder="例如：gpu:4090, region:hz, comfyui-158"
                />
                <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                  逗号分隔。要求执行节点 config.tags 中包含全部标签。
                </Typography.Text>
              </div>

              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-950/40">
                <Typography.Text className="text-sm font-semibold text-slate-900 dark:text-white">LoRA 绑定规则</Typography.Text>
                <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                  用于限制能力可选 LoRA，并统一默认值（避免误选导致输出异常）。
                </Typography.Text>
                <Space direction="vertical" size="middle" style={{ width: '100%', marginTop: 12 }}>
                  <div>
                    <Typography.Text theme="secondary">默认 LoRA（不填则保持原参数）</Typography.Text>
                    <input
                      list="ability-lora-options"
                      value={loraDefault}
                      onChange={(event) => onLoraDefaultChange(event.target.value)}
                      placeholder="从 LoRA 清单选择或手动输入文件名"
                      className={`${formControlClass} mt-2`}
                    />
                    <datalist id="ability-lora-options">
                      {loraOptions.map((option) => (
                        <option key={`ability-lora-option-${option.value}`} value={String(option.value)} />
                      ))}
                    </datalist>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">允许运行的 LoRA（多选）</Typography.Text>
                    {loraOptions.length > 0 ? (
                      <select
                        multiple
                        value={loraAllowedFiles}
                        onChange={(event) =>
                          onLoraAllowedFilesChange(Array.from(event.target.selectedOptions).map((option) => option.value))
                        }
                        className="mt-2 h-32 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                      >
                        {loraOptions.map((option) => (
                          <option key={`ability-lora-${option.value}`} value={String(option.value)}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                        LoRA 清单为空，请先在“ComfyUI 管理”中维护。
                      </div>
                    )}
                    <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                      不选表示“允许全部 LoRA”。
                    </Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">允许运行的 LoRA 标签（逗号分隔）</Typography.Text>
                    <Input
                      value={loraAllowedTags}
                      onChange={(value) => onLoraAllowedTagsChange(String(value))}
                      placeholder="例如：杯子, 毛毯, 服饰"
                    />
                    <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                      标签会与 LoRA 清单匹配过滤，配合“允许运行的 LoRA”使用。
                    </Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">允许运行的基座模型（多选）</Typography.Text>
                    {baseModelOptions.length > 0 ? (
                      <select
                        multiple
                        value={loraAllowedBaseModels}
                        onChange={(event) =>
                          onLoraAllowedBaseModelsChange(Array.from(event.target.selectedOptions).map((option) => option.value))
                        }
                        className="mt-2 h-28 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                      >
                        {baseModelOptions.map((model) => (
                          <option key={`ability-base-model-${model}`} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                        还未加载到基座模型清单，请刷新 ComfyUI 模型。
                      </div>
                    )}
                    <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                      不选表示不限制基座模型。
                    </Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">不匹配时处理</Typography.Text>
                    <Select
                      value={loraPolicy}
                      onChange={(value) => onLoraPolicyChange(String(value))}
                      options={[
                        { label: '回退到默认 LoRA', value: 'fallback' },
                        { label: '直接忽略（使用原配置）', value: 'ignore' },
                      ]}
                    />
                  </div>
                </Space>
              </div>
            </Space>
          </div>
        ) : null}

        {form.provider === 'coze' ? (
          <div>
            <Typography.Text theme="secondary">Coze 工作流编号</Typography.Text>
            <Input
              value={form.coze_workflow_id || ''}
              onChange={(value) =>
                onFormChange({
                  ...form,
                  coze_workflow_id: String(value).trim() ? String(value).trim() : undefined,
                })
              }
              placeholder="例如 1234567890"
            />
          </div>
        ) : null}

        <div>
          <Typography.Text theme="secondary">默认参数（高级）</Typography.Text>
          <Textarea
            value={form.default_params || ''}
            onChange={(value) => onFormChange({ ...form, default_params: String(value) })}
            autosize={{ minRows: 3, maxRows: 8 }}
          />
        </div>

        <div>
          <Typography.Text theme="secondary">输入表单配置（选填）</Typography.Text>
          <Textarea
            value={form.input_schema || ''}
            onChange={(value) => onFormChange({ ...form, input_schema: String(value) })}
            autosize={{ minRows: 3, maxRows: 8 }}
          />
        </div>

        <div>
          <Typography.Text theme="secondary">其他元信息（选填）</Typography.Text>
          <Textarea
            value={form.metadata || ''}
            onChange={(value) => onFormChange({ ...form, metadata: String(value) })}
            autosize={{ minRows: 3, maxRows: 8 }}
          />
        </div>
      </Space>
    </Dialog>
  );
}
