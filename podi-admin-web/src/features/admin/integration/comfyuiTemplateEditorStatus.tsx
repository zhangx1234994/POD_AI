import { Tag, Typography } from 'tdesign-react';
import type { WorkflowFormState } from '../../../types/admin';

type Props = {
  workflowForm: WorkflowFormState;
  workflowInputCount: number;
  workflowOutputCount: number;
  allowedExecutorCount: number;
  workflowDefinitionError?: string;
  workflowMetadataError?: string;
  workflowMappingErrorCount: number;
  workflowFormErrorCount: number;
};

type StepStatus = {
  label: string;
  ok: boolean;
  detail: string;
};

export function ComfyuiTemplateEditorStatus({
  workflowForm,
  workflowInputCount,
  workflowOutputCount,
  allowedExecutorCount,
  workflowDefinitionError,
  workflowMetadataError,
  workflowMappingErrorCount,
  workflowFormErrorCount,
}: Props) {
  const actionReady = Boolean(workflowForm.action?.trim());
  const nameReady = Boolean(workflowForm.name?.trim());
  const definitionReady = Boolean(workflowForm.definition?.trim()) && !workflowDefinitionError;
  const metadataReady = !workflowMetadataError;
  const hasErrors = workflowMappingErrorCount > 0 || workflowFormErrorCount > 0 || Boolean(workflowDefinitionError || workflowMetadataError);
  const steps: StepStatus[] = [
    {
      label: '基础信息',
      ok: actionReady && nameReady,
      detail: actionReady && nameReady ? '入口和名称已填写' : '需要填写业务入口和名称',
    },
    {
      label: '流程 JSON',
      ok: definitionReady,
      detail: definitionReady ? '已导入且格式正常' : workflowDefinitionError || '需要导入 ComfyUI API JSON',
    },
    {
      label: '输入/输出',
      ok: workflowInputCount > 0 && workflowOutputCount > 0,
      detail: `输入 ${workflowInputCount} 个，输出 ${workflowOutputCount || '默认全部'}`,
    },
    {
      label: '运行线路',
      ok: allowedExecutorCount > 0,
      detail: allowedExecutorCount > 0 ? `已限制 ${allowedExecutorCount} 条线路` : '未限制线路，将由调度默认选择',
    },
    {
      label: '保存检查',
      ok: !hasErrors && metadataReady,
      detail: hasErrors ? `还有 ${workflowMappingErrorCount + workflowFormErrorCount} 个配置问题` : '当前未发现阻塞问题',
    },
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Typography.Text strong>配置进度</Typography.Text>
        <Typography.Text theme="secondary">
          先把红色项处理掉，再保存模板。
        </Typography.Text>
      </div>
      <div className="grid gap-2 md:grid-cols-5">
        {steps.map((step) => (
          <div key={step.label} className="rounded-xl border border-white bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900/70">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="font-semibold text-slate-900 dark:text-white">{step.label}</span>
              <Tag theme={step.ok ? 'success' : 'warning'} variant="light" size="small">
                {step.ok ? '正常' : '待处理'}
              </Tag>
            </div>
            <div className="text-slate-600 dark:text-slate-400">{step.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
