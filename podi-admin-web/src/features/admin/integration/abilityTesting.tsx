import type { ReactNode } from 'react';
import { Button, Space, Switch, Tag, Typography } from 'tdesign-react';
import type { Ability, ComfyuiQueueStatus, Executor, JsonRecord, StoredAsset } from '../../../types/admin';
import type { UploadResult } from '../../../types/media';
import { formatDateTime } from './formatters';

export type AbilityTestFormView = {
  abilityId: string | null;
  provider: string | null;
  capabilityKey: string | null;
  executorId: string | null;
  params: string;
  imageBase64: string;
  imageUrl: string;
  comfyuiSubmitOnly: boolean;
};

export type AbilityTestResultView = {
  provider?: string;
  model?: string;
  logId?: string | number;
  durationMs?: number;
  taskId?: string;
  state?: string;
  imageBase64?: string;
  imageUrl?: string;
  storedUrl?: string;
  resultUrls?: string[];
  assets?: StoredAsset[];
  text?: string;
  raw?: JsonRecord | null;
};

const classifyOutputUrl = (url?: string | null) => {
  const value = String(url || '').toLowerCase();
  if (/\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?|#|$)/i.test(value)) return 'image';
  if (/\.(mp4|mov|webm|m4v|avi|mkv)(\?|#|$)/i.test(value)) return 'video';
  return 'resource';
};

const collectTestResultUrls = (result?: AbilityTestResultView | null) => {
  if (!result) return [];
  const urls = [
    result.storedUrl,
    result.imageUrl && !result.imageBase64 ? result.imageUrl : '',
    ...(result.assets || []).map((asset) => asset.ossUrl || asset.url || asset.sourceUrl || ''),
    ...(result.resultUrls || []),
  ]
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  return Array.from(new Set(urls));
};

const hasStructuredValue = (value: unknown) => {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
};

const resolveStructuredOutput = (result?: AbilityTestResultView | null): unknown => {
  const raw = result?.raw;
  if (!raw || typeof raw !== 'object') return null;
  const rawRecord = raw as Record<string, unknown>;
  const containers = [
    rawRecord,
    typeof rawRecord.data === 'object' && rawRecord.data ? (rawRecord.data as Record<string, unknown>) : null,
    typeof rawRecord.result === 'object' && rawRecord.result ? (rawRecord.result as Record<string, unknown>) : null,
  ].filter(Boolean) as Record<string, unknown>[];
  const keys = ['jsonOutput', 'outputJson', 'resultOutputJson', 'result_output_json', 'structuredOutput', 'json'];
  for (const container of containers) {
    for (const key of keys) {
      const value = container[key];
      if (hasStructuredValue(value)) return value;
    }
  }
  return null;
};

const resolveTestResultOutput = (result?: AbilityTestResultView | null, previewSrc?: string) => {
  const urls = collectTestResultUrls(result);
  const imageUrls = urls.filter((url) => classifyOutputUrl(url) === 'image');
  const videoUrls = urls.filter((url) => classifyOutputUrl(url) === 'video');
  const resourceUrls = urls.filter((url) => classifyOutputUrl(url) === 'resource');
  const base64Preview = result?.imageBase64 ? previewSrc || '' : '';
  const structuredOutput = resolveStructuredOutput(result);
  const textCount = String(result?.text || '').trim() ? 1 : 0;
  return {
    base64Preview,
    imageUrls,
    videoUrls,
    resourceUrls,
    textCount,
    structuredOutput,
    hasOutput:
      Boolean(base64Preview) ||
      imageUrls.length > 0 ||
      videoUrls.length > 0 ||
      resourceUrls.length > 0 ||
      textCount > 0 ||
      hasStructuredValue(structuredOutput),
  };
};

const formatTestResultState = (state?: string | null) => {
  const normalized = (state || '').trim().toLowerCase();
  if (['success', 'succeeded', 'completed', 'done', 'ok'].includes(normalized)) return '成功';
  if (['failed', 'error', 'timeout', 'rejected'].includes(normalized)) return '失败';
  if (['running', 'processing', 'in_progress'].includes(normalized)) return '执行中';
  if (['queued', 'pending', 'created'].includes(normalized)) return '排队中';
  if (['cancelled', 'canceled', 'stopped', 'aborted'].includes(normalized)) return '已取消';
  return state || '未知';
};

const resolveTestResultAction = (result: AbilityTestResultView, output: ReturnType<typeof resolveTestResultOutput>) => {
  const normalized = (result.state || '').trim().toLowerCase();
  if (['failed', 'error', 'timeout', 'rejected'].includes(normalized)) {
    return {
      theme: 'danger' as const,
      title: '先排查测试失败',
      detail: '看原始响应、密钥、节点和参数；修复后再重新运行测试。',
    };
  }
  if (['running', 'processing', 'in_progress', 'queued', 'pending', 'created'].includes(normalized)) {
    return {
      theme: 'warning' as const,
      title: '等待任务完成',
      detail: '当前只是提交或排队状态，先等待轮询完成；长时间不变再检查节点队列。',
    };
  }
  if (output.hasOutput) {
    return {
      theme: 'success' as const,
      title: '测试通过，可留作验收样本',
      detail: '结果已入库并可在页面查看，后续可进入业务版本验收或小流量验证。',
    };
  }
  return {
    theme: 'warning' as const,
    title: '确认结果入库',
    detail: '接口有响应但页面没有识别到图片、视频、文字或结构化结果，先展开原始响应确认字段。',
  };
};

const summarizeTestOutput = (output: ReturnType<typeof resolveTestResultOutput>) => {
  const parts = [
    output.base64Preview || output.imageUrls.length > 0 ? `${output.imageUrls.length + (output.base64Preview ? 1 : 0)} 张图` : '',
    output.videoUrls.length > 0 ? `${output.videoUrls.length} 个视频` : '',
    output.textCount > 0 ? `${output.textCount} 段文字` : '',
    output.resourceUrls.length > 0 ? `${output.resourceUrls.length} 个资源` : '',
    hasStructuredValue(output.structuredOutput) ? '1 个结构化结果' : '',
  ].filter(Boolean);
  return parts.join(' · ') || '未识别到输出';
};

const stringifyJSON = (value?: string | JsonRecord | null) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

const formatRawResponse = (record?: JsonRecord | null, max = 2000) => {
  if (!record) return '';
  const raw = stringifyJSON(record);
  return raw.length > max ? `${raw.slice(0, max)}…` : raw;
};

function StepTitle({ index, label, hint }: { index: number; label: string; hint?: string }) {
  return (
    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
      <Space align="center" size="small">
        <Tag theme="primary" variant="light">
          {index}
        </Tag>
        <Typography.Text strong>{label}</Typography.Text>
      </Space>
      {hint ? <Typography.Text theme="secondary">{hint}</Typography.Text> : null}
    </Space>
  );
}

function CodeBlock({ value, maxHeight = 320 }: { value: string; maxHeight?: number }) {
  return (
    <pre
      style={{
        marginTop: 8,
        padding: 12,
        borderRadius: 8,
        border: '1px solid var(--td-border-level-1-color)',
        background: 'var(--td-bg-color-secondarycontainer)',
        color: 'var(--td-text-color-primary)',
        fontSize: 12,
        lineHeight: 1.5,
        maxHeight,
        overflow: 'auto',
      }}
    >
      {value}
    </pre>
  );
}

export function AbilityTestingTab({
  selectedAbility,
  abilityExecutors,
  testForm,
  testResult,
  testLoading,
  abilityAllowsImageInput,
  abilityRequiresImageInput,
  uploadingImage,
  uploadedImage,
  uploadError,
  renderedSchemaFieldCount,
  schemaFieldNodes,
  activeComfyExecutorId,
  comfyQueueStatus,
  comfyQueueLoading,
  comfyQueueError,
  comfyQueueUpdatedAt,
  comfyModelLoading,
  comfyModelError,
  hasComfyModelCache,
  testResultPreviewSrc,
  onExecutorChange,
  onImageUrlChange,
  onFileChange,
  onParamsChange,
  onComfySubmitOnlyChange,
  onRefreshComfyQueue,
  onRun,
  getProviderLabel,
}: {
  selectedAbility?: Ability | null;
  abilityExecutors: Executor[];
  testForm: AbilityTestFormView;
  testResult?: AbilityTestResultView | null;
  testLoading: boolean;
  abilityAllowsImageInput: boolean;
  abilityRequiresImageInput: boolean;
  uploadingImage: boolean;
  uploadedImage?: UploadResult | null;
  uploadError?: string | null;
  renderedSchemaFieldCount: number;
  schemaFieldNodes: ReactNode[];
  activeComfyExecutorId?: string | null;
  comfyQueueStatus?: ComfyuiQueueStatus | null;
  comfyQueueLoading: boolean;
  comfyQueueError?: string | null;
  comfyQueueUpdatedAt?: string | null;
  comfyModelLoading: boolean;
  comfyModelError?: string | null;
  hasComfyModelCache: boolean;
  testResultPreviewSrc: string;
  onExecutorChange: (executorId: string | null) => void;
  onImageUrlChange: (value: string) => void;
  onFileChange: (files: FileList | null) => void;
  onParamsChange: (value: string) => void;
  onComfySubmitOnlyChange: (value: boolean) => void;
  onRefreshComfyQueue: () => void;
  onRun: () => void;
  getProviderLabel: (value: string) => string;
}) {
  if (!selectedAbility) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
        请在左侧能力列表中选择一条能力后，再运行链路自检。
      </div>
    );
  }

  const output = resolveTestResultOutput(testResult, testResultPreviewSrc);

  return (
    <div className="space-y-4 text-sm">
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-400">
        当前能力：<span className="text-white">{selectedAbility.display_name}</span>（{getProviderLabel(selectedAbility.provider)}）；
        这里仅用于链路巡检 / 运营测试，实际业务仍应通过能力接口或工作流调度调用。
      </div>
      <StepTitle index={1} label="选择接入节点" hint="系统按厂商/标签优先匹配" />
      <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4 space-y-2">
        <select
          value={abilityExecutors.length === 0 ? '' : testForm.executorId ?? abilityExecutors[0]?.id ?? ''}
          disabled={abilityExecutors.length === 0}
          onChange={(event) => onExecutorChange(event.target.value || null)}
          className="w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
        >
          {abilityExecutors.length === 0 ? (
            <option value="">暂无匹配节点</option>
          ) : (
            abilityExecutors.map((executor) => (
              <option key={executor.id} value={executor.id}>
                {executor.name} · {executor.type}
              </option>
            ))
          )}
        </select>
        {abilityExecutors.length === 0 && (
          <p className="text-xs text-amber-400">
            暂无 {getProviderLabel(selectedAbility.provider)} 类型/标签匹配的节点，请先前往“执行节点”创建并配置该厂商密钥。
          </p>
        )}
      </div>
      {selectedAbility.provider === 'comfyui' && activeComfyExecutorId ? (
        <div className="rounded-2xl border border-sky-900/40 bg-slate-950/40 p-4 text-xs text-slate-300 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-white">ComfyUI 队列状态</p>
              <p className="text-[11px] text-slate-500">
                节点：<span className="font-mono">{activeComfyExecutorId}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={onRefreshComfyQueue}
              className="rounded-full border border-slate-600 px-3 py-1 text-[11px] text-slate-100 hover:border-slate-400"
              disabled={comfyQueueLoading}
            >
              {comfyQueueLoading ? '刷新中…' : '刷新'}
            </button>
          </div>
          {comfyQueueError ? (
            <p className="text-rose-400 text-xs">{comfyQueueError}</p>
          ) : comfyQueueStatus ? (
            <>
              <div className="grid grid-cols-3 gap-3 text-center text-slate-200">
                <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500">运行中</div>
                  <div className="mt-1 text-2xl font-semibold">{comfyQueueStatus.runningCount}</div>
                </div>
                <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500">排队中</div>
                  <div className="mt-1 text-2xl font-semibold">{comfyQueueStatus.pendingCount}</div>
                </div>
                <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500">队列上限</div>
                  <div className="mt-1 text-2xl font-semibold">
                    {typeof comfyQueueStatus.queueMaxSize === 'number' ? comfyQueueStatus.queueMaxSize : '—'}
                  </div>
                </div>
              </div>
              <div className="text-[11px] text-slate-500">基座：{comfyQueueStatus.baseUrl || '—'}</div>
              <div className="text-[11px] text-slate-500">
                最近刷新：{comfyQueueUpdatedAt ? formatDateTime(comfyQueueUpdatedAt) : '刚刚'}
              </div>
              {comfyQueueStatus.supported === false ? (
                <p className="text-[11px] text-amber-400">
                  {comfyQueueStatus.message || '该 ComfyUI 版本未暴露 /queue/status，暂无法获取排队情况。'}
                </p>
              ) : (
                <p className="text-[11px] text-slate-500">
                  ComfyUI 默认单 worker 顺序执行，排队数量 &gt; 0 时说明仍在处理前序任务，可错峰提交或切换其他节点。
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-slate-500">
              {comfyQueueLoading ? '正在获取队列状态…' : '暂无实时数据，请点击刷新。'}
            </p>
          )}
        </div>
      ) : null}
      <StepTitle index={2} label="准备输入" />
      {abilityAllowsImageInput ? (
        <>
          <label className="text-xs text-slate-400">
            图片 URL（可选）
            <input
              type="text"
              value={testForm.imageUrl}
              onChange={(event) => onImageUrlChange(event.target.value)}
              className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white placeholder:text-slate-600"
              placeholder="https://xxx.example.com/image.png"
            />
          </label>
          <label className="text-xs text-slate-400">
            上传图片（或拖拽）
            <input
              type="file"
              accept="image/*"
              onChange={(event) => onFileChange(event.target.files)}
              className="mt-1 block w-full rounded-2xl border border-dashed border-slate-600 bg-slate-950/40 px-4 py-3 text-white"
            />
          </label>
          {uploadingImage ? <p className="text-xs text-sky-400">上传中，请稍候…</p> : null}
          {uploadedImage && !uploadingImage ? (
            <p className="text-xs text-emerald-400">
              已上传：{uploadedImage.name}（{(uploadedImage.size / 1024).toFixed(1)} KB）
            </p>
          ) : null}
          {uploadError ? <p className="text-xs text-rose-400">{uploadError}</p> : null}
          <p className="text-xs text-slate-500">
            上传的文件会暂存到 OSS（podi/test/…），系统会优先使用图片链接，并在需要时自动转换成接口要求的格式。
            {abilityRequiresImageInput ? '本能力为必填输入。' : '若该厂商支持视觉输入，可选填。'}
          </p>
        </>
      ) : (
        <p className="text-xs text-slate-500">该能力不需要图片输入，请直接在下方填写参数或使用默认配置。</p>
      )}
      <StepTitle index={3} label="调节参数（可选）" hint="默认值来自能力配置" />
      {renderedSchemaFieldCount > 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 space-y-3">
          <p className="text-xs text-slate-400">表单由能力配置自动生成，可快速调整提示词、尺寸等关键参数。</p>
          {selectedAbility.provider === 'comfyui' && activeComfyExecutorId ? (
            <p className="text-[11px] text-slate-500">
              {comfyModelLoading
                ? '正在同步该执行节点的模型/LoRA 列表…'
                : comfyModelError
                  ? `模型列表读取失败：${comfyModelError}`
                  : hasComfyModelCache
                    ? '模型/LoRA 列表已载入，可直接从下拉选项选择或手动输入。'
                    : '正在准备模型/LoRA 列表…'}
            </p>
          ) : null}
          <div className="space-y-3">{schemaFieldNodes}</div>
        </div>
      ) : null}
      <details className="rounded-2xl border border-slate-800 bg-slate-950/30 p-3 text-xs text-slate-400">
        <summary className="cursor-pointer text-slate-200">高级参数：覆盖默认配置</summary>
        <label className="mt-3 block">
          附加参数
          <textarea
            rows={renderedSchemaFieldCount > 0 ? 4 : 6}
            className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/60 p-3 text-xs text-white font-mono"
            placeholder='例如 {"temperature":0.6,"top_p":0.8}'
            value={testForm.params}
            onChange={(event) => onParamsChange(event.target.value)}
          />
        </label>
      </details>
      {selectedAbility.provider === 'comfyui' ? (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Switch value={testForm.comfyuiSubmitOnly} onChange={(value) => onComfySubmitOnlyChange(Boolean(value))} />
          提交后不等待（直接入队）
        </div>
      ) : null}
      <button
        onClick={onRun}
        disabled={
          testLoading ||
          !selectedAbility ||
          !testForm.executorId ||
          (abilityRequiresImageInput && !testForm.imageBase64 && !testForm.imageUrl)
        }
        className="w-full rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-500 px-4 py-3 text-white font-semibold disabled:opacity-40"
      >
        {testLoading ? '测试中…' : selectedAbility ? `运行：${selectedAbility.display_name}` : '请选择能力'}
      </button>
      {!testForm.executorId ? (
        <p className="text-xs text-amber-400">
          {abilityExecutors.length === 0
            ? '请先在“执行节点”中新建该厂商的节点，并填入调用密钥。'
            : '请选择一个执行节点，系统会使用该节点绑定的密钥调用接口。'}
        </p>
      ) : null}
      {abilityRequiresImageInput && !testForm.imageBase64 && !testForm.imageUrl ? (
        <p className="text-xs text-amber-400">该能力需要图片，请上传或填写一个可访问的 URL。</p>
      ) : null}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="text-lg font-semibold text-white mb-3">测试结果</h3>
        {testResult ? (
          <>
            {(() => {
              const action = resolveTestResultAction(testResult, output);
              return (
                <div className="mb-3 rounded-2xl border border-slate-800 bg-slate-950/50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag theme={action.theme} variant="light">
                      {action.title}
                    </Tag>
                    <span className="text-xs text-slate-400">输出：{summarizeTestOutput(output)}</span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">{action.detail}</div>
                </div>
              );
            })()}
            {output.base64Preview ? (
              <img src={output.base64Preview} alt="test-result" className="w-full max-h-[360px] rounded object-contain" />
            ) : null}
            {!output.base64Preview && output.imageUrls[0] ? (
              <img src={output.imageUrls[0]} alt="test-result" className="w-full max-h-[360px] rounded object-contain" />
            ) : null}
            {testResult.text ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-100 whitespace-pre-line">
                {testResult.text}
              </div>
            ) : null}
            {hasStructuredValue(output.structuredOutput) ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="text-slate-200">结构化结果</div>
                <CodeBlock value={stringifyJSON(output.structuredOutput as JsonRecord)} maxHeight={220} />
              </div>
            ) : null}
            <div className="mt-3 space-y-1 text-xs text-slate-400">
              {testResult.provider ? <div>厂商：{getProviderLabel(testResult.provider)}</div> : null}
              {testResult.model ? <div>模型：{testResult.model}</div> : null}
              {testResult.state ? <div>状态：{formatTestResultState(testResult.state)}</div> : null}
              {testResult.taskId ? (
                <div className="break-all">
                  任务编号：<span className="font-mono text-slate-200">{testResult.taskId}</span>
                </div>
              ) : null}
              {testResult.logId ? <div>调用记录编号：{testResult.logId}</div> : null}
              {typeof testResult.durationMs === 'number' ? <div>耗时：{testResult.durationMs} ms</div> : null}
            </div>
            {output.videoUrls.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="text-slate-200">视频输出</div>
                <ul className="mt-2 space-y-1">
                  {output.videoUrls.map((url, index) => (
                    <li key={`video-url-${index}`} className="break-all">
                      <a href={url} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                        打开视频 {index + 1}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {output.resourceUrls.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="text-slate-200">其他资源</div>
                <ul className="mt-2 space-y-1">
                  {output.resourceUrls.map((url, index) => (
                    <li key={`resource-url-${index}`} className="break-all">
                      <a href={url} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {testResult.assets && testResult.assets.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="text-slate-200">已同步至素材存储</div>
                <ul className="mt-2 space-y-1">
                  {testResult.assets.map((asset, index) => {
                    const assetUrl = asset.ossUrl || asset.url || asset.sourceUrl || '';
                    if (!assetUrl) return null;
                    return (
                      <li key={asset.ossKey || assetUrl || index} className="break-all">
                        <span className="text-slate-500">[{asset.tag || asset.type || `asset-${index + 1}`}] </span>
                        <a href={assetUrl} target="_blank" rel="noreferrer" className="text-emerald-400 underline">
                          {assetUrl}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
            {testResult.resultUrls && testResult.resultUrls.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="text-slate-200">上游原始链接（排障）</div>
                <ul className="mt-2 space-y-1">
                  {testResult.resultUrls.map((url, index) => (
                    <li key={`result-url-${index}`} className="break-all">
                      <a href={url} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {testResult.raw ? (
              <details className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                <summary className="cursor-pointer text-slate-200">高级排障：原始响应</summary>
                <CodeBlock value={formatRawResponse(testResult.raw)} maxHeight={240} />
              </details>
            ) : null}
            {!output.hasOutput ? (
              <div className="mt-4 text-sm text-slate-500">调用完成但未返回可预览内容，可展开原始响应确认详情。</div>
            ) : null}
          </>
        ) : (
          <div className="text-sm text-slate-500">
            步骤填写完成后点击“运行测试”，结果会在此处预览；如需保存到任务列表，请改用正式任务流程。
          </div>
        )}
      </div>
    </div>
  );
}
