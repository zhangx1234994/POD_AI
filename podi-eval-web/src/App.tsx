import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactNode, MouseEvent as ReactMouseEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Dialog,
  Input,
  Layout,
  Menu,
  Rate,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Textarea,
  Typography,
  MessagePlugin,
} from 'tdesign-react';
import {
  AiImageIcon,
  ChartBubbleIcon,
  ImageEditIcon,
  LayersIcon,
  ScanIcon,
  TaskIcon,
} from 'tdesign-icons-react';
import zhCN from 'tdesign-react/es/locale/zh_CN';
import { ApiRequestError, evalApi } from './api';
import type { ComfyuiQueueSummary, EvalOperationsHealth, EvalRun, EvalWorkflowVersion, SchemaField, WorkflowDoc } from './types';
import { EvalShell } from './layouts/EvalShell';
import { ActionBar, FilterBar, StatusBadge } from './features/eval/shared/ui';
import { mapStatusToBadge } from './features/eval/shared/status';
import type { ThemeMode } from './types/ui';
import { toDisplayErrorMessage } from './utils/errorMessageMap';

type RunWithLatest = EvalRun & {
  latest_annotation?: { rating: number; comment?: string | null; created_at: string; created_by: string } | null;
};

type EditorTool = 'point' | 'rect' | 'circle' | 'freehand';

type EditorPoint = { x: number; y: number };

type EditorMark = {
  id: string;
  name: string;
  type: EditorTool;
  points: EditorPoint[];
  created_at: number;
};

type PromptHint = {
  type: 'mark' | 'ref';
  query: string;
  start: number;
  end: number;
};

type LoraOption = { label: string; value: string };

type WorkflowMetric = {
  ratingCount: number;
  avgRating: number | null;
  runCount?: number;
  recentRunCount?: number;
  recentSuccessCount?: number;
  recentFailureCount?: number;
  recentRunningCount?: number;
  recentNoOutputCount?: number;
  recentOutputKindCounts?: Record<string, number>;
  recentHours?: number;
  lastRunStatus?: string | null;
  lastRunAt?: string | null;
  lastRunHasOutput?: boolean | null;
  lastRunOutputKind?: string | null;
  lastErrorCode?: string | null;
  lastErrorMessage?: string | null;
};

type ToolHistoryFocus = 'all' | 'succeeded' | 'failed' | 'running' | 'no_output';

type LoraBatchWorkflowMeta = {
  workflow: EvalWorkflowVersion;
  urlFieldName: string;
  loraField: SchemaField | null;
  loraSource?: string;
  loraOptions: LoraOption[];
};

type LoraBatchItemStatus = 'pending' | 'uploading' | 'submitting' | 'submitted' | 'failed';
type LoraBatchRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'unknown';
type LoraBatchReviewVerdict = 'pending' | 'satisfied' | 'unsatisfied';

type LoraBatchReview = {
  verdict: LoraBatchReviewVerdict;
  reason?: string;
  note?: string;
};

type LoraBatchOutputReview = {
  outputIndex: number;
  verdict: LoraBatchReviewVerdict;
  reason?: string;
  note?: string;
};

type LoraBatchSubView = 'generation' | 'annotation';

type LoraReviewGroupOutput = {
  reviewKey: string;
  runItemId: string;
  runId?: string;
  outputIndex: number;
  url: string;
  runStatus?: string;
};

type LoraReviewGroup = {
  assetId: string;
  sourceKey: string;
  fileName: string;
  inputUrl?: string;
  groupStatus: 'has_output' | 'no_output' | 'failed' | string;
  runTotal: number;
  completed: number;
  failed: number;
  waiting: number;
  lastError?: string;
  outputs: LoraReviewGroupOutput[];
};

type LoraReviewProgress = {
  pageSize: number;
  currentPage: number;
  completedPage: number;
  updatedAt?: string;
};

type LoraBatchItem = {
  key: string;
  batchId?: string;
  sourceKey?: string;
  fileName: string;
  repeatIndex: number;
  status: LoraBatchItemStatus;
  failureStage?: 'upload' | 'submit' | 'run';
  runItemId?: string;
  runId?: string;
  inputUrl?: string;
  error?: string;
  runStatus?: LoraBatchRunStatus;
  outputCount?: number;
  runError?: string;
  outputUrls?: string[];
  outputReviews?: LoraBatchOutputReview[];
  runPrompt?: string;
};

type LoraBatchSession = {
  batchId: string;
  workflowVersionId?: string | null;
  workflowName?: string | null;
  status?: string;
  total: number;
  completed: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  submittedCount?: number;
  uploadedCount?: number;
  uploadFailedCount?: number;
  expectedTotal?: number;
  expectedImages?: number;
  expectedRepeat?: number;
  latestCreatedAt?: string | null;
  latestUpdatedAt?: string | null;
};

type LoraBatchUploadProgress = {
  batchId: string;
  totalFiles: number;
  totalBytes: number;
  uploadedFiles: number;
  failedFiles: number;
  activeFiles: number;
  uploadedBytes: number;
};

type RemoteLoadStatus = 'idle' | 'loading' | 'success' | 'error';

type RemoteLoadError = {
  kind: 'http' | 'network' | 'timeout' | 'unknown';
  status?: number;
  message: string;
  rawBody?: string;
};

// Evaluation categories follow the business taxonomy, not vendor or workflow names.
const CATEGORY_ORDER = [
  '花纹提取',
  '图裂变',
  '扩图',
  '连续图',
  '抠图',
  '图像融合',
  '图像增强',
  '图像理解',
  '文本与提示词',
  '生视频',
  '平台工具',
];
const DEFAULT_CATEGORY = '图裂变';
const PINNED_CATEGORY_SET = new Set(['花纹提取', '图裂变', '扩图', '连续图']);
type EvalView = 'home' | 'tool' | 'tasks' | 'admin' | 'docs' | 'loraBatch';
const EVAL_VIEW_SET = new Set<EvalView>(['home', 'tool', 'tasks', 'admin', 'docs', 'loraBatch']);

const readEvalQuery = () => {
  if (typeof window === 'undefined') {
    return { view: 'home' as EvalView, category: DEFAULT_CATEGORY, toolId: '' };
  }
  const params = new URLSearchParams(window.location.search);
  const viewRaw = String(params.get('view') || '').trim();
  const view = EVAL_VIEW_SET.has(viewRaw as EvalView) ? (viewRaw as EvalView) : ('home' as EvalView);
  const categoryRaw = String(params.get('category') || '').trim();
  const category = CATEGORY_ORDER.includes(categoryRaw) ? categoryRaw : DEFAULT_CATEGORY;
  const toolId = String(params.get('tool') || '').trim();
  return { view, category, toolId };
};

const AI_EDITOR_WORKFLOW_ID = '7604714915110060032';
const SHENGTU_WORKFLOW_ID = '7602916576198656000';
const LORA_BATCH_MAX_TASKS = 5000;
const TERMINAL_BATCH_STATUS = new Set(['succeeded', 'failed', 'stopped']);
const COMFYUI_EXECUTOR_LABELS: Record<string, string> = {
  executor_comfyui_pattern_extract_158: '158 图形能力机',
  executor_comfyui_seamless_117: '117 连续图能力机',
};

const isTerminalBatchStatus = (status?: string | null): boolean =>
  TERMINAL_BATCH_STATUS.has(String(status || '').toLowerCase());

const isUploadStageFailure = (item: LoraBatchItem): boolean => {
  if (item.failureStage === 'upload') return true;
  if (item.failureStage) return false;
  if (item.status !== 'failed') return false;
  if (item.runId) return false;
  const msg = String(item.error || item.runError || '').toLowerCase();
  return msg.includes('上传') || msg.includes('upload') || msg.includes('sts') || msg.includes('upload-key');
};

const buildBatchReviewKey = (runItemId: string, outputIndex: number): string =>
  `${String(runItemId || '').trim()}::${Math.max(1, Number(outputIndex || 1))}`;

const formatErrorCodeLabel = (code?: string | null): string => {
  const raw = String(code || '').trim();
  if (!raw) return '未归类错误';
  const mapped = toDisplayErrorMessage(raw);
  return mapped ? mapped.replace(`（${raw}）`, '') : raw;
};

const formatEvalStageStatus = (
  stage: 'submit' | 'callback' | 'final',
  status?: string | null,
): string => {
  const value = String(status || '').toLowerCase();
  if (!value) return '未记录';
  if (stage === 'submit') {
    if (value === 'pending') return '待提交';
    if (value === 'submitting') return '提交中';
    if (value === 'submit_failed') return '提交失败';
    if (value === 'submitted') return '已提交';
  }
  if (stage === 'callback') {
    if (value === 'waiting') return '等待回填';
    if (value === 'running') return '回填中';
    if (value === 'success') return '回填成功';
    if (value === 'failed') return '回填失败';
    if (value === 'not_configured') return '未配置回调';
  }
  if (stage === 'final') {
    if (value === 'pending') return '未结束';
    if (value === 'canceled' || value === 'cancelled') return '已取消';
    return mapStatusToBadge(value).text;
  }
  return value;
};

const getEvalStageTone = (
  status?: string | null,
): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
  const value = String(status || '').toLowerCase();
  if (!value || value === 'not_configured') return 'default';
  if (value.includes('fail') || value.includes('error') || value.includes('cancel')) return 'danger';
  if (value === 'success' || value === 'succeeded' || value === 'completed') return 'success';
  if (value === 'submitted' || value === 'running' || value === 'submitting') return 'primary';
  if (value === 'waiting' || value === 'pending' || value === 'queued') return 'warning';
  return 'default';
};

const getOutputTone = (
  outputLabel: string,
): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
  if (
    outputLabel.includes('已回填') ||
    outputLabel.includes('非图片') ||
    outputLabel.includes('文字') ||
    outputLabel.includes('结构化') ||
    outputLabel.includes('视频')
  ) return 'success';
  if (outputLabel.includes('等待')) return 'primary';
  if (outputLabel.includes('成功无回填')) return 'warning';
  if (outputLabel.includes('无结果')) return 'danger';
  return 'default';
};

const formatComfyuiExecutorLabel = (executorId?: string | null): string => {
  const raw = String(executorId || '').trim();
  return COMFYUI_EXECUTOR_LABELS[raw] || raw || '未命名节点';
};

const getFailureActionMeta = (code?: string | null, message?: string | null) => {
  const rawCode = String(code || '').trim();
  const text = `${rawCode} ${message || ''}`.toLowerCase();
  if (rawCode === 'VENDOR_CREDITS_INSUFFICIENT' || text.includes('credits insufficient') || text.includes('balance')) {
    return {
      label: '第三方账号余额不足',
      theme: 'warning' as const,
      suggestion: '先充值或切换可用 Key；如果暂时不测商业模型，可先避开这类工作流。',
    };
  }
  if (rawCode === 'INTERNAL_ONLY' || text.includes('internal_only')) {
    return {
      label: '历史工具箱权限事故',
      theme: 'danger' as const,
      suggestion: '如果不再新增同类失败，说明修复已生效；保留观察到 24 小时窗口自然消失。',
    };
  }
  if (rawCode === 'COMFYUI_QUEUE_STATUS_ERROR' || text.includes('comfyui_queue')) {
    return {
      label: 'ComfyUI 队列不可达',
      theme: 'danger' as const,
      suggestion: '检查对应 ComfyUI 服务和网络；中台会把不可读节点标记为异常，避免继续误投。',
    };
  }
  if (rawCode === 'TASK_IMAGES_EMPTY' || rawCode === 'CALLBACK_IMAGES_EMPTY' || text.includes('images_empty')) {
    return {
      label: '已执行但没有结果图',
      theme: 'warning' as const,
      suggestion: '优先查回填链路和工作流输出节点，确认是否生成完成但没有落到 OSS。',
    };
  }
  return {
    label: rawCode ? formatErrorCodeLabel(rawCode) : '未归类失败',
    theme: 'default' as const,
    suggestion: '打开任务追踪查看原始错误；必要时把该工作流单独复测。',
  };
};

const buildFailureActionItems = (runs: EvalOperationsHealth['recentFailures'] = []) => {
  const grouped = new Map<
    string,
    {
      code: string;
      label: string;
      theme: 'default' | 'primary' | 'warning' | 'danger' | 'success';
      suggestion: string;
      count: number;
      sampleName: string;
    }
  >();
  runs.forEach((run) => {
    const code = String(run.errorCode || 'UNCLASSIFIED').trim();
    const meta = getFailureActionMeta(code, run.errorMessage);
    const item = grouped.get(code) || {
      code,
      label: meta.label,
      theme: meta.theme,
      suggestion: meta.suggestion,
      count: 0,
      sampleName: run.workflowName || run.workflowId || run.runId,
    };
    item.count += 1;
    grouped.set(code, item);
  });
  return Array.from(grouped.values()).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'zh-CN'));
};

const parseBatchReviewKey = (key: string): { runItemId: string; outputIndex: number } | null => {
  const parts = String(key || '').split('::');
  if (parts.length !== 2) return null;
  const runItemId = String(parts[0] || '').trim();
  const outputIndex = Number(parts[1] || 0);
  if (!runItemId || !Number.isFinite(outputIndex) || outputIndex <= 0) return null;
  return { runItemId, outputIndex: Math.floor(outputIndex) };
};

const isBatchSizeFieldName = (name: string): boolean =>
  name === 'aspect_ratio' ||
  name === 'aspectRatio' ||
  String(name || '').toLowerCase() === 'resolution' ||
  name === 'width' ||
  name === 'height';

const fitLongestEdge = (width: number, height: number, longest = 1024): { width: number; height: number } | null => {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const maxSide = Math.max(width, height);
  if (maxSide <= 0) return null;
  const scale = longest / maxSide;
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));
  return { width: w, height: h };
};

const inferFileNameFromUrl = (url: string): string => {
  const raw = String(url || '').trim();
  if (!raw) return '未命名图片';
  try {
    const u = new URL(raw);
    const name = decodeURIComponent(String(u.pathname || '').split('/').pop() || '');
    return name || '未命名图片';
  } catch {
    const name = decodeURIComponent(raw.split('?')[0].split('/').pop() || '');
    return name || '未命名图片';
  }
};

const loadImageSizeFromFile = async (file: File): Promise<{ width: number; height: number } | null> => {
  const blobUrl = URL.createObjectURL(file);
  try {
    const img = new Image();
    const size = await new Promise<{ width: number; height: number } | null>((resolve) => {
      img.onload = () => resolve({ width: img.naturalWidth || 0, height: img.naturalHeight || 0 });
      img.onerror = () => resolve(null);
      img.src = blobUrl;
    });
    return size;
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
};

const loadImageSizeFromUrl = async (url: string): Promise<{ width: number; height: number } | null> => {
  const target = String(url || '').trim();
  if (!target) return null;
  try {
    const img = new Image();
    const size = await new Promise<{ width: number; height: number } | null>((resolve) => {
      img.onload = () => resolve({ width: img.naturalWidth || 0, height: img.naturalHeight || 0 });
      img.onerror = () => resolve(null);
      img.src = target;
    });
    return size;
  } catch {
    return null;
  }
};

const normalizeCategory = (category: string | undefined | null): string => {
  const c = String(category || '').trim();
  if (!c) return '平台工具';
  if (CATEGORY_ORDER.includes(c)) return c;
  // Legacy/internal keys -> business labels
  if (c === '花纹提取类' || c === 'pattern_extract' || c === 'pattern' || c === 'pattern-extract') return '花纹提取';
  if (c === '图延伸类' || c === 'image_extend' || c === 'image_extension' || c === '图扩展' || c === '图延伸') return '扩图';
  if (c === '四方/两方连续图类' || c === 'continuous_pattern' || c === 'continuous' || c === 'lianxu') return '连续图';
  if (c === 'image_fission' || c === 'fission' || c === 'variation' || c === 'image_variation' || c === 'liebain' || c === 'liebiam') return '图裂变';
  if (c === 'cutout' || c === 'background_remove' || c === 'matting') return '抠图';
  if (c === 'image_composition' || c === 'composition' || c === 'fusion') return '图像融合';
  if (c === 'image_enhancement' || c === 'enhancement' || c === 'upscale') return '图像增强';
  if (c === 'vision_analysis' || c === 'vision' || c === 'vl') return '图像理解';
  if (c === 'text_prompt' || c === 'text_generation' || c === 'prompt') return '文本与提示词';
  if (c === 'video_generation' || c === 'video') return '生视频';
  if (c === 'general' || c === 'common' || c === '通用类') return '平台工具';
  return '平台工具';
};

const isGenericCategory = (category: string | undefined | null): boolean => {
  const c = String(category || '').trim().toLowerCase();
  return !c || c === '通用类' || c === '通用' || c === 'general' || c === 'common' || c === 'platform_tools';
};

const getWorkflowPresentation = (wf: EvalWorkflowVersion | null | undefined) =>
  (wf?.presentation && typeof wf.presentation === 'object' ? wf.presentation : null) as EvalWorkflowVersion['presentation'];

const getWorkflowUsage = (wf: EvalWorkflowVersion | null | undefined) =>
  (wf?.usage && typeof wf.usage === 'object' ? wf.usage : null) as EvalWorkflowVersion['usage'];

const getWorkflowGovernance = (wf: EvalWorkflowVersion | null | undefined) =>
  (wf?.governance && typeof wf.governance === 'object' ? wf.governance : null) as EvalWorkflowVersion['governance'];

const getWorkflowRoutingGovernance = (wf: EvalWorkflowVersion | null | undefined) =>
  (wf?.routingGovernance && typeof wf.routingGovernance === 'object'
    ? wf.routingGovernance
    : null) as EvalWorkflowVersion['routingGovernance'];

const getWorkflowEvalExecution = (wf: EvalWorkflowVersion | null | undefined): Record<string, unknown> | null => {
  const metadata = wf?.metadata;
  const execution = metadata && typeof metadata === 'object' ? (metadata as any).eval_execution : null;
  return execution && typeof execution === 'object' ? execution : null;
};

const isBusinessApiWorkflow = (wf: EvalWorkflowVersion | null | undefined): boolean => {
  const routing = getWorkflowRoutingGovernance(wf);
  const execution = getWorkflowEvalExecution(wf);
  return routing?.entryMode === 'business_api' || execution?.mode === 'business_run';
};

const inferWorkflowCategory = (
  wf: Pick<EvalWorkflowVersion, 'category' | 'presentation' | 'name' | 'workflow_id' | 'notes'> | null | undefined,
): string => {
  const presentation = getWorkflowPresentation(wf as EvalWorkflowVersion);
  const rawCategory = String(presentation?.categoryLabel || wf?.category || '').trim();
  const normalized = normalizeCategory(rawCategory);
  if (!isGenericCategory(rawCategory) && normalized !== '平台工具') return normalized;

  const text = [
    rawCategory,
    wf?.name,
    wf?.workflow_id,
    wf?.notes,
    presentation?.operationLabel,
    presentation?.variantLabel,
    presentation?.usageHint,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (/花纹|印花|pattern|yinhua/.test(text)) return '花纹提取';
  if (/裂变|fission|variation|softstyle|e7|flux-strong/.test(text)) return '图裂变';
  if (/扩图|延伸|outpaint|extend|extension|klein/.test(text)) return '扩图';
  if (/连续|四方|两方|seamless|lianxu/.test(text)) return '连续图';
  if (/抠图|抠像|去背|背景移除|background|cutout|matting|remove-bg|kouxiang|koutu/.test(text)) return '抠图';
  if (/融合|合成|多图|fusion|compose|composition|merge/.test(text)) return '图像融合';
  if (/放大|高清|dpi|清晰|增强|upscale|enhance|resize|denoise/.test(text)) return '图像增强';
  if (/vl|视觉|理解|识别|描述|标签|describe|vision|analy/.test(text)) return '图像理解';
  if (/文字|文本|提示词|prompt|text/.test(text)) return '文本与提示词';
  if (/视频|video|seedance|sora/.test(text)) return '生视频';
  return normalized;
};

const getWorkflowCategory = (wf: Pick<EvalWorkflowVersion, 'category' | 'presentation' | 'name' | 'workflow_id' | 'notes'> | null | undefined): string => {
  return inferWorkflowCategory(wf);
};

const getWorkflowSortOrder = (wf: EvalWorkflowVersion | null | undefined): number => {
  const raw = Number(getWorkflowPresentation(wf)?.sortOrder);
  return Number.isFinite(raw) ? raw : Number.MAX_SAFE_INTEGER;
};

const getWorkflowUsageHint = (wf: EvalWorkflowVersion | null | undefined): string =>
  String(getWorkflowPresentation(wf)?.usageHint || wf?.notes || '暂无说明，点击进入查看参数与结果。').trim();

const getWorkflowOperationLabel = (wf: EvalWorkflowVersion | null | undefined): string =>
  String(getWorkflowPresentation(wf)?.operationLabel || '').trim();

const getWorkflowVariantLabel = (wf: EvalWorkflowVersion | null | undefined): string =>
  String(getWorkflowPresentation(wf)?.variantLabel || '').trim();

const getWorkflowShortId = (wf: EvalWorkflowVersion | null | undefined): string => {
  const id = String(wf?.workflow_id || '').trim();
  if (!id) return '-';
  return id.length > 8 ? id.slice(-8) : id;
};

const getWorkflowGovernanceRank = (wf: EvalWorkflowVersion | null | undefined): number => {
  const raw = Number(getWorkflowGovernance(wf)?.rank);
  if (Number.isFinite(raw)) return raw;
  const role = String(getWorkflowGovernance(wf)?.role || '').toLowerCase();
  if (role === 'production') return 10;
  if (role === 'candidate') return 30;
  if (role === 'auxiliary') return 70;
  if (role === 'legacy') return 90;
  if (role === 'disabled') return 100;
  return 50;
};

const getWorkflowGovernanceTheme = (
  role?: string | null,
): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
  const value = String(role || '').toLowerCase();
  if (value === 'production') return 'success';
  if (value === 'candidate') return 'primary';
  if (value === 'legacy') return 'warning';
  if (value === 'auxiliary') return 'default';
  if (value === 'disabled') return 'danger';
  return 'default';
};

const getWorkflowRoutingGovernanceTheme = (
  status?: string | null,
): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
  const value = String(status || '').toLowerCase();
  if (value === 'aligned') return 'success';
  if (value === 'internal_only') return 'default';
  if (value.includes('vendor')) return 'primary';
  if (value.includes('task')) return 'warning';
  return 'default';
};

const isWorkflowBatchEnabled = (wf: EvalWorkflowVersion | null | undefined): boolean => {
  const usage = getWorkflowUsage(wf);
  if (typeof usage?.batchEnabled === 'boolean') return usage.batchEnabled;
  const presentation = getWorkflowPresentation(wf);
  if (typeof presentation?.supportsBatch === 'boolean') return presentation.supportsBatch;
  return false;
};

const categoryVisualMeta: Record<string, { icon: ReactNode; accent: string; summary: string; cover: string }> = {
  花纹提取: {
    icon: <ScanIcon size="18px" />,
    accent: '#0ea5e9',
    summary: '偏向纹理细节保留，重点验证边缘与纹路还原。',
    cover: 'linear-gradient(120deg, rgba(14,165,233,0.18), rgba(2,132,199,0.08))',
  },
  图裂变: {
    icon: <ChartBubbleIcon size="18px" />,
    accent: '#f59e0b',
    summary: '强调多样性与可控变体，避免主体语义漂移。',
    cover: 'linear-gradient(120deg, rgba(245,158,11,0.18), rgba(217,119,6,0.08))',
  },
  扩图: {
    icon: <ImageEditIcon size="18px" />,
    accent: '#3b82f6',
    summary: '关注主体连续性、边界自然过渡与风格一致性。',
    cover: 'linear-gradient(120deg, rgba(59,130,246,0.18), rgba(30,64,175,0.08))',
  },
  连续图: {
    icon: <LayersIcon size="18px" />,
    accent: '#6366f1',
    summary: '重点看拼接缝是否消失、图案周期是否稳定。',
    cover: 'linear-gradient(120deg, rgba(99,102,241,0.18), rgba(79,70,229,0.08))',
  },
  抠图: {
    icon: <ScanIcon size="18px" />,
    accent: '#0f766e',
    summary: '验证背景去除、边缘干净度和主体保留。',
    cover: 'linear-gradient(120deg, rgba(15,118,110,0.18), rgba(20,184,166,0.08))',
  },
  图像融合: {
    icon: <LayersIcon size="18px" />,
    accent: '#7c3aed',
    summary: '关注多图主体关系、材质融合和构图稳定性。',
    cover: 'linear-gradient(120deg, rgba(124,58,237,0.18), rgba(109,40,217,0.08))',
  },
  图像增强: {
    icon: <AiImageIcon size="18px" />,
    accent: '#10b981',
    summary: '检查放大、DPI、清晰度和尺寸修复是否稳定。',
    cover: 'linear-gradient(120deg, rgba(16,185,129,0.18), rgba(5,150,105,0.08))',
  },
  图像理解: {
    icon: <ScanIcon size="18px" />,
    accent: '#0891b2',
    summary: '验证 VL 模型对主体、风格、文字和风险的分析结果。',
    cover: 'linear-gradient(120deg, rgba(8,145,178,0.18), rgba(14,116,144,0.08))',
  },
  文本与提示词: {
    icon: <ChartBubbleIcon size="18px" />,
    accent: '#c2410c',
    summary: '验证文字增强、提示词优化和描述生成质量。',
    cover: 'linear-gradient(120deg, rgba(194,65,12,0.18), rgba(154,52,18,0.08))',
  },
  生视频: {
    icon: <AiImageIcon size="18px" />,
    accent: '#be123c',
    summary: '验证图生视频、文生视频和短视频结果链路。',
    cover: 'linear-gradient(120deg, rgba(190,18,60,0.18), rgba(159,18,57,0.08))',
  },
  平台工具: {
    icon: <TaskIcon size="18px" />,
    accent: '#64748b',
    summary: '内部自检、任务追踪、队列、模型和 LoRA 管理入口。',
    cover: 'linear-gradient(120deg, rgba(100,116,139,0.18), rgba(71,85,105,0.08))',
  },
};

const workflowAccentPalette = ['#2563eb', '#0f766e', '#c2410c', '#7c3aed', '#be123c', '#047857', '#b45309', '#0369a1'];

const hashText = (text: string): number => {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  }
  return hash;
};

const getWorkflowAccent = (wf: EvalWorkflowVersion): string => {
  const seed = `${wf.workflow_id || wf.id || wf.name}`;
  return workflowAccentPalette[hashText(seed) % workflowAccentPalette.length];
};

const getCategoryVisual = (category: string | undefined | null) => {
  const normalized = normalizeCategory(category);
  return categoryVisualMeta[normalized] || categoryVisualMeta['平台工具'];
};

const getCategoryNavIcon = (category: string): ReactNode => getCategoryVisual(category).icon;

const cleanWorkflowDisplayText = (value: string): string =>
  String(value || '')
    .replace(/新版/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/[·|｜:：/-]\s*$/g, '')
    .trim();

const hasWorkflowNewVersionFlag = (wf: EvalWorkflowVersion | null | undefined): boolean => {
  const metadata = wf?.metadata && typeof wf.metadata === 'object' ? wf.metadata : {};
  const presentation = getWorkflowPresentation(wf);
  const badges = Array.isArray(presentation?.badges) ? presentation.badges : [];
  return Boolean(
    (metadata as any).isNewVersion ||
      (metadata as any).is_new_version ||
      badges.includes('新版') ||
      (metadata as any).badge === '新版',
  );
};

const getWorkflowBadges = (wf: EvalWorkflowVersion): string[] => {
  const presentation = getWorkflowPresentation(wf);
  const metadata = wf.metadata && typeof wf.metadata === 'object' ? wf.metadata : {};
  const role = String(getWorkflowGovernance(wf)?.role || '').trim().toLowerCase();
  const rawBadges = [
    ...(Array.isArray(presentation?.badges) ? presentation.badges : []),
    ...((metadata as any).badge ? [(metadata as any).badge] : []),
    ...(Array.isArray((metadata as any).badges) ? (metadata as any).badges : []),
  ];
  if (role === 'candidate' && hasWorkflowNewVersionFlag(wf) && !rawBadges.includes('待内测')) {
    rawBadges.unshift('待内测');
  }
  if (hasWorkflowNewVersionFlag(wf) && !rawBadges.includes('新版')) {
    rawBadges.unshift('新版');
  }
  const seen = new Set<string>();
  return rawBadges
    .map((item) => String(item || '').trim())
    .filter((item) => {
      if (!item || seen.has(item)) return false;
      seen.add(item);
      return true;
    })
    .slice(0, 4);
};

const getWorkflowBadgeTheme = (badge: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
  if (badge === '新版') return 'success';
  if (badge === '待内测' || badge === '灰度验证') return 'warning';
  if (badge === '原生业务接口') return 'primary';
  if (badge === '原子组件') return 'default';
  return 'primary';
};

const isWorkflowNewVersion = (wf: EvalWorkflowVersion | null | undefined): boolean => {
  return hasWorkflowNewVersionFlag(wf);
};

const isWorkflowInternalTesting = (wf: EvalWorkflowVersion | null | undefined): boolean => {
  const role = String(getWorkflowGovernance(wf)?.role || '').trim().toLowerCase();
  return role === 'candidate' && isWorkflowNewVersion(wf);
};

const getWorkflowCornerBadge = (wf: EvalWorkflowVersion | null | undefined): string => {
  if (isWorkflowInternalTesting(wf)) return '待内测';
  if (isWorkflowNewVersion(wf)) return '新版';
  return '';
};

const getWorkflowTestingSortRank = (wf: EvalWorkflowVersion | null | undefined): number => {
  const role = String(getWorkflowGovernance(wf)?.role || '').trim().toLowerCase();
  if (isWorkflowInternalTesting(wf)) return 0;
  if (isWorkflowNewVersion(wf)) return 5;
  if (role === 'production') return 20;
  if (role === 'candidate') return 30;
  if (role === 'auxiliary') return 70;
  if (role === 'legacy') return 90;
  if (role === 'disabled') return 100;
  return 50;
};

const getSchemaFields = (schema: Record<string, unknown> | null | undefined): SchemaField[] => {
  const fields = schema?.fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter((field): field is SchemaField => Boolean(field && typeof field === 'object' && 'name' in field));
};

const getWorkflowCardTitle = (wf: EvalWorkflowVersion): string => {
  const operationLabel = getWorkflowOperationLabel(wf);
  const variantLabel = getWorkflowVariantLabel(wf);
  if (variantLabel) return cleanWorkflowDisplayText(variantLabel);
  const category = getWorkflowCategory(wf);
  const rawName = String(wf.name || wf.workflow_id || '未命名功能').trim();
  const parts = rawName
    .split(/[·|｜:：/-]/)
    .map((item) => item.trim())
    .filter(Boolean);
  const noisy = new Set([category, operationLabel, '图裂变', '裂变', '图延伸', '扩图', '连续图', '抠图', '图像增强', 'ComfyUI', '商业模型']);
  const distinctPart = parts.find((item) => !noisy.has(item));
  if (distinctPart) return cleanWorkflowDisplayText(distinctPart);
  if (operationLabel && rawName !== operationLabel) {
    return cleanWorkflowDisplayText(rawName.replace(operationLabel, '').replace(/[·|｜:：/-]/g, ' ')) || operationLabel;
  }
  return cleanWorkflowDisplayText(operationLabel || rawName) || `工作流 ${getWorkflowShortId(wf)}`;
};

const getWorkflowOperationTitle = (wf: EvalWorkflowVersion): string =>
  getWorkflowOperationLabel(wf) || getWorkflowCategory(wf);

const getWorkflowCardSubtitle = (wf: EvalWorkflowVersion): string => {
  const usageHint = getWorkflowUsageHint(wf);
  const title = getWorkflowCardTitle(wf);
  const cleaned = usageHint.replace(title, '').replace(getWorkflowOperationTitle(wf), '').replace(/^[\s，。,:：·|-]+/, '').trim();
  return cleaned || usageHint;
};

const getWorkflowStatusLabel = (status: string | undefined | null): string => {
  const value = String(status || '').toLowerCase();
  if (value === 'active') return '可用';
  if (value === 'draft') return '草稿';
  if (value === 'deprecated') return '已旧版';
  if (value === 'disabled') return '已停用';
  return value || '未知';
};

const getWorkflowVersionLabel = (wf: EvalWorkflowVersion | null | undefined): string => {
  const version = String(wf?.version || '').trim();
  const workflowId = String(wf?.workflow_id || '').trim();
  const text = `${workflowId} ${version}`.toLowerCase();
  if (workflowId === 'business_fission_gpt_image2_vl_v1' || text.includes('gpt-image2-vl')) return '商业模型 VL 控制版';
  if (workflowId === 'business_fission_comfyui_vl_control_v1' || text.includes('comfyui-vl-control')) return 'ComfyUI VL 控制版';
  if (workflowId === 'ability_fission_generated_image_evaluate_v1' || text.includes('generated-image-eval')) return '裂变质量评估';
  if (version === '2026-04-23') return '2026/4/23';
  return cleanWorkflowDisplayText(version || 'v1') || 'v1';
};

const getWorkflowResultModeLabel = (mode: string): string => {
  const value = String(mode || '').trim().toLowerCase();
  if (value === 'callback_image') return '图片回填';
  if (value === 'image_url') return '图片 URL';
  if (value === 'image') return '图片';
  if (value === 'video') return '视频';
  if (value === 'structured_json') return '结构化结果';
  if (value === 'text') return '文字';
  if (value === 'unknown') return '';
  return mode;
};

const getWorkflowInputSummary = (wf: EvalWorkflowVersion): string => {
  const text = getSchemaFields(wf.parameters_schema)
    .map((field) => `${field.name} ${field.label || ''} ${field.description || ''}`)
    .join(' ')
    .toLowerCase();
  const parts: string[] = [];
  if (/mask|蒙版/.test(text)) parts.push('蒙版');
  if (/image_urls|input_urls|多图|multi/.test(text)) parts.push('多图');
  else if (/image|url|图片|原图/.test(text)) parts.push('原图');
  if (/prompt|desc|text|提示词|描述/.test(text)) parts.push('提示词');
  if (/width|height|size|aspect|ratio|宽|高|尺寸|比例/.test(text)) parts.push('尺寸');
  if (/重绘|repaint|bili|denoise|noise|幅度|噪点/.test(text)) parts.push('重绘幅度');
  else if (/similarity|相似度/.test(text)) parts.push('相似度');
  if (/count|batch|数量|批量/.test(text)) parts.push('数量');
  return parts.slice(0, 4).join(' + ') || '按表单参数';
};

const getWorkflowOutputSummary = (wf: EvalWorkflowVersion): string => {
  const resultMode = String(getWorkflowPresentation(wf)?.resultMode || '').trim();
  const resultModeLabel = getWorkflowResultModeLabel(resultMode);
  if (resultModeLabel) return resultModeLabel;
  const text = getSchemaFields(wf.output_schema)
    .map((field) => `${field.name} ${field.label || ''} ${field.description || ''}`)
    .join(' ')
    .toLowerCase();
  if (/video|视频/.test(text)) return '视频';
  if (/text|文本|prompt/.test(text)) return '文本';
  if (/image|url|图片|图/.test(text)) return '图片';
  return '图片/任务结果';
};

const getWorkflowReleaseDate = (wf: EvalWorkflowVersion): string => {
  const metadata = wf.metadata && typeof wf.metadata === 'object' ? wf.metadata : {};
  const raw =
    getWorkflowPresentation(wf)?.['releaseTime' as keyof NonNullable<EvalWorkflowVersion['presentation']>] ||
    metadata.releaseTime ||
    metadata.release_time ||
    metadata.publishedAt ||
    metadata.published_at ||
    wf.created_at;
  return fmtTime(String(raw || '')).split(' ')[0] || '-';
};

const getWorkflowRuntimeHealth = (
  metric?: WorkflowMetric,
): {
  label: string;
  detail: string;
  theme: 'default' | 'primary' | 'success' | 'warning' | 'danger';
  focus: ToolHistoryFocus;
  cta: string;
} => {
  const recentHours = Math.max(1, Number(metric?.recentHours || 72));
  const recentRunCount = Number(metric?.recentRunCount || 0);
  const recentSuccessCount = Number(metric?.recentSuccessCount || 0);
  const recentFailureCount = Number(metric?.recentFailureCount || 0);
  const recentRunningCount = Number(metric?.recentRunningCount || 0);
  const recentNoOutputCount = Number(metric?.recentNoOutputCount || 0);
  if (!metric || recentRunCount <= 0) {
    return { label: '暂无运行', detail: `近 ${recentHours} 小时没有评测记录`, theme: 'default', focus: 'all', cta: '看历史记录' };
  }
  if (recentNoOutputCount > 0) {
    return {
      label: '生成未回填',
      detail: `近 ${recentHours} 小时 ${recentNoOutputCount} 次成功但没有结果图`,
      theme: 'warning',
      focus: 'no_output',
      cta: '看未回填',
    };
  }
  if (recentFailureCount > 0 && recentSuccessCount <= 0) {
    return {
      label: '最近失败',
      detail: `近 ${recentHours} 小时失败 ${recentFailureCount} 次，需要先排查`,
      theme: 'danger',
      focus: 'failed',
      cta: '看异常记录',
    };
  }
  if (recentFailureCount > 0) {
    return {
      label: '有失败样本',
      detail: `近 ${recentHours} 小时成功 ${recentSuccessCount} 次，失败 ${recentFailureCount} 次`,
      theme: 'warning',
      focus: 'failed',
      cta: '看失败样本',
    };
  }
  if (recentRunningCount > 0 && recentSuccessCount <= 0) {
    return {
      label: '运行中',
      detail: `近 ${recentHours} 小时还有 ${recentRunningCount} 次未完成`,
      theme: 'primary',
      focus: 'running',
      cta: '看执行中',
    };
  }
  return {
    label: '最近可用',
    detail: `近 ${recentHours} 小时成功 ${recentSuccessCount} 次`,
    theme: 'success',
    focus: 'succeeded',
    cta: '看成功记录',
  };
};

const getWorkflowRecentOutputLabel = (metric?: WorkflowMetric): string => {
  const counts = metric?.recentOutputKindCounts || {};
  const entries = [
    ['image', '图片'],
    ['video', '视频'],
    ['text', '文字/VL'],
    ['structured', '结构化'],
    ['none', '未回填'],
  ] as const;
  const visible = entries
    .map(([key, label]) => ({ label, count: Number(counts[key] || 0) }))
    .filter((item) => item.count > 0);
  if (!visible.length) return '';
  return `近期输出：${visible.map((item) => `${item.label}${item.count}`).join(' / ')}`;
};

const getHistoryFocusMeta = (
  focus: ToolHistoryFocus,
): { label: string; message: string; theme: 'info' | 'success' | 'warning' | 'error' } | null => {
  if (focus === 'failed') return { label: '失败记录', message: '已定位到最近失败任务，优先查看错误码、调试链接和中台任务 ID。', theme: 'error' };
  if (focus === 'no_output') return { label: '生成未回填', message: '已定位到状态成功但没有图片/结构化结果的任务，优先排查回填链路。', theme: 'warning' };
  if (focus === 'running') return { label: '执行中', message: '已定位到正在排队或运行的任务，用于观察是否卡住。', theme: 'info' };
  if (focus === 'succeeded') return { label: '成功记录', message: '已定位到近期成功任务，可直接对照输出质量和参数。', theme: 'success' };
  return null;
};

const dedupeWorkflowVersionsForDisplay = (rows: EvalWorkflowVersion[]): EvalWorkflowVersion[] => {
  const seen = new Set<string>();
  const next: EvalWorkflowVersion[] = [];
  for (const row of rows) {
    const key = `${String(row.workflow_id || '').trim()}::${String(row.category || '').trim()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    next.push(row);
  }
  if (next.length !== rows.length) {
    console.warn('[eval-web] duplicate workflow versions hidden in display layer', {
      raw: rows.length,
      display: next.length,
    });
  }
  return next;
};

const normalizeRemoteLoadError = (error: unknown): RemoteLoadError => {
  if (error instanceof ApiRequestError) {
    return {
      kind: error.kind,
      status: error.status,
      message: String(error.message || '请求失败'),
      rawBody: error.rawBody,
    };
  }
  return {
    kind: 'unknown',
    message: String((error as any)?.message || error || '请求失败'),
  };
};

const getListLoadHelp = (
  error: RemoteLoadError | null,
  scope: 'public' | 'admin',
): { title: string; description: string } => {
  const noun = scope === 'admin' ? '维护功能列表' : '测评功能列表';
  if (!error) {
    return {
      title: `${noun}加载失败`,
      description: '功能列表接口没有正常返回，请先重试；如果持续失败，通知中台排查后端日志。',
    };
  }
  if (error.kind === 'timeout') {
    return {
      title: `${noun}加载失败`,
      description: '请求超时，请检查网络或稍后重试；如果持续超时，通知中台排查服务状态。',
    };
  }
  if (error.kind === 'network') {
    return {
      title: `${noun}加载失败`,
      description: '当前无法连接到服务，请检查网络、网关或服务是否可达，然后重试。',
    };
  }
  if (typeof error.status === 'number' && error.status >= 500) {
    return {
      title: `${noun}加载失败`,
      description: '当前不是输入问题，而是功能列表接口没有正常返回。请先重试；如果持续失败，通知中台排查后端日志。',
    };
  }
  if (typeof error.status === 'number' && error.status >= 400) {
    return {
      title: `${noun}加载失败`,
      description: '当前请求被拒绝，请检查权限、Token 或服务配置，然后重试。',
    };
  }
  return {
    title: `${noun}加载失败`,
    description: '服务返回异常，请刷新或联系维护者。',
  };
};

function WorkflowListErrorState({
  scope,
  error,
  onRetry,
}: {
  scope: 'public' | 'admin';
  error: RemoteLoadError | null;
  onRetry: () => void;
}) {
  const copy = getListLoadHelp(error, scope);
  return (
    <Card bordered>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Alert theme="error" message={copy.title} />
        <Typography.Text theme="secondary">{copy.description}</Typography.Text>
        <Space>
          <Button theme="primary" onClick={onRetry}>
            重试
          </Button>
        </Space>
        {error ? (
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--td-text-color-secondary)' }}>查看调试信息</summary>
            <pre
              style={{
                marginTop: 12,
                maxHeight: 240,
                overflow: 'auto',
                border: '1px solid var(--td-border-level-1-color)',
                background: 'var(--td-bg-color-secondarycontainer)',
                borderRadius: 8,
                padding: 12,
                fontFamily: 'monospace',
                fontSize: 12,
                whiteSpace: 'pre-wrap',
              }}
            >
              {JSON.stringify(
                {
                  kind: error.kind,
                  status: error.status,
                  message: error.message,
                  rawBody: error.rawBody,
                },
                null,
                2,
              )}
            </pre>
          </details>
        ) : null}
      </Space>
    </Card>
  );
}

const normalizeFieldOptions = (field?: SchemaField | null, opts?: { allowEmpty?: boolean }): LoraOption[] => {
  const allowEmpty = Boolean(opts?.allowEmpty);
  const options = Array.isArray((field as any)?.options) ? (((field as any).options as any[]) || []) : [];
  const parsed = options
    .map((opt) => {
      if (typeof opt === 'string') {
        const value = opt.trim();
        if (!value && !allowEmpty) return null;
        return { label: value || '留空（跟随原图）', value };
      }
      if (opt && typeof opt === 'object') {
        const raw = (opt as any).value;
        const value = raw == null ? '' : String(raw).trim();
        const labelRaw = (opt as any).label;
        const label = String(labelRaw ?? value).trim();
        if (!value && !allowEmpty) return null;
        return { label: label || (value || '留空（跟随原图）'), value };
      }
      return null;
    })
    .filter((item): item is LoraOption => Boolean(item));
  const uniq = new Map<string, LoraOption>();
  for (const item of parsed) {
    if (!uniq.has(item.value)) uniq.set(item.value, item);
  }
  return Array.from(uniq.values());
};

const resolveModelAwareField = (
  field: SchemaField,
  modelValue: string,
): {
  optionsOverride?: LoraOption[];
  disabled: boolean;
  description: string;
} => {
  const descriptionRaw = String((field as any)?.description || '').trim();
  const supportedModels = Array.isArray((field as any)?.supportedModels)
    ? ((field as any).supportedModels as any[])
        .map((item) => String(item ?? '').trim())
        .filter((item) => item.length > 0)
    : [];
  const disabledByModel = supportedModels.length > 0 && modelValue.length > 0 && !supportedModels.includes(modelValue);

  let optionsOverride: LoraOption[] | undefined;
  const modelOptions = (field as any)?.modelOptions;
  if (modelValue && modelOptions && typeof modelOptions === 'object') {
    const selected = (modelOptions as Record<string, unknown>)[modelValue] ?? (modelOptions as Record<string, unknown>).default;
    if (Array.isArray(selected)) {
      const baseOptions = normalizeFieldOptions(field, { allowEmpty: true });
      const baseMap = new Map(baseOptions.map((opt) => [opt.value, opt.label]));
      const mapped: LoraOption[] = [];
      for (const raw of selected) {
        const value = typeof raw === 'string' ? raw.trim() : String((raw as any)?.value ?? '').trim();
        const labelFromRaw =
          typeof raw === 'string' ? '' : String((raw as any)?.label ?? '').trim();
        const label = labelFromRaw || baseMap.get(value) || (value || '留空（默认）');
        if (!mapped.some((item) => item.value === value)) {
          mapped.push({ label, value });
        }
      }
      optionsOverride = mapped;
    }
  }

  let description = descriptionRaw;
  if (disabledByModel) {
    const hint = '当前模型不支持该参数，提交时会自动忽略。';
    description = description ? `${description} ${hint}` : hint;
  }
  return {
    optionsOverride,
    disabled: disabledByModel,
    description,
  };
};

const buildWorkflowDefaultParams = (wf: EvalWorkflowVersion): Record<string, string> => {
  const defaults: Record<string, string> = {};
  for (const f of getFields(wf)) {
    if (f.name === 'url' || f.name === 'Url') continue;
    const options = normalizeFieldOptions(f);
    if (typeof (f as any).defaultValue === 'string') {
      defaults[f.name] = String((f as any).defaultValue);
    } else if (options.length > 0) {
      defaults[f.name] = options[0].value;
    } else {
      defaults[f.name] = '';
    }
  }
  return defaults;
};

const getFields = (wf: EvalWorkflowVersion | null): SchemaField[] => {
  const schema = wf?.parameters_schema as any;
  const fields = schema?.fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter((f: any) => f && typeof f === 'object' && typeof f.name === 'string');
};

const formatDuration = (ms?: number | null) => {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

const billingUnitLabel = (value?: string | null) => {
  if (value === 'image' || value === 'per_image') return '按图片';
  if (value === 'video' || value === 'per_video') return '按视频';
  if (value === 'run' || value === 'task' || value === 'per_run') return '按任务';
  if (value === 'token' || value === 'tokens') return '按文字量';
  return value || '未标单位';
};

const formatEvalRunCost = (run: Pick<EvalRun, 'cost_amount' | 'currency' | 'billing_unit' | 'unit_price'>) => {
  const amount = Number(run.cost_amount ?? 0);
  const unitPrice = Number(run.unit_price ?? 0);
  const currency = String(run.currency || '').trim() || '未标币种';
  if (Number.isFinite(amount) && amount > 0) {
    return `${currency} ${amount.toFixed(4)} · ${billingUnitLabel(run.billing_unit)}`;
  }
  if (Number.isFinite(unitPrice) && unitPrice > 0) {
    return `已配置单价 ${currency} ${unitPrice.toFixed(4)} · 本次成本待回填`;
  }
  return '成本未记录';
};

const fmtTime = (iso: string) => {
  try {
    const raw = String(iso || '').trim();
    if (!raw) return '—';
    // If backend returns a naive ISO string (no timezone), treat it as UTC.
    const hasTz = /Z$|[+-]\\d{2}:?\\d{2}$/.test(raw);
    const normalized = hasTz ? raw : `${raw}Z`;
    // Force CN business timezone regardless of server/browser settings.
    return new Date(normalized).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  } catch {
    return iso;
  }
};

const formatJsonPreview = (value: unknown, maxLen = 1200): string => {
  try {
    if (value == null) return '';
    // Coze "JSON output" is often a JSON string.
    if (typeof value === 'string') {
      const s = value.trim();
      if (!s) return '';
      if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
        try {
          const parsed = JSON.parse(s);
          const pretty = JSON.stringify(parsed, null, 2);
          return pretty.length > maxLen ? `${pretty.slice(0, maxLen)}…` : pretty;
        } catch {
          return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
        }
      }
      return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
    }
    const pretty = JSON.stringify(value, null, 2);
    return pretty.length > maxLen ? `${pretty.slice(0, maxLen)}…` : pretty;
  } catch {
    return String(value || '');
  }
};

const extractOutputField = (value: unknown, key: string): string => {
  try {
    if (value == null) return '';
    if (typeof value === 'string') {
      const s = value.trim();
      if (!s) return '';
      if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
        try {
          const parsed = JSON.parse(s);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            const found = (parsed as Record<string, unknown>)[key];
            return found == null ? '' : String(found);
          }
        } catch {
          return '';
        }
      }
      return '';
    }
    if (typeof value === 'object' && !Array.isArray(value)) {
      const found = (value as Record<string, unknown>)[key];
      return found == null ? '' : String(found);
    }
  } catch {
    return '';
  }
  return '';
};

const formatEditorToolLabel = (tool: EditorTool): string => {
  switch (tool) {
    case 'point':
      return '点选';
    case 'rect':
      return '矩形框选';
    case 'circle':
      return '圆形框选';
    case 'freehand':
      return '手绘';
    default:
      return '标注';
  }
};

const formatLoraBatchStatusLabel = (status: LoraBatchItemStatus): string => {
  switch (status) {
    case 'pending':
      return '待处理';
    case 'uploading':
      return '上传中';
    case 'submitting':
      return '提交中';
    case 'submitted':
      return '已提交';
    case 'failed':
      return '失败';
    default:
      return status;
  }
};

const formatLoraBatchRunStatusLabel = (status?: LoraBatchRunStatus, outputCount?: number): string => {
  if (!status) return '等待查询';
  switch (status) {
    case 'queued':
      return '排队中';
    case 'running':
      return '生成中';
    case 'succeeded':
      return (outputCount || 0) > 0 ? '已完成（有图）' : '已完成（无图）';
    case 'failed':
      return '生成失败';
    default:
      return '状态未知';
  }
};

const formatBatchSessionStatusLabel = (status?: string | null): string => {
  const value = String(status || '').toLowerCase();
  switch (value) {
    case 'draft':
      return '草稿';
    case 'uploading':
      return '上传中';
    case 'ready':
      return '待提交';
    case 'submitting':
      return '提交中';
    case 'running':
      return '执行中';
    case 'succeeded':
      return '已完成';
    case 'failed':
      return '已失败';
    case 'stopped':
      return '已停止';
    default:
      return value || '未知';
  }
};

const isEmptyDraftBatchSession = (item: LoraBatchSession): boolean => {
  const status = String(item.status || '').toLowerCase();
  if (status !== 'draft') return false;
  const planned = Number(item.expectedTotal || item.total || 0);
  const submitted = Number(item.submittedCount || 0);
  const completed = Number(item.completed || 0);
  return planned <= 0 && submitted <= 0 && completed <= 0;
};

const formatBatchSessionStatusDisplay = (item: LoraBatchSession): string => {
  const status = String(item.status || '').toLowerCase();
  if (status !== 'failed') return formatBatchSessionStatusLabel(item.status);
  const uploadFailed = Math.max(0, Number(item.uploadFailedCount || 0));
  const runFailed = Math.max(0, Number(item.failed || 0));
  if (runFailed <= 0 && uploadFailed > 0) return '已完成（含上传失败）';
  if (runFailed > 0) return '已完成（部分失败）';
  return '已失败';
};

const formatLoraReviewGroupStatusLabel = (status?: string | null): string => {
  const value = String(status || '').toLowerCase();
  if (value === 'has_output') return '已有结果';
  if (value === 'no_output') return '暂无结果';
  if (value === 'failed') return '执行失败';
  return value || '未知';
};

const formatLoraReviewVerdictLabel = (verdict: LoraBatchReviewVerdict): string => {
  switch (verdict) {
    case 'satisfied':
      return '满意';
    case 'unsatisfied':
      return '不满意';
    default:
      return '未标注';
  }
};

const buildEditorPrompt = (args: {
  rawPrompt: string;
  marks: EditorMark[];
  refUrls: string[];
  mainUrl?: string;
  imageSize: { width: number; height: number };
}): string => {
  const { rawPrompt, marks, refUrls, mainUrl, imageSize } = args;
  const width = Number(imageSize.width || 0);
  const height = Number(imageSize.height || 0);

  const prefix = [
    '你是专业的图像编辑助手。',
    '目标：在保持主图整体风格一致的前提下，仅根据标注与参考图完成指定修改。',
    '注意：主图=图1，参考图从图2开始编号。',
  ].join('\n');
  const outputRules = [
    '输出只需返回最终图片，不要输出解释性文字。',
    '未标注区域保持不变，禁止引入无关元素。',
    '如未明确指定画幅/分辨率，保持与主图一致。',
    '参考图只用于风格/纹理/形象参考，不要直接拼贴。',
    '严格遵循图像顺序规范（图1主图、图2/图3为参考图）。',
    '所有编辑动作只作用于图1；图2/图3仅提供参考，不可反向编辑。',
    '若用户写“把主图/图1 的A换成图N”，含义是“在图1中替换A为图N特征”，禁止改写图N本身。',
  ].join('\n');

  const fmt = (v: number, total: number) => {
    const rounded = Math.round(v);
    if (total > 0) {
      return `${rounded}(${(v / total).toFixed(4)})`;
    }
    return String(rounded);
  };

  const describeMark = (mark: EditorMark, index: number): string => {
    const label = mark.name || `标注${index + 1}`;
    const prefix = `@${label}`;
    const pts = mark.points || [];
    if (mark.type === 'point' && pts[0]) {
      const p = pts[0];
      return `${prefix}（点）：x=${fmt(p.x, width)}, y=${fmt(p.y, height)}`;
    }
    if (mark.type === 'rect' && pts.length >= 2) {
      const a = pts[0];
      const b = pts[1];
      const left = Math.min(a.x, b.x);
      const top = Math.min(a.y, b.y);
      const w = Math.abs(a.x - b.x);
      const h = Math.abs(a.y - b.y);
      return `${prefix}（矩形）：left=${fmt(left, width)}, top=${fmt(top, height)}, width=${fmt(w, width)}, height=${fmt(h, height)}`;
    }
    if (mark.type === 'circle' && pts.length >= 2) {
      const c = pts[0];
      const edge = pts[1];
      const r = Math.sqrt((c.x - edge.x) ** 2 + (c.y - edge.y) ** 2);
      return `${prefix}（圆形）：cx=${fmt(c.x, width)}, cy=${fmt(c.y, height)}, r=${fmt(r, Math.max(width, height))}`;
    }
    if (mark.type === 'freehand' && pts.length > 0) {
      let minX = pts[0].x;
      let maxX = pts[0].x;
      let minY = pts[0].y;
      let maxY = pts[0].y;
      for (const p of pts) {
        minX = Math.min(minX, p.x);
        maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y);
        maxY = Math.max(maxY, p.y);
      }
      const sample: EditorPoint[] = [];
      const step = Math.max(1, Math.floor(pts.length / 12));
      for (let i = 0; i < pts.length; i += step) {
        sample.push(pts[i]);
      }
      if (pts.length > 0 && sample[sample.length - 1] !== pts[pts.length - 1]) {
        sample.push(pts[pts.length - 1]);
      }
      const sampleStr = sample
        .map((p) => `(${fmt(p.x, width)},${fmt(p.y, height)})`)
        .join(' ');
      return `${prefix}（手绘）：bbox=[${fmt(minX, width)},${fmt(minY, height)}]-[${fmt(
        maxX,
        width,
      )},${fmt(maxY, height)}] points=${sampleStr}`;
    }
    return `${prefix}（${formatEditorToolLabel(mark.type)}）：无有效坐标`;
  };

  const rewritePrompt = (text: string) =>
    text.replace(/#(\d+)/g, (_, raw) => {
      const idx = Number(raw);
      if (Number.isNaN(idx)) return `#${raw}`;
      return `图${idx + 1}`;
    });
  const markLines = marks.length > 0 ? marks.map(describeMark).join('\n') : '无';
  const refLines =
    refUrls.length > 0 ? refUrls.map((u, idx) => `图${idx + 2}: ${u}`).join('\n') : '无';
  const sizeLine = width > 0 && height > 0 ? `width=${width}, height=${height}` : '未知';
  const imageIndexLines = [
    '图1=主图（原始上传图）',
    ...refUrls.map((_, idx) => `图${idx + 2}=参考图#${idx + 1}（image_urls[${idx}]）`),
    '顺序固定，不得重新理解或交换',
  ].join('\n');
  const imageUrlLines = [
    `图1主图URL: ${String(mainUrl || '').trim() || '（未提供）'}`,
    ...refUrls.map((u, idx) => `图${idx + 2}参考图URL: ${u}`),
  ].join('\n');

  return [
    '【系统前缀】',
    prefix,
    '',
    '【用户指令】',
    rewritePrompt(rawPrompt.trim() || '（空）'),
    '',
    '【图像顺序规范】',
    imageIndexLines,
    '',
    '【图像链接映射】',
    imageUrlLines,
    '',
    '【标注说明】',
    markLines,
    '',
    '【参考图】',
    refLines,
    '',
    '【原图尺寸】',
    sizeLine,
    '',
    '【输出标准】',
    outputRules,
  ].join('\n');
};

const renderOptionTags = (options?: Array<{ label: string; value: string } | string>): ReactNode => {
  if (!Array.isArray(options) || options.length === 0) return '—';
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {options.map((opt, idx) => {
        if (typeof opt === 'string') {
          const value = opt.trim();
          return (
            <Tag key={`${value}-${idx}`} size="small" variant="light">
              {value}
            </Tag>
          );
        }
        const value = String(opt.value || opt.label || '').trim();
        return (
          <Tag key={`${value}-${idx}`} size="small" variant="light">
            {value}
          </Tag>
        );
      })}
    </div>
  );
};

const OMIT_PARAM_KEYS = new Set([
  'url',
  'image',
  'images',
  'image_url',
  'image_urls',
  'imageurl',
  'imageurls',
  'input_url',
  'input_urls',
  'inputurl',
  'inputurls',
  'input_oss_url',
  'input_oss_urls',
  'oss_url',
  'oss_urls',
]);

const filterDisplayParams = (
  params: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null => {
  if (!params || typeof params !== 'object' || Array.isArray(params)) return null;
  const entries = Object.entries(params).filter(([key]) => {
    const normalized = key.trim().toLowerCase();
    return !OMIT_PARAM_KEYS.has(normalized);
  });
  if (entries.length === 0) return null;
  return Object.fromEntries(entries);
};

const INTERNAL_EVAL_DOC_KEYS = new Set(['count', 'generatecount', 'variantcount', 'n']);

const isFissionWorkflow = (wf: EvalWorkflowVersion): boolean =>
  getWorkflowCategory(wf) === '图裂变';

const sanitizeWorkflowDoc = (wf: WorkflowDoc): WorkflowDoc => {
  if (getWorkflowCategory(wf as any) !== '图裂变') return wf;
  const filteredParams = Array.isArray(wf.parameters)
    ? wf.parameters.filter((param) => !INTERNAL_EVAL_DOC_KEYS.has(String(param.name || '').toLowerCase()))
    : wf.parameters;
  const requestBody = wf.request?.body;
  const filteredRequest =
    requestBody && typeof requestBody === 'object'
      ? {
          ...wf.request,
          body: {
            ...requestBody,
            parameters:
              requestBody && typeof requestBody === 'object' && !Array.isArray(requestBody)
                ? Object.fromEntries(
                    Object.entries((requestBody as any).parameters || {}).filter(
                      ([key]) => !INTERNAL_EVAL_DOC_KEYS.has(String(key || '').toLowerCase()),
                    ),
                  )
                : (requestBody as any).parameters,
          },
        }
      : wf.request;
  return {
    ...wf,
    parameters: filteredParams,
    request: filteredRequest,
  };
};

const buildCozeDoc = (wf: EvalWorkflowVersion, urlExample: string) => {
  const paramsExample: Record<string, unknown> = {};
  const fields = getFields(wf).filter((f) => {
    if (!isFissionWorkflow(wf)) return true;
    return !INTERNAL_EVAL_DOC_KEYS.has(String(f.name || '').toLowerCase());
  });
  for (const f of fields) {
    if (f.name === 'url') {
      paramsExample.url = urlExample || 'https://...';
      continue;
    }
    const options = Array.isArray((f as any).options) ? ((f as any).options as any[]) : null;
    if (options && options.length > 0) {
      paramsExample[f.name] = String(options[0].value);
      continue;
    }
    if (typeof (f as any).defaultValue === 'string') {
      paramsExample[f.name] = (f as any).defaultValue;
      continue;
    }
    paramsExample[f.name] = '';
  }
  return [
    'curl -X POST "$COZE_BASE_URL/v1/workflow/run" \\',
    '  -H "Authorization: Bearer $COZE_API_TOKEN" \\',
    '  -H "Content-Type: application/json" \\',
    `  -d '${JSON.stringify({ workflow_id: wf.workflow_id, parameters: paramsExample }, null, 2)}'`,
  ].join('\n');
};

const buildBusinessApiDoc = (wf: EvalWorkflowVersion, urlExample: string) => {
  const execution = getWorkflowEvalExecution(wf);
  const businessKey = String(execution?.business_key || 'fission').trim() || 'fission';
  const businessVersion = String(execution?.version || wf.version || '').trim();
  const paramsExample: Record<string, unknown> = {};
  const fields = getFields(wf).filter((f) => {
    if (!isFissionWorkflow(wf)) return true;
    return !INTERNAL_EVAL_DOC_KEYS.has(String(f.name || '').toLowerCase());
  });

  for (const f of fields) {
    if (f.name === 'url' || f.name === 'imageUrl') {
      paramsExample.imageUrl = urlExample || 'https://...';
      continue;
    }
    const options = normalizeFieldOptions(f);
    if (options.length > 0) {
      paramsExample[f.name] = String(options[0].value);
      continue;
    }
    if (typeof f.defaultValue === 'string') {
      paramsExample[f.name] = f.defaultValue;
      continue;
    }
    paramsExample[f.name] = '';
  }

  if (!paramsExample.imageUrl) paramsExample.imageUrl = urlExample || 'https://...';
  if (businessVersion) paramsExample.version = businessVersion;
  paramsExample.source = 'partner-api';
  paramsExample.channel = 'open-api';
  paramsExample.requestId = 'biz-request-001';

  const endpointKey = businessKey.replaceAll('_', '-');
  return [
    '【提交任务】',
    `curl -X POST "$PODI_BASE_URL/api/business/${endpointKey}/runs" \\`,
    '  -H "Authorization: Bearer $PODI_API_TOKEN" \\',
    '  -H "Content-Type: application/json" \\',
    `  -d '${JSON.stringify(paramsExample, null, 2)}'`,
    '',
    '【查询结果】',
    'curl -X GET "$PODI_BASE_URL/api/business/runs/<runId>" \\',
    '  -H "Authorization: Bearer $PODI_API_TOKEN"',
    '',
    '返回中的 runId 是中台业务任务 ID；taskId 是底层能力任务 ID，业务方一般只需要保存 runId。',
  ].join('\n');
};

const buildAiEditorDoc = (
  wf: EvalWorkflowVersion,
  urlExample: string,
  promptExample: string,
  refUrls: string[],
) => {
  const prompt =
    promptExample ||
    '【用户指令】\\n@标注1 把这段文字改成“新年快乐”，字体风格参考 图2\\n\\n【图像编号】\\n图1=主图\\n图2=参考图#1\\n\\n【标注说明】\\n@标注1（矩形）：left=120(0.12), top=80(0.08), width=240(0.24), height=60(0.06)\\n\\n【参考图】\\n图2: https://...\\n\\n【原图尺寸】\\nwidth=1000, height=800';
  const imageUrls = refUrls.length > 0 ? refUrls.join(',') : 'https://...';
  return [
    '【提示词重组方法】',
    '1) 用户在图片上完成标注，系统为每个标注分配 @标注1/@标注2…',
    '2) 参考图按上传顺序编号为 #1/#2…（模型侧=图2/图3…，图1固定为主图）',
    '3) prompt 内的 #1/#2 会自动改写成 图2/图3，保证模型能理解对应图片',
    '4) 最终 prompt = 用户指令 + 图像编号 + 标注说明 + 参考图映射 + 原图尺寸（像素/比例）',
    '',
    '【调用示例】',
    'curl -X POST \"$COZE_BASE_URL/v1/workflow/run\" \\\\',
    '  -H \"Authorization: Bearer $COZE_API_TOKEN\" \\\\',
    '  -H \"Content-Type: application/json\" \\\\',
    `  -d '${JSON.stringify(
      {
        workflow_id: wf.workflow_id,
        parameters: { url: urlExample || 'https://...', image_urls: imageUrls, prompt },
      },
      null,
      2,
    )}'`,
  ].join('\\n');
};

const isLikelyImageUrl = (url: string): boolean => {
  const u = String(url || '').trim();
  if (!u.startsWith('http://') && !u.startsWith('https://')) return false;
  const lower = u.toLowerCase();
  if (/\.(mp4|mov|webm|m4v|avi)(\?|$)/.test(lower)) return false;
  // Coze debug URLs (HTML) are not image assets; avoid showing broken thumbnails.
  if (lower.includes('/work_flow') || (lower.includes('/workflow') && lower.includes('execute_id='))) return false;
  if (lower.includes('execute_mode=') && lower.includes('execute_id=')) return false;
  // Common image extensions and ComfyUI `/view?filename=xxx.png`.
  if (/\.(png|jpe?g|webp|gif|bmp)(\?|$)/.test(lower)) return true;
  if (lower.includes('filename=') && /filename=[^&]+\.(png|jpe?g|webp|gif|bmp)(\&|$)/.test(lower)) return true;
  // OSS storedUrl often carries an extension, but keep a small allowlist for safety.
  if (lower.includes('.aliyuncs.com') || lower.includes('.oss-')) return true;
  return false;
};

const isLikelyVideoUrl = (url: string): boolean => {
  const u = String(url || '').trim();
  if (!u.startsWith('http://') && !u.startsWith('https://')) return false;
  return /\.(mp4|mov|webm|m4v|avi)(\?|$)/.test(u.toLowerCase());
};

const filterImageUrls = (urls: unknown): string[] => {
  if (!Array.isArray(urls)) return [];
  return urls
    .filter((u) => typeof u === 'string')
    .map((u) => u.trim())
    .filter((u) => u && isLikelyImageUrl(u));
};

const parseOutputValue = (value: unknown): unknown => {
  if (typeof value !== 'string') return value;
  const text = value.trim();
  if (!text) return '';
  if ((text.startsWith('{') && text.endsWith('}')) || (text.startsWith('[') && text.endsWith(']'))) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return text;
};

const dedupeStrings = (items: string[]): string[] => {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const item of items) {
    const text = item.trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    next.push(text);
  }
  return next;
};

const collectOutputStrings = (value: unknown, keys: string[]): string[] => {
  const output = parseOutputValue(value);
  const results: string[] = [];
  const pushValue = (candidate: unknown) => {
    if (typeof candidate === 'string') {
      const text = candidate.trim();
      if (text) results.push(text);
      return;
    }
    if (Array.isArray(candidate)) {
      candidate.forEach(pushValue);
      return;
    }
    if (candidate && typeof candidate === 'object') {
      const record = candidate as Record<string, unknown>;
      for (const key of ['url', 'storedUrl', 'stored_url', 'outputUrl', 'output_url', 'imageUrl', 'videoUrl']) {
        pushValue(record[key]);
      }
    }
  };
  if (Array.isArray(output)) {
    output.forEach(pushValue);
    return dedupeStrings(results);
  }
  if (!output || typeof output !== 'object') return dedupeStrings(results);
  const record = output as Record<string, unknown>;
  keys.forEach((key) => pushValue(record[key]));
  return dedupeStrings(results);
};

type RunOutputDescriptor = {
  kind: 'image' | 'video' | 'text' | 'structured' | 'none';
  label: string;
  hasOutput: boolean;
  imageUrls: string[];
  videoUrls: string[];
  textCount: number;
  preview: string;
};

const getRunOutputDescriptor = (
  run: Pick<EvalRun, 'result_image_urls_json' | 'result_output_json'>,
): RunOutputDescriptor => {
  const output = parseOutputValue((run as any).result_output_json);
  const directImages = filterImageUrls(run.result_image_urls_json);
  const nestedImages = collectOutputStrings(output, ['imageUrls', 'image_urls', 'images', 'resultUrls', 'result_urls']).filter(
    isLikelyImageUrl,
  );
  const imageUrls = dedupeStrings([...directImages, ...nestedImages]);
  const videoUrls = collectOutputStrings(output, ['videoUrls', 'video_urls', 'videos', 'imageUrls', 'image_urls', 'images', 'resultUrls', 'result_urls'])
    .filter(isLikelyVideoUrl);
  const textValues = collectOutputStrings(output, ['texts', 'resultTexts', 'result_texts', 'text', 'content', 'message'])
    .filter((item) => !isLikelyImageUrl(item) && !isLikelyVideoUrl(item));
  const preview = formatJsonPreview(output, 1200);
  if (imageUrls.length > 0) {
    return { kind: 'image', label: `已回填 ${imageUrls.length} 张`, hasOutput: true, imageUrls, videoUrls, textCount: textValues.length, preview };
  }
  if (videoUrls.length > 0) {
    return { kind: 'video', label: `已回填 ${videoUrls.length} 个视频`, hasOutput: true, imageUrls, videoUrls, textCount: textValues.length, preview };
  }
  if ((typeof output === 'string' && output.trim()) || textValues.length > 0) {
    return { kind: 'text', label: '有文字/VL结果', hasOutput: true, imageUrls, videoUrls, textCount: Math.max(1, textValues.length), preview };
  }
  if (output && ((Array.isArray(output) && output.length > 0) || (typeof output === 'object' && Object.keys(output as Record<string, unknown>).length > 0))) {
    return { kind: 'structured', label: '有结构化结果', hasOutput: true, imageUrls, videoUrls, textCount: textValues.length, preview };
  }
  return { kind: 'none', label: '无结果', hasOutput: false, imageUrls, videoUrls, textCount: 0, preview: '' };
};

const runHasVisibleOutput = (run: Pick<EvalRun, 'result_image_urls_json' | 'result_output_json'>): boolean => {
  return getRunOutputDescriptor(run).hasOutput;
};

const isSucceededWithoutVisibleOutput = (run: Pick<EvalRun, 'status' | 'result_image_urls_json' | 'result_output_json'>): boolean =>
  ['succeeded', 'success', 'completed'].includes(String(run.status || '').toLowerCase()) && !runHasVisibleOutput(run);

function Lightbox({
  url,
  title,
  onClose,
}: {
  url: string;
  title?: string;
  onClose: () => void;
}) {
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    setZoomed(false);
  }, [url]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!url) return null;

  return (
    <Dialog
      visible
      header={title || '预览'}
      onClose={onClose}
      onCancel={onClose}
      footer={
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary" style={{ maxWidth: 560 }} ellipsis>
            {url}
          </Typography.Text>
          <Space>
            <Switch value={zoomed} onChange={(v) => setZoomed(Boolean(v))} />
            <Typography.Text theme="secondary">放大</Typography.Text>
            <Button variant="outline" onClick={() => window.open(url, '_blank', 'noreferrer')}>
              新窗口打开
            </Button>
          </Space>
        </Space>
      }
    >
      <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
        <img
          src={url}
          alt="preview"
          style={{
            display: 'block',
            margin: '0 auto',
            maxWidth: zoomed ? 'none' : '100%',
            width: zoomed ? 'auto' : '100%',
            maxHeight: zoomed ? 'none' : '70vh',
            objectFit: 'contain',
          }}
        />
      </div>
    </Dialog>
  );
}

function ToolCard({
  wf,
  active,
  metric,
  onClick,
  onOpenRecent,
}: {
  wf: EvalWorkflowVersion;
  active: boolean;
  metric?: WorkflowMetric;
  onClick: () => void;
  onOpenRecent?: (focus: ToolHistoryFocus) => void;
}) {
  const ratingText = metric?.avgRating ? metric.avgRating.toFixed(2) : '—';
  const ratingCountText = metric?.ratingCount ? `${metric.ratingCount}票` : '未评分';
  const categoryName = getWorkflowCategory(wf);
  const visual = getCategoryVisual(categoryName);
  const accent = getWorkflowAccent(wf);
  const title = getWorkflowCardTitle(wf);
  const operationTitle = getWorkflowOperationTitle(wf);
  const usageHint = getWorkflowCardSubtitle(wf);
  const inputSummary = getWorkflowInputSummary(wf);
  const outputSummary = getWorkflowOutputSummary(wf);
  const releaseDate = getWorkflowReleaseDate(wf);
  const shortId = getWorkflowShortId(wf);
  const runtimeHealth = getWorkflowRuntimeHealth(metric);
  const recentOutputLabel = getWorkflowRecentOutputLabel(metric);
  const governance = getWorkflowGovernance(wf);
  const routingGovernance = getWorkflowRoutingGovernance(wf);
  const roleLabel = String(governance?.roleLabel || '可测版本').trim();
  const roleReason = String(governance?.roleReason || '').trim();
  const roleTheme = getWorkflowGovernanceTheme(governance?.role);
  const role = String(governance?.role || '').trim().toLowerCase();
  const isAuxiliary = role === 'auxiliary';
  const isInternalTesting = isWorkflowInternalTesting(wf);
  const routingTheme = getWorkflowRoutingGovernanceTheme(routingGovernance?.governanceStatus);
  const executionLabel = String(routingGovernance?.executionLabel || '执行面待确认').trim();
  const trackingLabel = String(routingGovernance?.currentTrackingLabel || '追踪待确认').trim();
  const badges = getWorkflowBadges(wf);
  const cornerBadge = getWorkflowCornerBadge(wf);
  const panelStyle = {
    height: '100%',
    borderColor: active ? accent : undefined,
    '--podi-tool-accent': accent,
    '--podi-tool-cover': `linear-gradient(120deg, ${accent}22, ${accent}08)`,
  } as CSSProperties;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick();
      }}
      className={`podi-eval-tool-card${isAuxiliary ? ' podi-eval-tool-card--auxiliary' : ''}${isInternalTesting ? ' podi-eval-tool-card--candidate' : ''}`}
    >
      <Card bordered className="podi-eval-tool-card__panel" style={panelStyle}>
        <div className="podi-eval-tool-card__topline" />
        {cornerBadge ? <div className="podi-eval-tool-card__corner-badge">{cornerBadge}</div> : null}
        <div className="podi-eval-tool-card__cover">
          <span className="podi-eval-tool-card__cover-icon" style={{ color: accent }}>
            {visual.icon}
          </span>
          <span className="podi-eval-tool-card__cover-text">{categoryName}</span>
        </div>
        {isAuxiliary ? (
          <div className="podi-eval-tool-card__auxiliary-note">
            辅助验证工具，不作为业务主入口；用于自检、排障或结果补充处理。
          </div>
        ) : null}
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="podi-eval-tool-card__identity">
            <div style={{ minWidth: 0 }}>
              <div className="podi-eval-tool-card__kicker">{operationTitle}</div>
              <div className="podi-eval-tool-card__title" title={cleanWorkflowDisplayText(wf.name || title)}>{title}</div>
              {badges.length ? (
                <div className="podi-eval-tool-card__badges" aria-label="功能标记">
                  {badges.map((badge) => (
                    <Tag key={badge} size="small" theme={getWorkflowBadgeTheme(badge)} variant="light">
                      {badge}
                    </Tag>
                  ))}
                </div>
              ) : null}
              <div className="podi-eval-tool-card__subtitle podi-clamp-2">{usageHint}</div>
            </div>
            <Space direction="vertical" size={2} style={{ alignItems: 'flex-end' }}>
              <Typography.Text className="podi-eval-tool-card__score">{ratingText}</Typography.Text>
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {ratingCountText}
              </Typography.Text>
            </Space>
          </div>

          <div className="podi-eval-tool-card__signature">
            <span>{getWorkflowVersionLabel(wf)}</span>
            <span>发布 {releaseDate}</span>
          </div>
          <div className="podi-eval-tool-card__runtime">
            <Tag variant="light" theme={runtimeHealth.theme}>
              {runtimeHealth.label}
            </Tag>
            <span title={runtimeHealth.detail}>
              <Typography.Text theme="secondary">{runtimeHealth.detail}</Typography.Text>
            </span>
            <Button
              size="small"
              variant="text"
              onClick={(event) => {
                event.stopPropagation();
                onOpenRecent?.(runtimeHealth.focus);
              }}
            >
              {runtimeHealth.cta}
            </Button>
          </div>

          <div className="podi-eval-tool-card__meta-grid">
            <div>
              <span>输入</span>
              <strong>{inputSummary}</strong>
            </div>
            <div>
              <span>输出</span>
              <strong>{outputSummary}</strong>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <Space breakLine>
              <Tag variant="light" theme={roleTheme}>{roleLabel}</Tag>
              <Tag variant="light">{getWorkflowStatusLabel(wf.status)}</Tag>
              {recentOutputLabel ? <Tag variant="light">{recentOutputLabel}</Tag> : null}
              {isWorkflowBatchEnabled(wf) ? <Tag variant="light">支持批量</Tag> : null}
            </Space>
          </div>
          {roleReason ? (
            <Typography.Text theme="secondary" className="podi-eval-tool-card__role-reason">
              {roleReason}
            </Typography.Text>
          ) : null}
          <details
            className="podi-eval-tool-card__details"
            onClick={(event) => event.stopPropagation()}
          >
            <summary>查看底层链路</summary>
            <div>
              <span>工作流 {shortId}</span>
              <span>{routingGovernance?.governanceLabel || '链路待确认'}</span>
              <span>{executionLabel}</span>
              <span>{trackingLabel}</span>
              <Tag size="small" variant="light" theme={routingTheme}>
                排障信息
              </Tag>
            </div>
          </details>
          <div className="podi-eval-tool-card__footer">
            <Typography.Text>进入功能工作台</Typography.Text>
            <Typography.Text theme="secondary">→</Typography.Text>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ParamField({
  field,
  value,
  onChange,
  optionsOverride,
  disabled,
  description,
}: {
  field: SchemaField;
  value: string;
  onChange: (v: string) => void;
  optionsOverride?: LoraOption[];
  disabled?: boolean;
  description?: string;
}) {
  const label = field.label ?? field.name;
  const required = Boolean(field.required);
  const options = Array.isArray(optionsOverride)
    ? optionsOverride
    : Array.isArray((field as any).options)
      ? ((field as any).options as any[]).map((opt) => ({
          label: String((opt as any)?.label ?? (opt as any)?.value ?? opt),
          value: String((opt as any)?.value ?? opt),
        }))
      : null;
  const helperText = String(description ?? field.description ?? '').trim();
  const type = (field.type || '').toLowerCase();

  if (options && options.length > 0) {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text>
          {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
        </Typography.Text>
        <Select
          value={value}
          onChange={(v) => onChange(String(v))}
          options={options.map((opt) => ({ label: String((opt as any).label ?? (opt as any).value), value: String((opt as any).value) }))}
          disabled={disabled}
        />
        {helperText ? <Typography.Text theme="secondary">{helperText}</Typography.Text> : null}
      </Space>
    );
  }

  if (type === 'textarea') {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text>
          {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
        </Typography.Text>
        <Textarea
          value={value}
          onChange={(v) => onChange(String(v))}
          autosize={{ minRows: 3, maxRows: 8 }}
          disabled={disabled}
        />
        {helperText ? <Typography.Text theme="secondary">{helperText}</Typography.Text> : null}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Typography.Text>
        {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
      </Typography.Text>
      <Input value={value} onChange={(v) => onChange(String(v))} disabled={disabled} />
      {helperText ? <Typography.Text theme="secondary">{helperText}</Typography.Text> : null}
    </Space>
  );
}

function StepGuide({
  title,
  hint,
  steps,
}: {
  title: string;
  hint?: string;
  steps: Array<{ title: string; description: string }>;
}) {
  return (
    <Card bordered>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Typography.Text strong>{title}</Typography.Text>
          {hint ? (
            <div>
              <Typography.Text theme="secondary">{hint}</Typography.Text>
            </div>
          ) : null}
        </div>
        <div className="podi-eval-step-grid">
          {steps.map((step, idx) => (
            <div key={step.title} className="podi-eval-step-card">
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Tag theme="primary" variant="light">
                  步骤 {idx + 1}
                </Tag>
                <Typography.Text strong>{step.title}</Typography.Text>
                <Typography.Text theme="secondary">{step.description}</Typography.Text>
              </Space>
            </div>
          ))}
        </div>
      </Space>
    </Card>
  );
}

function IntegrationDocBlock({
  doc,
  title = '业务接入文档（Coze OpenAPI）',
  description = '低频资料默认收起；需要给业务方核对参数时再展开。',
  expanded,
  onToggle,
  onCopy,
}: {
  doc: string;
  title?: string;
  description?: string;
  expanded: boolean;
  onToggle: () => void;
  onCopy: () => void;
}) {
  return (
    <div className="podi-integration-doc">
      <div className="podi-integration-doc__head">
        <div>
          <strong>{title}</strong>
          <span>{description}</span>
        </div>
        <Space>
          <Button size="small" variant="outline" onClick={onCopy}>
            复制
          </Button>
          <Button size="small" variant="text" onClick={onToggle}>
            {expanded ? '收起' : '展开'}
          </Button>
        </Space>
      </div>
      {expanded ? <pre className="podi-integration-doc__pre">{doc}</pre> : null}
    </div>
  );
}

function TaskTable({
  runs,
  workflowMap,
}: {
  runs: RunWithLatest[];
  workflowMap: Record<string, EvalWorkflowVersion>;
}) {
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
              <Typography.Text strong>任务管理</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                实时刷新：排队/运行中会持续轮询；ComfyUI 类回调出图后才算完成。
                </Typography.Text>
              </div>
            </div>
          <Typography.Text theme="secondary">最近 {runs.length} 条</Typography.Text>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={runs}
        empty={<Typography.Text theme="secondary">暂无任务。</Typography.Text>}
        columns={[
          {
            colKey: 'created_at',
            title: '时间',
            width: 180,
            cell: ({ row }) => <Typography.Text>{fmtTime(row.created_at)}</Typography.Text>,
          },
          {
            colKey: 'workflow',
            title: '工作流',
            minWidth: 240,
            cell: ({ row }) => {
              const wf = workflowMap[row.workflow_version_id];
              return (
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{wf ? wf.name : row.workflow_version_id}</Typography.Text>
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }} ellipsis>
                    {wf?.workflow_id || '—'}
                  </Typography.Text>
                </Space>
              );
            },
          },
          {
            colKey: 'status',
            title: '状态',
            width: 150,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <StatusBadge status={row.status} />
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  耗时：{formatDuration(row.duration_ms)}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'pipeline',
            title: '中台链路',
            minWidth: 300,
            cell: ({ row }) => (
              <Space direction="vertical" size={4}>
                {row.podi_task_id ? (
                  <Typography.Text style={{ fontFamily: 'monospace', fontSize: 12 }} ellipsis>
                    中台任务：{row.podi_task_id}
                  </Typography.Text>
                ) : (
                  <Tag variant="light">未返回中台任务 ID</Tag>
                )}
                <Space breakLine>
                  <Tag variant="light">提交：{formatEvalStageStatus('submit', row.submit_status)}</Tag>
                  <Tag variant="light">回填：{formatEvalStageStatus('callback', row.callback_status)}</Tag>
                  <Tag variant="light">最终：{formatEvalStageStatus('final', row.final_status || row.status)}</Tag>
                  <Tag variant="light">成本：{formatEvalRunCost(row)}</Tag>
                </Space>
                {row.error_code ? (
                  <Typography.Text theme="error" style={{ fontSize: 12 }}>
                    错误码：{row.error_code}
                  </Typography.Text>
                ) : null}
              </Space>
            ),
          },
          {
            colKey: 'rating',
            title: '评分',
            width: 120,
            cell: ({ row }) =>
              row.latest_annotation?.rating ? (
                <Tag theme="warning" variant="light">
                  {row.latest_annotation.rating}
                </Tag>
              ) : (
                <Typography.Text theme="secondary">未评分</Typography.Text>
              ),
          },
          {
            colKey: 'output',
            title: '输出',
            minWidth: 220,
            cell: ({ row }) => {
              const output = getRunOutputDescriptor(row);
              if (output.imageUrls.length > 0) {
                return (
                  <Space breakLine>
                    <Typography.Text theme="secondary">{output.label}</Typography.Text>
                    <Button size="small" variant="text" onClick={() => window.open(output.imageUrls[0], '_blank', 'noreferrer')}>
                      打开首张
                    </Button>
                  </Space>
                );
              }
              if (output.videoUrls.length > 0) {
                return (
                  <Space breakLine>
                    <Typography.Text theme="secondary">{output.label}</Typography.Text>
                    <Button size="small" variant="text" onClick={() => window.open(output.videoUrls[0], '_blank', 'noreferrer')}>
                      打开视频
                    </Button>
                  </Space>
                );
              }
              if (output.preview) {
                return (
                  <Typography.Text theme="secondary" style={{ fontFamily: 'monospace', fontSize: 12 }} ellipsis>
                    {output.label}：{output.preview}
                  </Typography.Text>
                );
              }
              return (
                <Typography.Text theme="secondary">
                  {row.status === 'running' || row.status === 'queued' ? '生成中…' : '暂无输出'}
                </Typography.Text>
              );
            },
          },
          {
            colKey: 'actions',
            title: '操作',
            width: 220,
            cell: ({ row }) => (
              <Space>
                {row.coze_debug_url ? (
                  <Button
                    size="small"
                    variant="outline"
                    onClick={() => window.open(row.coze_debug_url || '', '_blank', 'noreferrer')}
                  >
                    调试链接
                  </Button>
                ) : null}
                {row.error_message ? <Typography.Text theme="error">失败</Typography.Text> : null}
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}

function ImageTile({
  url,
  title,
  onOpen,
}: {
  url: string;
  title: string;
  onOpen: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="podi-image-tile"
    >
      {!loaded && !failed ? (
        <div className="podi-image-tile__loading">
          加载中…
        </div>
      ) : null}
      {failed ? (
        <div className="podi-image-tile__error">
          <strong>图片加载失败</strong>
          <span>{url}</span>
        </div>
      ) : null}
      <img
        src={url}
        alt={title}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className="podi-image-tile__img"
      />
      <span className="podi-image-tile__caption">{title}</span>
    </button>
  );
}

function SkeletonTile({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="podi-image-tile podi-image-tile--skeleton">
      <div className="podi-image-tile__pulse" />
      <strong>{title}</strong>
      {subtitle ? <span>{subtitle}</span> : null}
    </div>
  );
}

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem('podi.eval.theme');
  return stored === 'dark' ? 'dark' : 'light';
}

export function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme());
  const [pageVisible, setPageVisible] = useState<boolean>(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible',
  );
  const [recentTaskRefreshUntil, setRecentTaskRefreshUntil] = useState<number>(0);
  useEffect(() => {
    const isDark = theme === 'dark';
    // TDesign dark mode is driven by `t-theme-dark` class.
    document.documentElement.classList.toggle('t-theme-dark', isDark);
    // Keep Tailwind dark variants working during migration.
    document.documentElement.classList.toggle('dark', isDark);
    window.localStorage.setItem('podi.eval.theme', theme);
  }, [theme]);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const syncVisibility = () => setPageVisible(document.visibilityState === 'visible');
    syncVisibility();
    document.addEventListener('visibilitychange', syncVisibility);
    window.addEventListener('focus', syncVisibility);
    return () => {
      document.removeEventListener('visibilitychange', syncVisibility);
      window.removeEventListener('focus', syncVisibility);
    };
  }, []);

  const pushNotice = useCallback((type: 'error' | 'success' | 'info', message: string) => {
    const content = toDisplayErrorMessage(message) || '未知错误';
    if (type === 'error') MessagePlugin.error({ content, duration: 5000 });
    else if (type === 'success') MessagePlugin.success({ content, duration: 3500 });
    else MessagePlugin.info({ content, duration: 3500 });
  }, []);

  const [raterId, setRaterId] = useState<string>('');
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [metrics, setMetrics] = useState<Record<string, WorkflowMetric>>({});
  const [resourceOptionsCache, setResourceOptionsCache] = useState<Record<string, LoraOption[]>>({});
  const [bootstrapLoading, setBootstrapLoading] = useState<boolean>(false);
  const [workflowListStatus, setWorkflowListStatus] = useState<RemoteLoadStatus>('idle');
  const [workflowListError, setWorkflowListError] = useState<RemoteLoadError | null>(null);

  const initialQuery = useMemo(() => readEvalQuery(), []);
  const [activeCategory, setActiveCategory] = useState<string>(initialQuery.category);
  const [activeView, setActiveView] = useState<EvalView>(initialQuery.view);
  const [selectedTool, setSelectedTool] = useState<EvalWorkflowVersion | null>(null);
  const [pendingToolId, setPendingToolId] = useState<string>(initialQuery.toolId);
  const [showIntegrationDoc, setShowIntegrationDoc] = useState(false);

  const [formUrl, setFormUrl] = useState('');
  const [formParams, setFormParams] = useState<Record<string, string>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extraImageUploading, setExtraImageUploading] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const extraImagesInputRef = useRef<HTMLInputElement | null>(null);
  const [extraImageFieldTarget, setExtraImageFieldTarget] = useState<string | null>(null);

  const [editorTool, setEditorTool] = useState<EditorTool>('rect');
  const [editorPrompt, setEditorPrompt] = useState('');
  const [editorPromptHint, setEditorPromptHint] = useState<PromptHint | null>(null);
  const [editorMarks, setEditorMarks] = useState<EditorMark[]>([]);
  const [editorRefs, setEditorRefs] = useState<string[]>([]);
  const [editorRefDraft, setEditorRefDraft] = useState('');
  const [editorDrawing, setEditorDrawing] = useState<EditorMark | null>(null);
  const [editorImageMeta, setEditorImageMeta] = useState({
    displayW: 0,
    displayH: 0,
    naturalW: 0,
    naturalH: 0,
  });
  const editorIdRef = useRef(1);
  const editorContainerRef = useRef<HTMLDivElement | null>(null);
  const editorImageRef = useRef<HTMLImageElement | null>(null);
  const editorPromptRef = useRef<HTMLTextAreaElement | null>(null);
  const editorRefUploadRef = useRef<HTMLInputElement | null>(null);

  // Keep tool run history and global task list separate.
  // Otherwise, in-flight requests from one view can overwrite the other's list.
  const [toolRuns, setToolRuns] = useState<RunWithLatest[]>([]);
  const [taskRuns, setTaskRuns] = useState<RunWithLatest[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterRating, setFilterRating] = useState<string>('all');
  const [filterUnrated, setFilterUnrated] = useState<boolean>(false);
  const [historyFocus, setHistoryFocus] = useState<ToolHistoryFocus>('all');
  const [search, setSearch] = useState<string>('');
  const [lightbox, setLightbox] = useState<{ url: string; title?: string } | null>(null);

  // Simple "private" admin token stored in localStorage.
  const [adminToken, setAdminToken] = useState<string>(() => localStorage.getItem('podi_eval_admin_token') || '');
  const [adminWorkflows, setAdminWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [adminWorkflowStatus, setAdminWorkflowStatus] = useState<RemoteLoadStatus>('idle');
  const [adminWorkflowError, setAdminWorkflowError] = useState<RemoteLoadError | null>(null);
  const [operationsHealth, setOperationsHealth] = useState<EvalOperationsHealth | null>(null);
  const [operationsHealthStatus, setOperationsHealthStatus] = useState<RemoteLoadStatus>('idle');
  const [operationsHealthError, setOperationsHealthError] = useState<RemoteLoadError | null>(null);
  const [comfyuiQueueSummary, setComfyuiQueueSummary] = useState<ComfyuiQueueSummary | null>(null);
  const [comfyuiQueueStatus, setComfyuiQueueStatus] = useState<RemoteLoadStatus>('idle');
  const [comfyuiQueueError, setComfyuiQueueError] = useState<RemoteLoadError | null>(null);
  const [docsMarkdown, setDocsMarkdown] = useState<string>('');
  const [docsLoading, setDocsLoading] = useState<boolean>(false);
  const [docsGeneratedAt, setDocsGeneratedAt] = useState<string>('');
  const [docsWorkflows, setDocsWorkflows] = useState<WorkflowDoc[]>([]);
  const [docsView, setDocsView] = useState<'structured' | 'markdown'>('structured');
  const [batchWorkflowId, setBatchWorkflowId] = useState<string>('');
  const [batchLoraValue, setBatchLoraValue] = useState<string>('');
  const [batchRepeatCount, setBatchRepeatCount] = useState<string>('3');
  const [batchConcurrency, setBatchConcurrency] = useState<string>('3');
  const [batchSizeMode, setBatchSizeMode] = useState<'original' | 'preset_1k' | 'custom'>('preset_1k');
  const [batchAspectRatio, setBatchAspectRatio] = useState<string>('auto');
  const [batchResolution, setBatchResolution] = useState<string>('1K');
  const [batchCustomWidth, setBatchCustomWidth] = useState<string>('1024');
  const [batchCustomHeight, setBatchCustomHeight] = useState<string>('1024');
  const [batchParamOverrides, setBatchParamOverrides] = useState<Record<string, string>>({});
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [loraBatchSubView, setLoraBatchSubView] = useState<LoraBatchSubView>('generation');
  const [batchDetailExpanded, setBatchDetailExpanded] = useState<boolean>(false);
  const [batchSessionId, setBatchSessionId] = useState<string>('');
  const [batchSessions, setBatchSessions] = useState<LoraBatchSession[]>([]);
  const [batchItems, setBatchItems] = useState<LoraBatchItem[]>([]);
  const [batchReviewMap, setBatchReviewMap] = useState<Record<string, LoraBatchReview>>({});
  const batchReviewMapRef = useRef<Record<string, LoraBatchReview>>({});
  const [batchSubmitting, setBatchSubmitting] = useState<boolean>(false);
  const [batchLoadingSessions, setBatchLoadingSessions] = useState<boolean>(false);
  const [batchLoadingItems, setBatchLoadingItems] = useState<boolean>(false);
  const [batchSessionLoadError, setBatchSessionLoadError] = useState<string>('');
  const [batchItemsLoadError, setBatchItemsLoadError] = useState<string>('');
  const [batchReviewGroups, setBatchReviewGroups] = useState<LoraReviewGroup[]>([]);
  const [batchReviewGroupLoading, setBatchReviewGroupLoading] = useState<boolean>(false);
  const [batchReviewGroupError, setBatchReviewGroupError] = useState<string>('');
  const [batchReviewPage, setBatchReviewPage] = useState<number>(1);
  const [batchReviewTotalPages, setBatchReviewTotalPages] = useState<number>(0);
  const [batchReviewTotalGroups, setBatchReviewTotalGroups] = useState<number>(0);
  const [batchReviewProgress, setBatchReviewProgress] = useState<LoraReviewProgress>({
    pageSize: 20,
    currentPage: 1,
    completedPage: 0,
  });
  const [showNoOutputGroups, setShowNoOutputGroups] = useState<boolean>(false);
  const [batchReviewProgressSaving, setBatchReviewProgressSaving] = useState<boolean>(false);
  const [batchReviewPageJumping, setBatchReviewPageJumping] = useState<boolean>(false);
  const [batchExporting, setBatchExporting] = useState<'' | 'all' | 'unsatisfied'>('');
  const batchSessionsLoadingRef = useRef<boolean>(false);
  const batchItemsLoadingRef = useRef<boolean>(false);
  const batchReviewGroupLoadingRef = useRef<boolean>(false);
  const [batchStopping, setBatchStopping] = useState<boolean>(false);
  const batchStopRef = useRef<boolean>(false);
  const batchFileInputRef = useRef<HTMLInputElement | null>(null);
  const [batchUploadProgress, setBatchUploadProgress] = useState<LoraBatchUploadProgress>({
    batchId: '',
    totalFiles: 0,
    totalBytes: 0,
    uploadedFiles: 0,
    failedFiles: 0,
    activeFiles: 0,
    uploadedBytes: 0,
  });
  const batchUploadCommittedBytesRef = useRef<number>(0);
  const batchUploadInFlightRef = useRef<Map<string, number>>(new Map());
  const batchUploadUploadedFilesRef = useRef<number>(0);
  const batchUploadFailedFilesRef = useRef<number>(0);
  const batchReviewSaveTimersRef = useRef<Map<string, number>>(new Map());
  const batchReviewSaveErrorKeysRef = useRef<Set<string>>(new Set());

  const displayWorkflows = useMemo(() => dedupeWorkflowVersionsForDisplay(workflows), [workflows]);

  const workflowMap = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion> = {};
    for (const wf of displayWorkflows) m[wf.id] = wf;
    return m;
  }, [displayWorkflows]);

  const grouped = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion[]> = {};
    for (const wf of displayWorkflows) {
      const key = getWorkflowCategory(wf);
      m[key] = m[key] || [];
      m[key].push(wf);
    }
    return m;
  }, [displayWorkflows]);

  const orderedCategories = useMemo(() => {
    const visible = CATEGORY_ORDER.filter((category) => PINNED_CATEGORY_SET.has(category) || (grouped[category] || []).length > 0);
    return visible.length > 0 ? visible : CATEGORY_ORDER.slice(0, 4);
  }, [grouped]);

  const toolList = useMemo(() => {
    const list = (grouped[activeCategory] || []).slice().sort((a, b) => {
      const testingOrder = getWorkflowTestingSortRank(a) - getWorkflowTestingSortRank(b);
      if (testingOrder !== 0) return testingOrder;
      const order = getWorkflowSortOrder(a) - getWorkflowSortOrder(b);
      if (order !== 0) return order;
      const roleOrder = getWorkflowGovernanceRank(a) - getWorkflowGovernanceRank(b);
      if (roleOrder !== 0) return roleOrder;
      return a.name.localeCompare(b.name);
    });
    return list;
  }, [grouped, activeCategory]);
  const totalToolCount = displayWorkflows.length;

  useEffect(() => {
    if (!pendingToolId) return;
    const matched = displayWorkflows.find((wf) => wf.id === pendingToolId);
    if (!matched) return;
    setSelectedTool(matched);
    setShowIntegrationDoc(false);
    setActiveCategory(getWorkflowCategory(matched));
    setActiveView('tool');
    setPendingToolId('');
  }, [pendingToolId, displayWorkflows]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('view', activeView);
    params.set('category', activeCategory);
    if (selectedTool?.id) params.set('tool', selectedTool.id);
    else params.delete('tool');
    const next = params.toString();
    const current = window.location.search.replace(/^\?/, '');
    if (next === current) return;
    const suffix = next ? `?${next}` : '';
    window.history.replaceState(null, '', `${window.location.pathname}${suffix}${window.location.hash}`);
  }, [activeView, activeCategory, selectedTool?.id]);

  useEffect(() => {
    const loraBindings = displayWorkflows
      .flatMap((wf) => (Array.isArray(wf.resourceBindings) ? wf.resourceBindings : []))
      .filter((binding) => binding && binding.resourceType === 'lora' && typeof binding.source === 'string' && binding.source.trim());
    const pending = loraBindings.filter((binding) => !resourceOptionsCache[binding.source]);
    if (pending.length === 0) return;
    let cancelled = false;
    void (async () => {
      for (const binding of pending) {
        try {
          const url = new URL(binding.source, window.location.origin);
          const type = url.searchParams.get('type') || 'lora';
          const status = url.searchParams.get('status') || 'active';
          const resp = await evalApi.listResourceOptions({ type, status, q: url.searchParams.get('q') || undefined });
          if (cancelled) return;
          const options = (resp.items || []).map((item) => ({ label: item.label || item.key, value: item.key }));
          setResourceOptionsCache((prev) => ({ ...prev, [binding.source]: options }));
        } catch (err) {
          console.error(err);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [displayWorkflows, resourceOptionsCache]);

  const loraBatchWorkflows = useMemo<LoraBatchWorkflowMeta[]>(() => {
    const metas: LoraBatchWorkflowMeta[] = [];
    for (const wf of displayWorkflows) {
      if (!isWorkflowBatchEnabled(wf)) continue;
      const fields = getFields(wf);
      const urlField = fields.find((f) => f.name === 'url' || f.name === 'Url') || null;
      if (!urlField) continue;
      const usage = getWorkflowUsage(wf);
      const resourceOptionTypes = Array.isArray(usage?.resourceOptionTypes) ? usage?.resourceOptionTypes.map((x) => String(x || '').toLowerCase()) : [];
      const expectsLoraFromUsage = resourceOptionTypes.includes('lora');
      const loraField =
        fields.find((f) => String(f.name || '').toLowerCase() === 'lora') ||
        fields.find((f) => String(f.name || '').toLowerCase().includes('lora')) ||
        null;
      if (!loraField && !expectsLoraFromUsage) continue;
      const loraBinding =
        (Array.isArray(wf.resourceBindings) ? wf.resourceBindings : []).find(
          (binding) => binding.resourceType === 'lora' && (!loraField || binding.field === loraField.name),
        ) || null;
      const dynamicOptions =
        loraBinding && resourceOptionsCache[loraBinding.source] && resourceOptionsCache[loraBinding.source].length > 0
          ? resourceOptionsCache[loraBinding.source]
          : null;
      metas.push({
        workflow: wf,
        urlFieldName: urlField.name,
        loraField,
        loraSource: loraBinding?.source,
        loraOptions: dynamicOptions || normalizeFieldOptions(loraField),
      });
    }
    metas.sort((a, b) => {
      const order = getWorkflowSortOrder(a.workflow) - getWorkflowSortOrder(b.workflow);
      if (order !== 0) return order;
      return String(a.workflow.name || '').localeCompare(String(b.workflow.name || ''));
    });
    return metas;
  }, [displayWorkflows, resourceOptionsCache]);

  const selectedBatchWorkflowMeta = useMemo<LoraBatchWorkflowMeta | null>(() => {
    if (!batchWorkflowId) return null;
    return loraBatchWorkflows.find((item) => item.workflow.id === batchWorkflowId) || null;
  }, [batchWorkflowId, loraBatchWorkflows]);

  const selectedBatchWorkflow = selectedBatchWorkflowMeta?.workflow || null;
  const batchLoraFieldName = selectedBatchWorkflowMeta?.loraField?.name || '';
  const batchFields = useMemo(() => getFields(selectedBatchWorkflow), [selectedBatchWorkflow]);
  const batchPromptField = useMemo(
    () => batchFields.find((f) => String(f.name || '').toLowerCase() === 'prompt') || null,
    [batchFields],
  );
  const batchAspectField = useMemo(
    () => batchFields.find((f) => f.name === 'aspect_ratio' || f.name === 'aspectRatio') || null,
    [batchFields],
  );
  const batchResolutionField = useMemo(
    () => batchFields.find((f) => String(f.name || '').toLowerCase() === 'resolution') || null,
    [batchFields],
  );
  const batchWidthField = useMemo(
    () => batchFields.find((f) => String(f.name || '').toLowerCase() === 'width') || null,
    [batchFields],
  );
  const batchHeightField = useMemo(
    () => batchFields.find((f) => String(f.name || '').toLowerCase() === 'height') || null,
    [batchFields],
  );
  const batchAspectOptions = useMemo(() => normalizeFieldOptions(batchAspectField, { allowEmpty: true }), [batchAspectField]);
  const batchResolutionOptions = useMemo(() => normalizeFieldOptions(batchResolutionField), [batchResolutionField]);
  const batchExtraFields = useMemo(
    () =>
      batchFields.filter((f) => {
        if (f.name === 'url' || f.name === 'Url') return false;
        if (batchLoraFieldName && f.name === batchLoraFieldName) return false;
        if (batchPromptField && f.name === batchPromptField.name) return false;
        if (isBatchSizeFieldName(f.name)) return false;
        return true;
      }),
    [batchFields, batchLoraFieldName, batchPromptField],
  );
  const filteredBatchSessions = useMemo(
    () => batchSessions.filter((item) => !isEmptyDraftBatchSession(item)),
    [batchSessions],
  );
  const batchSessionOptions = useMemo(
    () =>
      filteredBatchSessions.map((item) => ({
        label: `${item.workflowName ? `${item.workflowName} · ` : ''}${item.batchId}（完成 ${item.completed}/${item.total}）`,
        value: item.batchId,
      })),
    [filteredBatchSessions],
  );
  const selectedBatchId = useMemo(() => {
    if (batchSessionId && filteredBatchSessions.some((item) => item.batchId === batchSessionId)) return batchSessionId;
    return String(filteredBatchSessions[0]?.batchId || '');
  }, [batchSessionId, filteredBatchSessions]);
  const selectedBatchSession = useMemo(
    () => batchSessions.find((item) => item.batchId === selectedBatchId) || null,
    [batchSessions, selectedBatchId],
  );
  const visibleBatchItems = useMemo(
    () => (selectedBatchId ? batchItems.filter((item) => item.batchId === selectedBatchId) : []),
    [batchItems, selectedBatchId],
  );
  const uploadFailedBatchItems = useMemo(
    () => visibleBatchItems.filter((item) => isUploadStageFailure(item)),
    [visibleBatchItems],
  );
  const visibleExecutionBatchItems = useMemo(
    () => visibleBatchItems.filter((item) => !isUploadStageFailure(item)),
    [visibleBatchItems],
  );
  const batchSummary = useMemo(() => {
    const total = visibleExecutionBatchItems.length;
    const imageCountRaw = new Set(visibleExecutionBatchItems.map((item) => item.sourceKey || item.fileName)).size;
    const repeatCountRaw = imageCountRaw > 0 ? Math.max(...visibleExecutionBatchItems.map((item) => item.repeatIndex || 1), 1) : 0;
    const sessionImageCount = Number(selectedBatchSession?.expectedImages || 0);
    const sessionRepeatCount = Number(selectedBatchSession?.expectedRepeat || 0);
    const sessionPlannedTotal = Number(selectedBatchSession?.expectedTotal || selectedBatchSession?.total || 0);
    const sessionSubmitted = Number(selectedBatchSession?.submittedCount || 0);
    const sessionSucceeded = Number(selectedBatchSession?.succeeded || 0);
    const sessionFailed = Number(selectedBatchSession?.failed || 0);
    const sessionCompleted = sessionSucceeded + sessionFailed;
    const sessionQueuedOrRunning = Math.max(0, Number(selectedBatchSession?.queued || 0) + Number(selectedBatchSession?.running || 0));
    const sessionUploadFailed = Math.max(0, Number(selectedBatchSession?.uploadFailedCount || 0));
    const sessionStatus = String(selectedBatchSession?.status || '').toLowerCase();
    const hasItemDetails = total > 0 || uploadFailedBatchItems.length > 0;

    const imageCount = sessionImageCount > 0 ? sessionImageCount : imageCountRaw;
    const repeatCount = sessionRepeatCount > 0 ? sessionRepeatCount : repeatCountRaw;
    const plannedTotal = sessionPlannedTotal > 0 ? sessionPlannedTotal : total;
    const submittedFromItems = visibleExecutionBatchItems.filter((item) => item.status === 'submitted' && Boolean(item.runId)).length;
    const completedFromItems = visibleExecutionBatchItems.filter((item) => item.runStatus === 'succeeded' || item.runStatus === 'failed').length;
    const generatedFromItems = visibleExecutionBatchItems.filter((item) => item.runStatus === 'succeeded' && (item.outputCount || 0) > 0).length;
    const failedFromItems = visibleExecutionBatchItems.filter((item) => item.status === 'failed' || item.runStatus === 'failed').length;
    const activeFromItems = visibleExecutionBatchItems.filter((item) => item.status === 'uploading' || item.status === 'submitting').length;
    const queuedOrRunningFromItems = visibleExecutionBatchItems.filter(
      (item) =>
        item.status === 'submitted' &&
        (!item.runStatus || item.runStatus === 'queued' || item.runStatus === 'running' || item.runStatus === 'unknown'),
    ).length;
    const submitted = hasItemDetails ? submittedFromItems : sessionSubmitted;
    const completed = hasItemDetails ? completedFromItems : sessionCompleted;
    const generated = hasItemDetails ? generatedFromItems : sessionSucceeded;
    const failed = hasItemDetails ? failedFromItems : sessionFailed;
    const active = hasItemDetails
      ? activeFromItems
      : sessionStatus === 'uploading' || sessionStatus === 'ready' || sessionStatus === 'submitting'
        ? Math.max(1, sessionQueuedOrRunning)
        : 0;
    const queuedOrRunning = hasItemDetails ? queuedOrRunningFromItems : sessionQueuedOrRunning;
    const uploadFailed = hasItemDetails ? uploadFailedBatchItems.length : sessionUploadFailed;
    const missingSubmissions = Math.max(0, plannedTotal - submitted - uploadFailed);
    return { total, imageCount, repeatCount, plannedTotal, missingSubmissions, submitted, completed, generated, failed, active, queuedOrRunning, uploadFailed };
  }, [visibleExecutionBatchItems, uploadFailedBatchItems.length, selectedBatchSession]);
  const selectedBatchIsTerminal = useMemo(
    () => isTerminalBatchStatus(String(selectedBatchSession?.status || '')),
    [selectedBatchSession?.status],
  );
  const batchReviewPageOptions = useMemo(
    () =>
      Array.from({ length: Math.max(0, batchReviewTotalPages) }, (_, idx) => {
        const value = idx + 1;
        return { label: `第 ${value} 页`, value };
      }),
    [batchReviewTotalPages],
  );
  const batchUploadFilePercent = useMemo(() => {
    if (!batchUploadProgress.totalFiles) return 0;
    const done = batchUploadProgress.uploadedFiles + batchUploadProgress.failedFiles;
    return Math.max(0, Math.min(100, Math.round((done / batchUploadProgress.totalFiles) * 100)));
  }, [batchUploadProgress]);
  const batchUploadBytePercent = useMemo(() => {
    if (!batchUploadProgress.totalBytes) return 0;
    return Math.max(0, Math.min(100, Math.round((batchUploadProgress.uploadedBytes / batchUploadProgress.totalBytes) * 100)));
  }, [batchUploadProgress]);
  const batchReviewReasonOptions = useMemo(
    () => [
      { label: '主体风格不一致', value: '主体风格不一致' },
      { label: '细节结构错误', value: '细节结构错误' },
      { label: '边缘/拼接异常', value: '边缘/拼接异常' },
      { label: '颜色偏差明显', value: '颜色偏差明显' },
      { label: '构图偏移', value: '构图偏移' },
      { label: '提示词理解错误', value: '提示词理解错误' },
      { label: '分辨率质量不足', value: '分辨率质量不足' },
      { label: '其他', value: '其他' },
    ],
    [],
  );
  useEffect(() => {
    batchReviewMapRef.current = batchReviewMap;
  }, [batchReviewMap]);

  const actionableReviewGroups = useMemo(
    () => batchReviewGroups.filter((group) => Array.isArray(group.outputs) && group.outputs.length > 0),
    [batchReviewGroups],
  );
  const noOutputGroupCount = useMemo(
    () => Math.max(0, batchReviewGroups.length - actionableReviewGroups.length),
    [batchReviewGroups.length, actionableReviewGroups.length],
  );

  useEffect(
    () => () => {
      for (const timer of batchReviewSaveTimersRef.current.values()) {
        window.clearTimeout(timer);
      }
      batchReviewSaveTimersRef.current.clear();
    },
    [],
  );

  const toolFields = useMemo(() => getFields(selectedTool), [selectedTool]);
  const requiresImage = useMemo(
    () => toolFields.some((f) => f.name === 'url' || f.name === 'Url'),
    [toolFields],
  );
  const isAiEditor = selectedTool?.workflow_id === AI_EDITOR_WORKFLOW_ID;
  const isShengtuWorkflow = selectedTool?.workflow_id === SHENGTU_WORKFLOW_ID;
  const selectedModelValue = useMemo(() => {
    if (!isShengtuWorkflow) return '';
    const raw = String((formParams as any)?.moxing ?? '').trim();
    if (raw) return raw;
    const modelField = toolFields.find((f) => f.name === 'moxing');
    return String((modelField as any)?.defaultValue ?? '1').trim() || '1';
  }, [isShengtuWorkflow, formParams, toolFields]);
  const modelAwareFieldMap = useMemo(() => {
    const map = new Map<string, { optionsOverride?: LoraOption[]; disabled: boolean; description: string }>();
    for (const field of toolFields) {
      map.set(field.name, resolveModelAwareField(field, selectedModelValue));
    }
    return map;
  }, [toolFields, selectedModelValue]);

  useEffect(() => {
    if (!isShengtuWorkflow) return;
    if (!selectedModelValue) return;
    const next = { ...formParams };
    let changed = false;
    for (const field of toolFields) {
      const view = modelAwareFieldMap.get(field.name);
      if (!view) continue;
      const current = String((next as any)[field.name] ?? '');
      if (view.disabled && current.trim()) {
        (next as any)[field.name] = '';
        changed = true;
        continue;
      }
      if (view.optionsOverride && view.optionsOverride.length > 0 && !view.optionsOverride.some((opt) => opt.value === current)) {
        (next as any)[field.name] = view.optionsOverride[0].value;
        changed = true;
      }
    }
    if (changed) setFormParams(next);
  }, [isShengtuWorkflow, selectedModelValue, modelAwareFieldMap, toolFields, formParams]);
  const editorPromptPreview = useMemo(() => {
    if (!isAiEditor) return '';
    return buildEditorPrompt({
      rawPrompt: editorPrompt,
      marks: editorMarks,
      refUrls: editorRefs,
      mainUrl: formUrl.trim(),
      imageSize: { width: editorImageMeta.naturalW, height: editorImageMeta.naturalH },
    });
  }, [editorPrompt, editorMarks, editorRefs, formUrl, editorImageMeta, isAiEditor]);

  const updateEditorPromptHint = useCallback(
    (value: string) => {
      if (!isAiEditor) {
        setEditorPromptHint(null);
        return;
      }
      const el = editorPromptRef.current;
      const pos = el?.selectionStart ?? value.length;
      const before = value.slice(0, pos);
      const lastAt = before.lastIndexOf('@');
      const lastHash = before.lastIndexOf('#');
      const symbolIndex = Math.max(lastAt, lastHash);
      if (symbolIndex < 0) {
        setEditorPromptHint(null);
        return;
      }
      const symbol = before[symbolIndex];
      const query = before.slice(symbolIndex + 1);
      if (/\s/.test(query)) {
        setEditorPromptHint(null);
        return;
      }
      setEditorPromptHint({
        type: symbol === '@' ? 'mark' : 'ref',
        query,
        start: symbolIndex,
        end: pos,
      });
    },
    [isAiEditor],
  );

  const promptHintOptions = useMemo(() => {
    if (!editorPromptHint) return [];
    if (editorPromptHint.type === 'mark') {
      return editorMarks
        .map((mark, idx) => {
          const name = mark.name || `标注${idx + 1}`;
          return { label: `@${name}`, token: `@${name}` };
        })
        .filter((item) => !editorPromptHint.query || item.label.includes(editorPromptHint.query));
    }
    return editorRefs
      .map((url, idx) => ({
        label: `#${idx + 1}（图${idx + 2}）`,
        token: `#${idx + 1}`,
        url,
      }))
      .filter((item) => !editorPromptHint.query || item.label.includes(editorPromptHint.query));
  }, [editorPromptHint, editorMarks, editorRefs]);

  const applyPromptHint = useCallback(
    (token: string) => {
      const el = editorPromptRef.current;
      const value = editorPrompt;
      if (!el) return;
      const start = editorPromptHint ? editorPromptHint.start : el.selectionStart ?? value.length;
      const end = editorPromptHint ? editorPromptHint.end : el.selectionStart ?? value.length;
      const next = `${value.slice(0, start)}${token}${value.slice(end)}`;
      setEditorPrompt(next);
      setEditorPromptHint(null);
      window.requestAnimationFrame(() => {
        try {
          el.focus();
          const cursor = start + token.length;
          el.setSelectionRange(cursor, cursor);
        } catch {
          // ignore
        }
      });
    },
    [editorPrompt, editorPromptHint],
  );

  const refreshMetrics = async () => {
    const resp = await evalApi.workflowMetrics().catch(() => ({ metrics: {} }));
    setMetrics(resp.metrics || {});
  };

  const loadWorkflowList = useCallback(async () => {
    setWorkflowListStatus('loading');
    setWorkflowListError(null);
    try {
      const wfs = await evalApi.listWorkflowVersions();
      const rawRows = wfs || [];
      const displayRows = dedupeWorkflowVersionsForDisplay(rawRows);
      setWorkflows(rawRows);
      setWorkflowListStatus('success');
      if (displayRows.length > 0) {
        const counts: Record<string, number> = {};
        for (const wf of displayRows) {
          const k = getWorkflowCategory(wf);
          counts[k] = (counts[k] || 0) + 1;
        }
        const firstNonEmpty = CATEGORY_ORDER.find((k) => (counts[k] || 0) > 0);
        setActiveCategory((prev) => {
          const current = CATEGORY_ORDER.includes(prev) ? prev : normalizeCategory(prev);
          if ((counts[current] || 0) > 0) return current;
          return firstNonEmpty || DEFAULT_CATEGORY;
        });
      }
    } catch (err) {
      console.error(err);
      setWorkflowListStatus('error');
      setWorkflowListError(normalizeRemoteLoadError(err));
    }
  }, []);

  const loadBootstrap = useCallback(async () => {
    setBootstrapLoading(true);
    try {
      await evalApi
        .me()
        .then((me) => setRaterId(me.raterId))
        .catch((err) => {
          console.error(err);
          return null;
        });
      await Promise.allSettled([loadWorkflowList(), refreshMetrics()]);
    } finally {
      setBootstrapLoading(false);
    }
  }, [loadWorkflowList]);

  const loadAdminWorkflowList = useCallback(
    async (token: string, opts?: { notifySuccess?: boolean }) => {
      const trimmed = String(token || '').trim();
      if (!trimmed) return;
      setAdminWorkflowStatus('loading');
      setAdminWorkflowError(null);
      try {
        const list = await evalApi.adminListWorkflowVersions(trimmed);
        setAdminWorkflows(dedupeWorkflowVersionsForDisplay(list || []));
        setAdminWorkflowStatus('success');
        if (opts?.notifySuccess) pushNotice('success', '已刷新列表');
      } catch (err) {
        console.error(err);
        setAdminWorkflowStatus('error');
        setAdminWorkflowError(normalizeRemoteLoadError(err));
        throw err;
      }
    },
    [],
  );

  const loadOperationsHealth = useCallback(
    async (token?: string, opts?: { notifySuccess?: boolean }) => {
      const trimmed = String(token || adminToken || '').trim();
      if (!trimmed) {
        setOperationsHealth(null);
        setOperationsHealthStatus('idle');
        setOperationsHealthError(null);
        return;
      }
      setOperationsHealthStatus('loading');
      setOperationsHealthError(null);
      try {
        const report = await evalApi.adminGetOperationsHealth(trimmed);
        setOperationsHealth(report);
        setOperationsHealthStatus('success');
        if (opts?.notifySuccess) pushNotice('success', '已刷新链路健康');
      } catch (err) {
        console.error(err);
        setOperationsHealthStatus('error');
        setOperationsHealthError(normalizeRemoteLoadError(err));
        throw err;
      }
    },
    [adminToken, pushNotice],
  );

  const loadComfyuiQueueSummary = useCallback(
    async (token?: string, opts?: { notifySuccess?: boolean }) => {
      const trimmed = String(token || adminToken || '').trim();
      if (!trimmed) {
        setComfyuiQueueSummary(null);
        setComfyuiQueueStatus('idle');
        setComfyuiQueueError(null);
        return;
      }
      setComfyuiQueueStatus('loading');
      setComfyuiQueueError(null);
      try {
        const report = await evalApi.adminGetComfyuiQueueSummary(trimmed);
        setComfyuiQueueSummary(report);
        setComfyuiQueueStatus('success');
        if (opts?.notifySuccess) pushNotice('success', '已刷新 ComfyUI 队列');
      } catch (err) {
        console.error(err);
        setComfyuiQueueStatus('error');
        setComfyuiQueueError(normalizeRemoteLoadError(err));
        throw err;
      }
    },
    [adminToken, pushNotice],
  );

  const loadRunsForTool = async (workflowVersionId: string) => {
    try {
      const resp = await evalApi.listRunsWithLatestAnnotation({
        workflow_version_id: workflowVersionId,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        unrated: filterUnrated,
        limit: 80,
        offset: 0,
      });
      setToolRuns((resp.items || []) as RunWithLatest[]);
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const loadTasks = async () => {
    try {
      const resp = await evalApi.listRunsWithLatestAnnotation({ limit: 80, offset: 0 });
      setTaskRuns((resp.items || []) as RunWithLatest[]);
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const bumpTaskRefreshWindow = useCallback((seconds = 20) => {
    setRecentTaskRefreshUntil(Date.now() + seconds * 1000);
  }, []);

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (!adminToken) {
      setOperationsHealth(null);
      setOperationsHealthStatus('idle');
      setOperationsHealthError(null);
      setComfyuiQueueSummary(null);
      setComfyuiQueueStatus('idle');
      setComfyuiQueueError(null);
      return;
    }
    void loadOperationsHealth(adminToken).catch(() => undefined);
    void loadComfyuiQueueSummary(adminToken).catch(() => undefined);
  }, [adminToken, loadOperationsHealth, loadComfyuiQueueSummary]);

  useEffect(() => {
    if (loraBatchWorkflows.length === 0) {
      setBatchWorkflowId('');
      setBatchLoraValue('');
      return;
    }
    if (!batchWorkflowId || !loraBatchWorkflows.some((item) => item.workflow.id === batchWorkflowId)) {
      const first = loraBatchWorkflows[0];
      setBatchWorkflowId(first.workflow.id);
      setBatchLoraValue(first.loraOptions[0]?.value || '');
    }
  }, [loraBatchWorkflows, batchWorkflowId]);

  useEffect(() => {
    if (!selectedBatchWorkflowMeta) {
      setBatchLoraValue('');
      return;
    }
    const options = selectedBatchWorkflowMeta.loraOptions;
    if (options.length === 0) {
      setBatchLoraValue('');
      return;
    }
    if (!batchLoraValue || !options.some((opt) => opt.value === batchLoraValue)) {
      setBatchLoraValue(options[0].value);
    }
  }, [selectedBatchWorkflowMeta, batchLoraValue]);

  useEffect(() => {
    if (!selectedBatchWorkflow) {
      setBatchParamOverrides({});
      return;
    }
    const defaults = buildWorkflowDefaultParams(selectedBatchWorkflow);
    const next: Record<string, string> = {};
    for (const field of batchFields) {
      if (field.name === 'url' || field.name === 'Url') continue;
      if (batchLoraFieldName && field.name === batchLoraFieldName) continue;
      if (isBatchSizeFieldName(field.name)) continue;
      next[field.name] = String(defaults[field.name] ?? '');
    }
    setBatchParamOverrides(next);
  }, [selectedBatchWorkflow, batchFields, batchLoraFieldName]);

  useEffect(() => {
    if (!selectedBatchWorkflow) return;
    if (batchAspectField) {
      const opts = normalizeFieldOptions(batchAspectField, { allowEmpty: true });
      const preferred =
        opts.find((item) => item.value === '')?.value ||
        opts.find((item) => item.value.toLowerCase() === 'auto')?.value ||
        String((batchAspectField as any)?.defaultValue ?? '');
      setBatchAspectRatio(preferred);
    } else {
      setBatchAspectRatio('');
    }
    if (batchResolutionField) {
      const opts = normalizeFieldOptions(batchResolutionField);
      const preferred =
        opts.find((item) => String(item.value).toLowerCase() === '1k')?.value ||
        opts[0]?.value ||
        String((batchResolutionField as any)?.defaultValue || '1K');
      setBatchResolution(preferred);
    } else {
      setBatchResolution('');
    }
    if (batchWidthField || batchHeightField) {
      setBatchCustomWidth(String((batchWidthField as any)?.defaultValue || '1024'));
      setBatchCustomHeight(String((batchHeightField as any)?.defaultValue || '1024'));
    } else {
      setBatchCustomWidth('');
      setBatchCustomHeight('');
    }
  }, [selectedBatchWorkflow, batchAspectField, batchResolutionField, batchWidthField, batchHeightField]);

  const loadBatchSessions = useCallback(async (opts?: { silent?: boolean }) => {
    if (batchSessionsLoadingRef.current) return;
    batchSessionsLoadingRef.current = true;
    if (!opts?.silent) setBatchLoadingSessions(true);
    try {
      const res = await evalApi.listRunBatches({
        mine_only: false,
        limit: 200,
        offset: 0,
      });
      const items = Array.isArray(res.items) ? (res.items as LoraBatchSession[]) : [];
      setBatchSessions((prev) => {
        if (prev.length === items.length) {
          const unchanged = prev.every((item, idx) => {
            const next = items[idx];
            return (
              item.batchId === next.batchId &&
              String(item.status || '') === String(next.status || '') &&
              Number(item.total || 0) === Number(next.total || 0) &&
              Number(item.completed || 0) === Number(next.completed || 0) &&
              Number(item.queued || 0) === Number(next.queued || 0) &&
              Number(item.running || 0) === Number(next.running || 0) &&
              Number(item.succeeded || 0) === Number(next.succeeded || 0) &&
              Number(item.failed || 0) === Number(next.failed || 0) &&
              String(item.latestUpdatedAt || '') === String(next.latestUpdatedAt || '')
            );
          });
          if (unchanged) return prev;
        }
        return items;
      });
      setBatchSessionLoadError('');
      const selectable = items.filter((item) => !isEmptyDraftBatchSession(item));
      if (!batchSessionId && selectable[0]?.batchId) {
        setBatchSessionId(selectable[0].batchId);
      } else if (batchSessionId && !selectable.some((item) => item.batchId === batchSessionId)) {
        setBatchSessionId(selectable[0]?.batchId || '');
      }
    } catch (err) {
      const msg = String((err as any)?.message || err || '');
      setBatchSessionLoadError(msg || '加载失败');
    } finally {
      if (!opts?.silent) setBatchLoadingSessions(false);
      batchSessionsLoadingRef.current = false;
    }
  }, [batchSessionId]);

  const loadBatchItems = useCallback(
    async (batchId: string, opts?: { silent?: boolean }) => {
      const id = String(batchId || '').trim();
      if (!id) return;
      if (batchItemsLoadingRef.current) return;
      batchItemsLoadingRef.current = true;
      if (!opts?.silent) setBatchLoadingItems(true);
      try {
        const repeatCount = Math.max(
          1,
          Number(batchSessions.find((item) => item.batchId === id)?.expectedRepeat || 0) || 1,
        );
        const fetchAllPages = async <T,>(
          fetcher: (offset: number) => Promise<{ total: number; items: T[] }>,
        ): Promise<T[]> => {
          const pageSize = 200;
          let offset = 0;
          let total = 0;
          const out: T[] = [];
          do {
            const res = await fetcher(offset);
            const items = Array.isArray(res.items) ? res.items : [];
            total = Number(res.total || 0);
            out.push(...items);
            offset += items.length;
            if (items.length === 0) break;
            if (offset >= 10000) break;
          } while (offset < total);
          return out;
        };

        const [runItems, assets] = await Promise.all([
          fetchAllPages((offset) => evalApi.listBatchItems(id, { limit: 200, offset })),
          fetchAllPages((offset) => evalApi.listBatchAssets(id, { limit: 200, offset })),
        ]);

        const mapped: LoraBatchItem[] = [];
        const knownRunKeys = new Set<string>();
        for (const row of runItems) {
          const sourceKey = String(row.asset_source_key || row.asset_id || '').trim() || `asset_${row.asset_id}`;
          const repeatIndexRaw = Number(row.repeat_index || 1);
          const repeatIndex = Number.isFinite(repeatIndexRaw) && repeatIndexRaw > 0 ? Math.floor(repeatIndexRaw) : 1;
          const itemStatusRaw = String(row.status || '').toLowerCase();
          const runStatusRaw = String(row.run_status || '').toLowerCase();
          let status: LoraBatchItemStatus = 'pending';
          if (itemStatusRaw === 'submitting') status = 'submitting';
          else if (itemStatusRaw === 'failed' || itemStatusRaw === 'canceled') status = 'failed';
          else if (itemStatusRaw === 'submitted' || itemStatusRaw === 'running' || itemStatusRaw === 'succeeded') status = 'submitted';
          let runStatus: LoraBatchRunStatus = 'unknown';
          if (runStatusRaw === 'queued' || itemStatusRaw === 'submitted') runStatus = 'queued';
          else if (runStatusRaw === 'running' || itemStatusRaw === 'running') runStatus = 'running';
          else if (runStatusRaw === 'failed' || itemStatusRaw === 'failed' || itemStatusRaw === 'canceled') runStatus = 'failed';
          else if (runStatusRaw === 'succeeded' || itemStatusRaw === 'succeeded') runStatus = 'succeeded';
          const outputUrls = Array.isArray(row.run_output_urls_json)
            ? row.run_output_urls_json.map((u) => String(u || '').trim()).filter((u) => Boolean(u))
            : [];
          const outputReviews: LoraBatchOutputReview[] = [];
          if (Array.isArray((row as any).run_output_reviews_json)) {
            for (const rv of (row as any).run_output_reviews_json as any[]) {
              const outputIndex = Number((rv as any)?.output_index || 0);
              if (!Number.isFinite(outputIndex) || outputIndex <= 0) continue;
              const verdictRaw = String((rv as any)?.verdict || '').trim().toLowerCase();
              const verdict: LoraBatchReviewVerdict =
                verdictRaw === 'satisfied' || verdictRaw === 'unsatisfied' ? (verdictRaw as LoraBatchReviewVerdict) : 'pending';
              outputReviews.push({
                outputIndex: Math.floor(outputIndex),
                verdict,
                reason: String((rv as any)?.reason || '').trim() || undefined,
                note: String((rv as any)?.note || '').trim() || undefined,
              });
            }
          }
          const runId = row.eval_run_id ? String(row.eval_run_id) : undefined;
          const runItemId = String(row.id || '').trim();
          const key = runItemId || runId || `${id}::${sourceKey}::${repeatIndex}`;
          knownRunKeys.add(`${sourceKey}::${repeatIndex}`);
          mapped.push({
            key,
            batchId: id,
            sourceKey,
            fileName: String(row.asset_file_name || '').trim() || inferFileNameFromUrl(String(row.asset_oss_url || '')),
            repeatIndex,
            status,
            runItemId: runItemId || undefined,
            runId,
            inputUrl: String(row.asset_oss_url || '').trim() || undefined,
            error: String(row.error_message || row.run_error_message || '').trim() || undefined,
            runStatus,
            outputCount: outputUrls.length,
            outputUrls,
            outputReviews,
            runPrompt: String(row.run_prompt || '').trim() || undefined,
            runError: String(row.run_error_message || row.error_message || '').trim() || undefined,
            failureStage:
              status === 'failed'
                ? runId
                  ? 'run'
                  : 'submit'
                : undefined,
          });
        }

        for (const asset of assets) {
          const sourceKey = String(asset.source_key || '').trim() || `asset_${asset.id}`;
          const fileName = String(asset.file_name || '').trim() || inferFileNameFromUrl(String(asset.oss_url || ''));
          const inputUrl = String(asset.oss_url || '').trim() || undefined;
          const uploadStatus = String(asset.upload_status || '').toLowerCase();
          for (let repeatIndex = 1; repeatIndex <= repeatCount; repeatIndex += 1) {
            const lookup = `${sourceKey}::${repeatIndex}`;
            if (knownRunKeys.has(lookup)) continue;
            if (uploadStatus === 'failed') {
              mapped.push({
                key: `${id}::${lookup}::upload_failed`,
                batchId: id,
                sourceKey,
                fileName,
                repeatIndex,
                status: 'failed',
                failureStage: 'upload',
                inputUrl,
                error: String(asset.upload_error_message || asset.upload_error_code || '素材上传失败'),
                runStatus: 'failed',
                outputCount: 0,
                outputUrls: [],
              });
              continue;
            }
            mapped.push({
              key: `${id}::${lookup}::pending`,
              batchId: id,
              sourceKey,
              fileName,
              repeatIndex,
              status: uploadStatus === 'uploading' ? 'uploading' : 'pending',
              inputUrl,
              outputCount: 0,
              outputUrls: [],
            });
          }
        }

        mapped.sort((a, b) => {
          const source = String(a.sourceKey || '').localeCompare(String(b.sourceKey || ''));
          if (source !== 0) return source;
          return (a.repeatIndex || 1) - (b.repeatIndex || 1);
        });

        const runItemIds = new Set<string>();
        const serverReviewMap: Record<string, LoraBatchReview> = {};
        for (const item of mapped) {
          const runItemId = String(item.runItemId || '').trim();
          if (!runItemId) continue;
          runItemIds.add(runItemId);
          const reviews = Array.isArray(item.outputReviews) ? item.outputReviews : [];
          for (const review of reviews) {
            const outputIndex = Number(review.outputIndex || 0);
            if (!Number.isFinite(outputIndex) || outputIndex <= 0) continue;
            const reviewKey = buildBatchReviewKey(runItemId, outputIndex);
            serverReviewMap[reviewKey] = {
              verdict: review.verdict || 'pending',
              reason: review.reason,
              note: review.note,
            };
          }
        }

        setBatchItems((prev) => {
          const others = prev.filter((item) => item.batchId !== id);
          return [...mapped, ...others];
        });
        setBatchReviewMap((prev) => {
          const next: Record<string, LoraBatchReview> = {};
          for (const [key, value] of Object.entries(prev)) {
            const parsed = parseBatchReviewKey(key);
            if (!parsed) {
              next[key] = value;
              continue;
            }
            if (!runItemIds.has(parsed.runItemId)) {
              next[key] = value;
            }
          }
          return { ...next, ...serverReviewMap };
        });
        setBatchItemsLoadError('');
      } catch (err) {
        const msg = String((err as any)?.message || err || '');
        setBatchItemsLoadError(msg || '加载失败');
      } finally {
        if (!opts?.silent) setBatchLoadingItems(false);
        batchItemsLoadingRef.current = false;
      }
    },
    [batchSessions],
  );

  const loadBatchReviewGroups = useCallback(
    async (
      batchId: string,
      page: number,
      opts?: { silent?: boolean; followProgress?: boolean },
    ) => {
      const id = String(batchId || '').trim();
      if (!id) return;
      if (batchReviewGroupLoadingRef.current) return;
      batchReviewGroupLoadingRef.current = true;
      if (!opts?.silent) setBatchReviewGroupLoading(true);
      try {
        const fetchOne = async (targetPage: number) =>
          evalApi.listBatchReviewGroups(id, { page: targetPage, page_size: 20 });

        let resp = await fetchOne(Math.max(1, Number(page || 1)));
        const progressCurrent = Number(resp.review_progress?.current_page || 1);
        if (
          opts?.followProgress &&
          Number(resp.total_pages || 0) > 0 &&
          progressCurrent > 0 &&
          progressCurrent !== Number(resp.page || 1)
        ) {
          resp = await fetchOne(progressCurrent);
        }

        const groups: LoraReviewGroup[] = [];
        const serverReviewMap: Record<string, LoraBatchReview> = {};
        const pageRunItemIds = new Set<string>();
        for (const row of Array.isArray(resp.items) ? resp.items : []) {
          const outputs: LoraReviewGroupOutput[] = [];
          for (const out of Array.isArray(row.outputs) ? row.outputs : []) {
            const runItemId = String(out.run_item_id || '').trim();
            const outputIndex = Number(out.output_index || 0);
            if (!runItemId || !Number.isFinite(outputIndex) || outputIndex <= 0) continue;
            const reviewKey = buildBatchReviewKey(runItemId, outputIndex);
            outputs.push({
              reviewKey,
              runItemId,
              runId: String(out.run_id || '').trim() || undefined,
              outputIndex: Math.floor(outputIndex),
              url: String(out.url || ''),
              runStatus: String(out.run_status || '').trim() || undefined,
            });
            pageRunItemIds.add(runItemId);
            const rawVerdict = String((out.review as any)?.verdict || '').trim().toLowerCase();
            const verdict: LoraBatchReviewVerdict =
              rawVerdict === 'unsatisfied' || rawVerdict === 'satisfied' ? (rawVerdict as LoraBatchReviewVerdict) : 'pending';
            serverReviewMap[reviewKey] = {
              verdict,
              reason: String((out.review as any)?.reason || '').trim() || undefined,
              note: String((out.review as any)?.note || '').trim() || undefined,
            };
          }
          groups.push({
            assetId: String(row.asset_id || ''),
            sourceKey: String(row.source_key || ''),
            fileName: String(row.file_name || ''),
            inputUrl: String(row.input_url || '').trim() || undefined,
            groupStatus: String(row.group_status || 'no_output'),
            runTotal: Number(row.run_total || 0),
            completed: Number(row.completed || 0),
            failed: Number(row.failed || 0),
            waiting: Number(row.waiting || 0),
            lastError: String(row.last_error || '').trim() || undefined,
            outputs,
          });
        }

        setBatchReviewGroups(groups);
        setBatchReviewPage(Math.max(1, Number(resp.page || 1)));
        setBatchReviewTotalPages(Math.max(0, Number(resp.total_pages || 0)));
        setBatchReviewTotalGroups(Math.max(0, Number(resp.total_groups || 0)));
        setBatchReviewProgress({
          pageSize: 20,
          currentPage: Math.max(1, Number(resp.review_progress?.current_page || resp.page || 1)),
          completedPage: Math.max(0, Number(resp.review_progress?.completed_page || 0)),
          updatedAt: String(resp.review_progress?.updated_at || '').trim() || undefined,
        });
        setBatchReviewMap((prev) => {
          const next: Record<string, LoraBatchReview> = {};
          for (const [key, value] of Object.entries(prev)) {
            const parsed = parseBatchReviewKey(key);
            if (!parsed) {
              next[key] = value;
              continue;
            }
            if (!pageRunItemIds.has(parsed.runItemId)) {
              next[key] = value;
            }
          }
          return { ...next, ...serverReviewMap };
        });
        setBatchReviewGroupError('');
      } catch (err) {
        const msg = String((err as any)?.message || err || '');
        setBatchReviewGroupError(msg || '加载失败');
        if (!opts?.silent) pushNotice('error', `加载标注分页失败：${msg}`);
      } finally {
        if (!opts?.silent) setBatchReviewGroupLoading(false);
        batchReviewGroupLoadingRef.current = false;
      }
    },
    [pushNotice],
  );

  const saveBatchReviewProgress = useCallback(
    async (
      batchId: string,
      payload: { currentPage: number; completedPage: number },
      opts?: { silent?: boolean },
    ) => {
      const id = String(batchId || '').trim();
      if (!id) return null;
      try {
        const res = await evalApi.saveBatchReviewProgress(id, {
          current_page: Math.max(1, Number(payload.currentPage || 1)),
          completed_page: Math.max(0, Number(payload.completedPage || 0)),
          page_size: 20,
        });
        const nextProgress: LoraReviewProgress = {
          pageSize: 20,
          currentPage: Math.max(1, Number(res.review_progress?.current_page || payload.currentPage || 1)),
          completedPage: Math.max(0, Number(res.review_progress?.completed_page || payload.completedPage || 0)),
          updatedAt: String(res.review_progress?.updated_at || '').trim() || undefined,
        };
        setBatchReviewProgress(nextProgress);
        return nextProgress;
      } catch (err) {
        if (!opts?.silent) {
          pushNotice('error', `保存标注进度失败：${String((err as any)?.message || err || '未知错误')}`);
        }
        throw err;
      }
    },
    [pushNotice],
  );

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    if (loraBatchSubView !== 'generation') return;
    if (!pageVisible) return;
    void loadBatchSessions({ silent: true });
    const hasActiveBatch = batchSessions.some((item) => !isTerminalBatchStatus(item.status));
    const intervalMs = hasActiveBatch || batchSubmitting ? 10000 : 30000;
    const timer = window.setInterval(() => {
      void loadBatchSessions({ silent: true });
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [activeView, loraBatchSubView, loadBatchSessions, batchSessions, batchSubmitting, pageVisible]);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    if (loraBatchSubView !== 'generation') return;
    if (!pageVisible) return;
    if (!selectedBatchId) return;
    if (batchSubmitting) return;
    if (!batchDetailExpanded) return;
    void loadBatchItems(selectedBatchId, { silent: true });
  }, [activeView, loraBatchSubView, selectedBatchId, loadBatchItems, batchSubmitting, batchDetailExpanded, pageVisible]);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    if (loraBatchSubView !== 'generation') return;
    if (!pageVisible) return;
    if (!batchDetailExpanded) return;
    const timer = window.setInterval(() => {
      const selectedStatus = String(selectedBatchSession?.status || '');
      if (selectedBatchId && !batchSubmitting && !isTerminalBatchStatus(selectedStatus)) {
        void loadBatchItems(selectedBatchId, { silent: true });
      }
    }, 20000);
    return () => window.clearInterval(timer);
  }, [activeView, loraBatchSubView, selectedBatchId, loadBatchItems, batchSubmitting, selectedBatchSession?.status, batchDetailExpanded, pageVisible]);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    if (loraBatchSubView !== 'annotation') return;
    if (!pageVisible) return;
    if (!selectedBatchId) return;
    if (batchSubmitting) return;
    if (!selectedBatchIsTerminal) return;
    void loadBatchReviewGroups(selectedBatchId, batchReviewPage, { followProgress: true });
  }, [activeView, loraBatchSubView, selectedBatchId, batchSubmitting, selectedBatchIsTerminal, batchReviewPage, loadBatchReviewGroups, pageVisible]);

  useEffect(() => {
    if (activeView !== 'tool' || !selectedTool) return;
    if (!pageVisible) return;
    void loadRunsForTool(selectedTool.id);
    const hasPending = toolRuns.some((r) => r.status === 'queued' || r.status === 'running');
    const recentActivity = Date.now() < recentTaskRefreshUntil;
    if (!hasPending && !recentActivity) return;
    const timer = window.setInterval(() => {
      void loadRunsForTool(selectedTool.id);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeView, selectedTool?.id, filterStatus, filterUnrated, toolRuns, pageVisible, recentTaskRefreshUntil]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setBatchReviewGroups([]);
    setBatchReviewGroupError('');
    setBatchReviewTotalGroups(0);
    setBatchReviewTotalPages(0);
    setBatchReviewPage(1);
    setBatchReviewProgress({
      pageSize: 20,
      currentPage: 1,
      completedPage: 0,
      updatedAt: undefined,
    });
    setShowNoOutputGroups(false);
  }, [selectedBatchId]);

  useEffect(() => {
    if (activeView !== 'tasks') return;
    if (!pageVisible) return;
    void loadTasks();
    const hasPending = taskRuns.some((r) => r.status === 'queued' || r.status === 'running');
    const recentActivity = Date.now() < recentTaskRefreshUntil;
    const intervalMs = hasPending || recentActivity ? 2000 : 10000;
    const timer = window.setInterval(() => void loadTasks(), intervalMs);
    return () => window.clearInterval(timer);
  }, [activeView, pageVisible, taskRuns, recentTaskRefreshUntil]);

  useEffect(() => {
    if (activeView !== 'docs') return;
    setDocsLoading(true);
    void (async () => {
      try {
        const res = await evalApi.getWorkflowDocs();
        setDocsMarkdown(String(res.markdown || ''));
        setDocsGeneratedAt(String(res.generatedAt || ''));
        setDocsWorkflows(Array.isArray(res.workflows) ? res.workflows : []);
      } catch (err) {
        console.error(err);
        pushNotice('error', String((err as any)?.message || err));
      } finally {
        setDocsLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView]);

  const openTool = (wf: EvalWorkflowVersion, focus: ToolHistoryFocus = 'all') => {
    setSelectedTool(wf);
    setFormUrl('');
    // Prevent showing previous tool's results while the new tool's history is loading.
    setToolRuns([]);
    setHistoryFocus(focus);
    setFilterStatus(
      focus === 'failed' ? 'failed' : focus === 'running' ? 'running' : focus === 'succeeded' || focus === 'no_output' ? 'succeeded' : 'all',
    );
    setFilterRating('all');
    setFilterUnrated(false);
    setShowIntegrationDoc(false);
    setSearch('');
    const defaults: Record<string, string> = {};
    for (const f of getFields(wf)) {
      if (f.name === 'url') continue;
      const opt = Array.isArray((f as any).options) && (f as any).options.length > 0 ? (f as any).options[0]?.value : undefined;
      const def = typeof (f as any).defaultValue === 'string' ? (f as any).defaultValue : undefined;
      if (def !== undefined) {
        defaults[f.name] = String(def);
      } else if (opt !== undefined) {
        defaults[f.name] = String(opt);
      } else {
        defaults[f.name] = '';
      }
    }
    if (wf.workflow_id === AI_EDITOR_WORKFLOW_ID) {
      defaults.aspect_ratio = '';
      defaults.resolution = '';
    }
    setFormParams(defaults);
    if (wf.workflow_id === AI_EDITOR_WORKFLOW_ID) {
      setEditorTool('rect');
      setEditorPrompt('');
      setEditorPromptHint(null);
      setEditorMarks([]);
      setEditorRefs([]);
      setEditorRefDraft('');
      setEditorDrawing(null);
      setEditorImageMeta({ displayW: 0, displayH: 0, naturalW: 0, naturalH: 0 });
      editorIdRef.current = 1;
    }
    setActiveView('tool');
  };



  const parseImageUrlList = useCallback((raw: string): string[] => {
    return String(raw || '')
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }, []);

  const appendImageUrls = useCallback((incoming: string[]) => {
    setFormParams((prev) => {
      const current = parseImageUrlList(String(prev.image_urls || ''));
      const merged = [...current];
      for (const url of incoming) {
        if (url && !merged.includes(url)) merged.push(url);
      }
      return { ...prev, image_urls: merged.join('\n') };
    });
  }, [parseImageUrlList]);

  const removeImageUrlAt = useCallback((index: number) => {
    setFormParams((prev) => {
      const current = parseImageUrlList(String(prev.image_urls || ''));
      current.splice(index, 1);
      return { ...prev, image_urls: current.join('\n') };
    });
  }, [parseImageUrlList]);

  const setSingleImageField = useCallback((fieldName: string, value: string) => {
    setFormParams((prev) => ({ ...prev, [fieldName]: value }));
  }, []);
  const syncEditorImageMeta = useCallback(() => {
    const img = editorImageRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    setEditorImageMeta({
      displayW: rect.width,
      displayH: rect.height,
      naturalW: img.naturalWidth || rect.width,
      naturalH: img.naturalHeight || rect.height,
    });
  }, []);

  useEffect(() => {
    if (!isAiEditor || !formUrl.trim()) return;
    syncEditorImageMeta();
    const handleResize = () => syncEditorImageMeta();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [formUrl, isAiEditor, syncEditorImageMeta]);

  useEffect(() => {
    if (!isAiEditor) return;
    if (!formUrl.trim()) {
      setEditorMarks([]);
      setEditorDrawing(null);
    }
  }, [formUrl, isAiEditor]);

  const getEditorDisplayPoint = (evt: ReactMouseEvent): EditorPoint | null => {
    const container = editorContainerRef.current;
    if (!container) return null;
    const rect = container.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const x = Math.max(0, Math.min(rect.width, evt.clientX - rect.left));
    const y = Math.max(0, Math.min(rect.height, evt.clientY - rect.top));
    return { x, y };
  };

  const toEditorOrigPoint = (p: EditorPoint): EditorPoint => {
    const { displayW, displayH, naturalW, naturalH } = editorImageMeta;
    if (!displayW || !displayH) return p;
    return {
      x: (p.x * naturalW) / displayW,
      y: (p.y * naturalH) / displayH,
    };
  };

  const toEditorDisplayPoint = (p: EditorPoint): EditorPoint => {
    const { displayW, displayH, naturalW, naturalH } = editorImageMeta;
    if (!naturalW || !naturalH) return p;
    return {
      x: (p.x * displayW) / naturalW,
      y: (p.y * displayH) / naturalH,
    };
  };

  const createEditorMark = (tool: EditorTool, points: EditorPoint[]): EditorMark => {
    const seq = editorIdRef.current++;
    return {
      id: `mark_${Date.now()}_${seq}`,
      name: `标注${seq}`,
      type: tool,
      points,
      created_at: Date.now(),
    };
  };

  const handleEditorPointerDown = (evt: ReactMouseEvent) => {
    if (!isAiEditor || !formUrl.trim()) return;
    const displayPoint = getEditorDisplayPoint(evt);
    if (!displayPoint) return;
    const origPoint = toEditorOrigPoint(displayPoint);
    if (editorTool === 'point') {
      const mark = createEditorMark('point', [origPoint]);
      setEditorMarks((prev) => [...prev, mark]);
      return;
    }
    setEditorDrawing(createEditorMark(editorTool, [origPoint]));
  };

  const handleEditorPointerMove = (evt: ReactMouseEvent) => {
    if (!editorDrawing) return;
    const displayPoint = getEditorDisplayPoint(evt);
    if (!displayPoint) return;
    const origPoint = toEditorOrigPoint(displayPoint);
    setEditorDrawing((prev) => {
      if (!prev) return prev;
      if (prev.type === 'freehand') {
        const pts = prev.points;
        const last = pts[pts.length - 1];
        const dx = last ? origPoint.x - last.x : 0;
        const dy = last ? origPoint.y - last.y : 0;
        if (last && Math.hypot(dx, dy) < 4) return prev;
        return { ...prev, points: [...pts, origPoint] };
      }
      return { ...prev, points: [prev.points[0], origPoint] };
    });
  };

  const finalizeEditorDrawing = () => {
    if (!editorDrawing) return;
    const mark = editorDrawing;
    let shouldAdd = true;
    if (mark.type === 'rect' || mark.type === 'circle') {
      if (mark.points.length < 2) shouldAdd = false;
      else {
        const a = mark.points[0];
        const b = mark.points[1];
        if (Math.hypot(a.x - b.x, a.y - b.y) < 6) shouldAdd = false;
      }
    }
    if (mark.type === 'freehand' && mark.points.length < 2) {
      shouldAdd = false;
    }
    if (shouldAdd) {
      setEditorMarks((prev) => [...prev, mark]);
    }
    setEditorDrawing(null);
  };

  const groupedDocs = useMemo(() => {
    const map = new Map<string, WorkflowDoc[]>();
    for (const wf of docsWorkflows.map(sanitizeWorkflowDoc)) {
      const cat = normalizeCategory(wf.category);
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(wf);
    }
    const ordered: { category: string; items: WorkflowDoc[] }[] = [];
    for (const cat of CATEGORY_ORDER) {
      if (map.has(cat)) ordered.push({ category: cat, items: map.get(cat)! });
    }
    for (const [cat, items] of map.entries()) {
      if (!ordered.some((entry) => entry.category === cat)) {
        ordered.push({ category: cat, items });
      }
    }
    for (const entry of ordered) {
      entry.items.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    }
    return ordered;
  }, [docsWorkflows]);

  const toAnchorId = (value: string) => `doc-cat-${String(value).replace(/\s+/g, '-')}`;

  const runTool = async () => {
    if (isRunning) return;
    if (!selectedTool) return;
    const url = formUrl.trim();
    const requiresImage = toolFields.some((f) => f.name === 'url' || f.name === 'Url');
    if (requiresImage && !url) {
      pushNotice('error', '请先填写或上传图片 URL');
      return;
    }
    if (isAiEditor && !editorPrompt.trim()) {
      pushNotice('error', '请先填写提示词');
      return;
    }
    if (isAiEditor) {
      const refsCount = editorRefs.length;
      const matches = Array.from(editorPrompt.matchAll(/#(\d+)/g));
      if (matches.length > 0) {
        const nums = matches
          .map((m) => Number(m[1]))
          .filter((n) => Number.isFinite(n) && n > 0);
        const maxRef = nums.length > 0 ? Math.max(...nums) : 0;
        if (maxRef > refsCount) {
          pushNotice('error', `提示词引用了 #${maxRef}，但当前仅有 ${refsCount} 张参考图。`);
          return;
        }
      }
    }

    // Validate required fields in schema (except `prompt`: backend will fallback to " ").
    const missing: string[] = [];
    for (const f of getFields(selectedTool)) {
      if (!(f as any)?.required) continue;
      if (f.name === 'url' || f.name === 'Url' || f.name === 'prompt') continue;
      if (isAiEditor && f.name === 'prompt') continue;
      const modelAware = resolveModelAwareField(f, selectedModelValue);
      if (modelAware.disabled) continue;
      const v = String((formParams as any)?.[f.name] ?? '').trim();
      if (!v) missing.push((f as any).label || f.name);
    }
    if (missing.length > 0) {
      pushNotice('error', `请补齐必填参数：${missing.join('、')}`);
      return;
    }

    setIsRunning(true);
    try {
      const isDuotuRongheWorkflow = String((selectedTool as any)?.workflow_id || '').trim() === '7615600173695107072';
      const normalizeNumericParam = (key: string, value: string): string => {
        const pixelKeys = new Set([
          'width',
          'height',
          'expand_left',
          'expand_right',
          'expand_top',
          'expand_bottom',
          'expandLeft',
          'expandRight',
          'expandTop',
          'expandBottom',
          'left',
          'right',
          'top',
          'bottom',
          'bianchang',
        ]);
        if (!pixelKeys.has(key)) return value;
        const raw = String(value || '').trim();
        if (!raw) return raw;
        let num = '';
        for (const ch of raw) {
          if (ch >= '0' && ch <= '9') {
            num += ch;
          } else if (num) {
            break;
          }
        }
        return num || raw;
      };

      const normalizeWorkflowParam = (key: string, value: string): string => {
        const normalized = normalizeNumericParam(key, value);
        if (key === 'similarity' || key === 'bili') {
          return String(normalized || '')
            .replace(/%/g, '')
            .trim();
        }
        return normalized;
      };

      const parameters: Record<string, unknown> = {};
      if (requiresImage && url) {
        parameters.url = url;
      }
      if (isAiEditor) {
        const prompt = buildEditorPrompt({
          rawPrompt: editorPrompt,
          marks: editorMarks,
          refUrls: editorRefs,
          mainUrl: url,
          imageSize: { width: editorImageMeta.naturalW, height: editorImageMeta.naturalH },
        });
        parameters.prompt = prompt;
        if (editorRefs.length > 0) {
          parameters.image_urls = editorRefs.join(',');
        }
      }
      for (const [k, v] of Object.entries(formParams)) {
        if (isAiEditor && (k === 'prompt' || k === 'image_urls')) continue;
        if (isShengtuWorkflow) {
          const field = toolFields.find((f) => f.name === k);
          if (field) {
            const modelAware = resolveModelAwareField(field, selectedModelValue);
            if (modelAware.disabled) continue;
          }
        }
        if (v === '') continue;
        if (isAiEditor && k === 'aspect_ratio' && String(v).trim() === 'auto') continue;
        if (isAiEditor && k === 'resolution' && String(v).trim() === '1K') continue;
        if (typeof v === 'string') {
          parameters[k] = normalizeWorkflowParam(k, v);
        } else {
          parameters[k] = v;
        }
      }
      if (isDuotuRongheWorkflow) {
        const widthRaw = String(parameters.width ?? '').trim();
        const heightRaw = String(parameters.height ?? '').trim();
        if ((!widthRaw || !heightRaw) && url) {
          const size = await loadImageSizeFromUrl(url);
          if (size) {
            if (!widthRaw) parameters.width = String(size.width);
            if (!heightRaw) parameters.height = String(size.height);
          }
        }
      }
      if (isShengtuWorkflow) {
        const parseRefs = (raw: string): string[] =>
          String(raw || '')
            .split(/[\n,]/g)
            .map((item) => item.trim())
            .filter((item) => item.length > 0);
        const refRaw = String((formParams as any)?.cankaotu ?? (formParams as any)?.image_urls ?? '');
        const refs = parseRefs(refRaw);
        if (refs.length > 0) {
          if (selectedModelValue === '3') {
            pushNotice('info', 'Seedream 4.5 不支持参考图，已自动忽略 cankaotu。');
            delete parameters.cankaotu;
            delete parameters.image_urls;
          } else {
            const packed = refs.join(',');
            parameters.cankaotu = packed;
            parameters.image_urls = packed;
          }
        }
      }
      const createdRun = await evalApi.createRun({
        workflow_version_id: selectedTool.id,
        input_oss_urls_json: requiresImage && url ? [url] : [],
        parameters_json: parameters,
      });
      setTaskRuns((prev) => [createdRun as RunWithLatest, ...prev]);
      await loadRunsForTool(selectedTool.id);
      await loadTasks();
      await refreshMetrics();
      bumpTaskRefreshWindow();
      pushNotice('success', '已提交运行，稍后会自动刷新结果');
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    } finally {
      setIsRunning(false);
    }
  };

  const runLoraBatch = async () => {
    if (batchSubmitting) return;
    if (!selectedBatchWorkflow || !selectedBatchWorkflowMeta) {
      pushNotice('error', '请先选择工作流');
      return;
    }
    if (batchFiles.length === 0) {
      pushNotice('error', '请先上传批量图片');
      return;
    }
    const repeat = Math.max(1, Math.min(20, Number(batchRepeatCount) || 1));
    const workerCount = Math.max(1, Math.min(8, Number(batchConcurrency) || 1));
    const plannedTotal = batchFiles.length * repeat;
    if (plannedTotal > LORA_BATCH_MAX_TASKS) {
      pushNotice('error', `本次计划提交 ${plannedTotal} 条，超过单批上限 ${LORA_BATCH_MAX_TASKS}。请分批执行。`);
      return;
    }
    if (batchLoraFieldName && !batchLoraValue.trim()) {
      pushNotice('error', '请先选择 LoRA');
      return;
    }
    const activeBatch = batchSessions.find((item) => !isTerminalBatchStatus(item.status));
    if (activeBatch) {
      setBatchSessionId(activeBatch.batchId);
      pushNotice('info', `当前已有进行中的批次：${activeBatch.batchId}。请先等待完成或手动停止，再创建新批次。`);
      return;
    }

    const baseParams = buildWorkflowDefaultParams(selectedBatchWorkflow);
    const effectiveParams: Record<string, string> = {
      ...baseParams,
      ...batchParamOverrides,
    };
    if (batchLoraFieldName) {
      effectiveParams[batchLoraFieldName] = batchLoraValue.trim();
    }
    const missingRequired: string[] = [];
    for (const f of getFields(selectedBatchWorkflow)) {
      if (!(f as any)?.required) continue;
      if (f.name === 'url' || f.name === 'Url') continue;
      if (isBatchSizeFieldName(f.name)) continue;
      const raw = String(effectiveParams[f.name] ?? '').trim();
      if (!raw) missingRequired.push((f as any)?.label || f.name);
    }
    if (missingRequired.length > 0) {
      pushNotice('error', `请补齐必填参数：${missingRequired.join('、')}`);
      return;
    }

    const normalizeNumericParam = (key: string, value: string): string => {
      const pixelKeys = new Set([
        'width',
        'height',
        'expand_left',
        'expand_right',
        'expand_top',
        'expand_bottom',
        'expandLeft',
        'expandRight',
        'expandTop',
        'expandBottom',
        'left',
        'right',
        'top',
        'bottom',
        'bianchang',
      ]);
      if (!pixelKeys.has(key)) return value;
      const raw = String(value || '').trim();
      if (!raw) return raw;
      let num = '';
      for (const ch of raw) {
        if (ch >= '0' && ch <= '9') {
          num += ch;
        } else if (num) {
          break;
        }
      }
      return num || raw;
    };

    const normalizedEffectiveParams: Record<string, string> = Object.fromEntries(
      Object.entries(effectiveParams).map(([key, value]) => {
        const raw = String(value ?? '');
        if (key === 'similarity' || key === 'bili') {
          return [key, raw.replace(/%/g, '').trim()];
        }
        return [key, raw];
      }),
    );

    const batchControlParams: Record<string, unknown> = {
      ...normalizedEffectiveParams,
      __batch_size_mode: batchSizeMode,
      __batch_aspect_ratio: batchAspectRatio,
      __batch_resolution: batchResolution,
      __batch_custom_width: batchCustomWidth,
      __batch_custom_height: batchCustomHeight,
      __batch_aspect_field: batchAspectField?.name || '',
      __batch_resolution_field: batchResolutionField?.name || '',
      __batch_width_field: batchWidthField?.name || '',
      __batch_height_field: batchHeightField?.name || '',
      __batch_aspect_options: batchAspectOptions.map((item) => item.value),
    };

    let currentBatchId = '';
    try {
      const created = await evalApi.createBatch({
        workflow_version_id: selectedBatchWorkflow.id,
        repeat_count: repeat,
        parameters_json: batchControlParams,
      });
      currentBatchId = String(created.id || '').trim();
      if (!currentBatchId) throw new Error('批次创建成功但未返回批次ID');
    } catch (err) {
      const msg = String((err as any)?.message || err || '');
      if (msg.startsWith('BATCH_ACTIVE_EXISTS:')) {
        const activeId = msg.split(':')[1] || '';
        if (activeId) setBatchSessionId(activeId);
        pushNotice('info', `已有进行中的批次：${activeId || '未知批次'}。请先完成或停止后再创建。`);
      } else {
        pushNotice('error', `创建批次失败：${msg}`);
      }
      return;
    }

    const plans: Array<{ key: string; file: File; fileName: string; repeatIndex: number; sourceKey: string }> = [];
    for (let i = 0; i < batchFiles.length; i += 1) {
      const file = batchFiles[i];
      for (let j = 1; j <= repeat; j += 1) {
        const relativePath = String((file as any)?.webkitRelativePath || '').trim();
        const sourceKey = relativePath
          ? `${currentBatchId}::${i + 1}::${relativePath}`
          : `${currentBatchId}::${i + 1}::${file.name}::${file.size}::${file.lastModified}`;
        plans.push({
          key: `${currentBatchId}::${i + 1}-${j}`,
          file,
          fileName: file.name,
          repeatIndex: j,
          sourceKey,
        });
      }
    }

    setBatchSessionId(currentBatchId);
    setBatchSessions((prev) => {
      if (prev.some((item) => item.batchId === currentBatchId)) return prev;
      return [
        {
          batchId: currentBatchId,
          workflowVersionId: selectedBatchWorkflow.id,
          workflowName: selectedBatchWorkflow.name,
          total: plannedTotal,
          completed: 0,
          queued: plannedTotal,
          running: 0,
          succeeded: 0,
          failed: 0,
          latestCreatedAt: new Date().toISOString(),
          latestUpdatedAt: new Date().toISOString(),
        },
        ...prev,
      ];
    });

    const newBatchItems = plans.map((item) => ({
      key: item.key,
      batchId: currentBatchId,
      sourceKey: item.sourceKey,
      fileName: item.fileName,
      repeatIndex: item.repeatIndex,
      status: 'pending' as const,
    }));
    setBatchItems((prev) => [...newBatchItems, ...prev]);

    const updateItems = (keys: string[], patch: Partial<LoraBatchItem>) => {
      const keySet = new Set(keys);
      setBatchItems((prev) => prev.map((item) => (keySet.has(item.key) ? { ...item, ...patch } : item)));
    };

    const planByFile = new Map<string, Array<{ key: string; repeatIndex: number; fileName: string; sourceKey: string }>>();
    const fileOrder: Array<{ file: File; sourceKey: string }> = [];
    for (const plan of plans) {
      const fileKey = plan.sourceKey;
      if (!planByFile.has(fileKey)) {
        planByFile.set(fileKey, []);
        fileOrder.push({ file: plan.file, sourceKey: fileKey });
      }
      planByFile.get(fileKey)!.push({
        key: plan.key,
        repeatIndex: plan.repeatIndex,
        fileName: plan.fileName,
        sourceKey: plan.sourceKey,
      });
    }

    const totalUploadFiles = fileOrder.length;
    const totalUploadBytes = fileOrder.reduce((sum, item) => sum + Math.max(0, Number(item.file.size || 0)), 0);
    batchUploadCommittedBytesRef.current = 0;
    batchUploadInFlightRef.current = new Map();
    batchUploadUploadedFilesRef.current = 0;
    batchUploadFailedFilesRef.current = 0;
    const refreshBatchUploadProgress = () => {
      let inFlightLoadedBytes = 0;
      for (const value of batchUploadInFlightRef.current.values()) {
        inFlightLoadedBytes += Math.max(0, Number(value || 0));
      }
      setBatchUploadProgress({
        batchId: currentBatchId,
        totalFiles: totalUploadFiles,
        totalBytes: totalUploadBytes,
        uploadedFiles: batchUploadUploadedFilesRef.current,
        failedFiles: batchUploadFailedFilesRef.current,
        activeFiles: batchUploadInFlightRef.current.size,
        uploadedBytes: batchUploadCommittedBytesRef.current + inFlightLoadedBytes,
      });
    };
    refreshBatchUploadProgress();

    const fileSizeMap = new Map<string, { width: number; height: number } | null>();
    await Promise.all(
      fileOrder.map(async ({ file, sourceKey }) => {
        const size = await loadImageSizeFromFile(file);
        fileSizeMap.set(sourceKey, size);
      }),
    );

    batchStopRef.current = false;
    setBatchSubmitting(true);

    const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
    const uploadWithRetry = async (file: File, sourceKey: string) => {
      const maxAttempts = 2;
      let lastErr: unknown = null;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        if (batchStopRef.current) {
          throw new Error('已手动停止');
        }
        try {
          const uploaded = await evalApi.uploadImage(file, {
            onProgress: (loaded) => {
              batchUploadInFlightRef.current.set(sourceKey, Math.min(Math.max(0, loaded || 0), Math.max(1, file.size || 1)));
              refreshBatchUploadProgress();
            },
          });
          batchUploadInFlightRef.current.delete(sourceKey);
          batchUploadCommittedBytesRef.current += Math.max(0, Number(file.size || 0));
          batchUploadUploadedFilesRef.current += 1;
          refreshBatchUploadProgress();
          return uploaded;
        } catch (err) {
          lastErr = err;
          batchUploadInFlightRef.current.delete(sourceKey);
          refreshBatchUploadProgress();
          if (attempt < maxAttempts) {
            await sleep(500 * attempt);
          }
        }
      }
      batchUploadFailedFilesRef.current += 1;
      refreshBatchUploadProgress();
      throw lastErr;
    };
    const upsertAssetsWithRetry = async (items: Array<Record<string, unknown>>) => {
      const maxAttempts = 3;
      let lastErr: unknown = null;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          await evalApi.upsertBatchAssets(currentBatchId, { items: items as any });
          return;
        } catch (err) {
          lastErr = err;
          if (attempt < maxAttempts) {
            await sleep(300 * attempt);
          }
        }
      }
      throw new Error(`任务登记失败: ${String((lastErr as any)?.message || lastErr || '未知错误')}`);
    };

    const uploadedSourceMap = new Map<string, { inputUrl: string; imageSize: { width: number; height: number } | null; fileName: string }>();
    let uploadCursor = 0;
    const nextUploadFile = (): { file: File; sourceKey: string } | null => {
      if (uploadCursor >= fileOrder.length) return null;
      const entry = fileOrder[uploadCursor];
      uploadCursor += 1;
      return entry;
    };

    const runUploadWorker = async () => {
      while (!batchStopRef.current) {
        const fileEntry = nextUploadFile();
        if (!fileEntry) break;
        const file = fileEntry.file;
        const fileKey = fileEntry.sourceKey;
        const imageSize = fileSizeMap.get(fileKey) || null;
        const filePlans = (planByFile.get(fileKey) || []).sort((a, b) => a.repeatIndex - b.repeatIndex);
        const keys = filePlans.map((item) => item.key);
        const fileName = filePlans[0]?.fileName || file.name || 'unnamed';
        updateItems(keys, { status: 'uploading', error: undefined, runError: undefined });
        try {
          const upload = await uploadWithRetry(file, fileKey);
          const inputUrl = String(upload.url || '').trim();
          if (!inputUrl) throw new Error('上传成功但未返回 URL');
          uploadedSourceMap.set(fileKey, { inputUrl, imageSize, fileName });
          updateItems(keys, { status: 'pending', inputUrl, error: undefined, failureStage: undefined });
          await upsertAssetsWithRetry([
            {
              source_key: fileKey,
              file_name: fileName,
              oss_url: inputUrl,
              object_key: String(upload.objectKey || ''),
              size_bytes: Number(file.size || 0),
              width: imageSize?.width || undefined,
              height: imageSize?.height || undefined,
              upload_status: 'uploaded',
            },
          ]);
        } catch (err) {
          const errMsg = String((err as any)?.message || err || '上传失败');
          updateItems(keys, {
            status: 'failed',
            failureStage: 'upload',
            error: errMsg,
          });
          try {
            await upsertAssetsWithRetry([
              {
                source_key: fileKey,
                file_name: fileName,
                size_bytes: Number(file.size || 0),
                width: imageSize?.width || undefined,
                height: imageSize?.height || undefined,
                upload_status: 'failed',
                upload_error_code: 'BATCH_ASSET_UPLOAD_FAILED',
                upload_error_message: errMsg,
              },
            ]);
          } catch (saveErr) {
            updateItems(keys, { error: `${errMsg}；失败状态回写失败：${String((saveErr as any)?.message || saveErr || '')}` });
          }
        }
      }
    };

    let enteredSubmitPhase = false;
    try {
      // 阶段一：先把素材上传完，再进入任务提交，避免上传波动影响任务创建一致性。
      await Promise.all(Array.from({ length: workerCount }, () => runUploadWorker()));
      const uploadedCount = uploadedSourceMap.size;
      const failedUploads = Math.max(0, totalUploadFiles - uploadedCount);
      if (batchStopRef.current) {
        pushNotice('info', '批量任务已停止');
      } else if (uploadedCount <= 0) {
        pushNotice('error', '素材上传全部失败，未创建任何任务');
      } else {
        if (failedUploads > 0) {
          pushNotice('info', `素材上传完成：成功 ${uploadedCount} 张，失败 ${failedUploads} 张，失败素材已跳过`);
        } else {
          pushNotice('success', `素材上传完成：${uploadedCount} 张，开始提交任务`);
        }
        // 阶段二：仅对上传成功的素材创建任务。
        enteredSubmitPhase = true;
        const uploadedKeySet = new Set<string>(Array.from(uploadedSourceMap.keys()));
        setBatchItems((prev) =>
          prev.map((item) => {
            if (item.batchId !== currentBatchId) return item;
            if (item.status !== 'pending') return item;
            if (!uploadedKeySet.has(String(item.sourceKey || ''))) return item;
            return { ...item, status: 'submitting', error: undefined };
          }),
        );
        const submitResult = await evalApi.submitBatch(currentBatchId, { only_pending: true });
        if (Number(submitResult.failed_items || 0) > 0) {
          pushNotice(
            'info',
            `任务创建完成：已提交 ${Number(submitResult.submitted_items || 0)} 条，失败 ${Number(submitResult.failed_items || 0)} 条`,
          );
        }
      }
      if (batchStopRef.current) {
        try {
          await evalApi.stopRunBatch(currentBatchId);
        } catch {
          // ignore
        }
        setBatchItems((prev) =>
          prev.map((item) =>
            item.batchId === currentBatchId &&
            (item.status === 'pending' || item.status === 'uploading' || item.status === 'submitting')
              ? { ...item, status: 'failed', failureStage: 'submit', error: '已手动停止（未提交）' }
              : item,
          ),
        );
        pushNotice('info', '批量提交已停止');
      } else if (enteredSubmitPhase) {
        pushNotice('success', '批量提交完成，系统会自动刷新执行进度');
      }
      await loadBatchSessions();
      await loadBatchItems(currentBatchId, { silent: true });
      await loadTasks();
      bumpTaskRefreshWindow(30);
    } catch (err) {
      pushNotice('error', String((err as any)?.message || err || '批量提交失败'));
    } finally {
      setBatchSubmitting(false);
    }
  };

  const persistBatchReview = useCallback(
    async (batchId: string, key: string, review: LoraBatchReview) => {
      const parsed = parseBatchReviewKey(key);
      if (!parsed) return;
      const reason = String(review.reason || '').trim();
      const note = String(review.note || '').trim();
      const verdict: LoraBatchReviewVerdict =
        review.verdict === 'satisfied' || review.verdict === 'unsatisfied' ? review.verdict : 'pending';
      try {
        await evalApi.upsertBatchOutputReviews(batchId, {
          items: [
            {
              run_item_id: parsed.runItemId,
              output_index: parsed.outputIndex,
              verdict,
              reason: reason || undefined,
              note: note || undefined,
            },
          ],
        });
        batchReviewSaveErrorKeysRef.current.delete(key);
      } catch (err) {
        if (!batchReviewSaveErrorKeysRef.current.has(key)) {
          batchReviewSaveErrorKeysRef.current.add(key);
          pushNotice('error', `标注保存失败：${String((err as any)?.message || err || '未知错误')}`);
        }
      }
    },
    [pushNotice],
  );

  const queuePersistBatchReview = useCallback(
    (batchId: string, key: string, review: LoraBatchReview) => {
      if (!batchId) return;
      const timers = batchReviewSaveTimersRef.current;
      const prevTimer = timers.get(key);
      if (prevTimer) window.clearTimeout(prevTimer);
      const timer = window.setTimeout(() => {
        timers.delete(key);
        void persistBatchReview(batchId, key, review);
      }, 450);
      timers.set(key, timer);
    },
    [persistBatchReview],
  );

  const updateBatchReview = useCallback(
    (key: string, patch: Partial<LoraBatchReview>) => {
      const batchId = String(selectedBatchId || '').trim();
      setBatchReviewMap((prev) => {
        const current: LoraBatchReview = prev[key] || { verdict: 'pending' };
        const next: LoraBatchReview = {
          ...current,
          ...patch,
        };
        if (batchId) queuePersistBatchReview(batchId, key, next);
        return {
          ...prev,
          [key]: next,
        };
      });
    },
    [queuePersistBatchReview, selectedBatchId],
  );

  const flushPendingBatchReviewSaves = useCallback(async () => {
    const tasks: Promise<void>[] = [];
    const timers = batchReviewSaveTimersRef.current;
    const pendingEntries = Array.from(timers.entries());
    for (const [key, timer] of pendingEntries) {
      window.clearTimeout(timer);
      timers.delete(key);
      const review = batchReviewMapRef.current[key];
      const batchId = String(selectedBatchId || '').trim();
      if (!batchId || !review) continue;
      tasks.push(persistBatchReview(batchId, key, review));
    }
    if (tasks.length > 0) {
      await Promise.all(tasks);
    }
  }, [persistBatchReview, selectedBatchId]);

  const jumpToBatchReviewPage = useCallback(
    async (targetPage: number) => {
      const batchId = String(selectedBatchId || '').trim();
      if (!batchId) return;
      const normalized = Math.max(1, Math.min(Math.max(1, batchReviewTotalPages || 1), Math.floor(targetPage)));
      setBatchReviewPageJumping(true);
      try {
        await flushPendingBatchReviewSaves();
        await saveBatchReviewProgress(
          batchId,
          {
            currentPage: normalized,
            completedPage: Math.min(batchReviewProgress.completedPage, normalized),
          },
          { silent: true },
        );
        await loadBatchReviewGroups(batchId, normalized, { silent: true });
      } finally {
        setBatchReviewPageJumping(false);
      }
    },
    [
      selectedBatchId,
      batchReviewTotalPages,
      flushPendingBatchReviewSaves,
      saveBatchReviewProgress,
      batchReviewProgress.completedPage,
      loadBatchReviewGroups,
    ],
  );

  const completeBatchReviewPage = useCallback(async () => {
    const batchId = String(selectedBatchId || '').trim();
    if (!batchId) return;
    if (batchReviewTotalPages <= 0) return;
    setBatchReviewProgressSaving(true);
    try {
      await flushPendingBatchReviewSaves();
      const currentPage = Math.max(1, Number(batchReviewPage || 1));
      const nextCompleted = Math.max(Number(batchReviewProgress.completedPage || 0), currentPage);
      const nextPage = currentPage < batchReviewTotalPages ? currentPage + 1 : currentPage;
      await saveBatchReviewProgress(batchId, { currentPage: nextPage, completedPage: nextCompleted }, { silent: true });
      await loadBatchReviewGroups(batchId, nextPage, { silent: true });
      if (nextPage !== currentPage) {
        pushNotice('success', `第 ${currentPage} 页已完成，已进入第 ${nextPage} 页`);
      } else {
        pushNotice('success', '本批次已标注到最后一页');
      }
    } catch (err) {
      pushNotice('error', `提交本页完成失败：${String((err as any)?.message || err || '未知错误')}`);
    } finally {
      setBatchReviewProgressSaving(false);
    }
  }, [
    selectedBatchId,
    batchReviewTotalPages,
    flushPendingBatchReviewSaves,
    batchReviewPage,
    batchReviewProgress.completedPage,
    saveBatchReviewProgress,
    loadBatchReviewGroups,
    pushNotice,
  ]);

  const stopSelectedBatch = useCallback(async () => {
    if (!selectedBatchId) {
      pushNotice('error', '请先选择要停止的批次');
      return;
    }
    if (!window.confirm(`确认停止批次 ${selectedBatchId} 的未完成任务吗？`)) return;
    setBatchStopping(true);
    try {
      const res = await evalApi.stopRunBatch(selectedBatchId);
      pushNotice('success', `已停止：评测任务 ${res.stoppedRuns} 条，能力任务 ${res.stoppedTasks} 条`);
      await loadBatchSessions();
      await loadBatchItems(selectedBatchId, { silent: true });
    } catch (err) {
      pushNotice('error', `停止批次失败：${String((err as any)?.message || err || '')}`);
    } finally {
      setBatchStopping(false);
    }
  }, [selectedBatchId, loadBatchSessions, loadBatchItems, pushNotice]);

  const exportBatchComparisonCsv = useCallback(
    async (onlyUnsatisfied: boolean) => {
      const batchId = String(selectedBatchId || '').trim();
      if (!batchId) {
        pushNotice('error', '请先选择批次');
        return;
      }
      setBatchExporting(onlyUnsatisfied ? 'unsatisfied' : 'all');
      try {
        await flushPendingBatchReviewSaves();
        const rows: string[][] = [];
        rows.push([
          'batch_id',
          'workflow_id',
          'workflow_name',
          'lora',
          'source_file_name',
          'source_image_url',
          'repeat_index',
          'run_id',
          'run_status',
          'output_index',
          'output_url',
          'prompt',
          'verdict',
          'reason',
          'note',
          'run_error',
        ]);
        const pushRow = (cols: string[]) => rows.push(cols.map((v) => (v == null ? '' : String(v))));

        const firstPage = await evalApi.listBatchReviewGroups(batchId, { page: 1, page_size: 20 });
        const totalPages = Math.max(0, Number(firstPage.total_pages || 0));
        const completedPage = Math.max(0, Number(firstPage.review_progress?.completed_page || 0));

        const consumePage = (resp: Awaited<ReturnType<typeof evalApi.listBatchReviewGroups>>, pageNo: number) => {
          const pageDone = pageNo <= completedPage;
          for (const group of Array.isArray(resp.items) ? resp.items : []) {
            const outputs = Array.isArray(group.outputs) ? group.outputs : [];
            if (outputs.length === 0) {
              if (onlyUnsatisfied) continue;
              pushRow([
                batchId,
                String(selectedBatchSession?.workflowVersionId || ''),
                String(selectedBatchSession?.workflowName || ''),
                String(batchLoraValue || ''),
                String(group.file_name || ''),
                String(group.input_url || ''),
                '',
                '',
                String(group.group_status || ''),
                '',
                '',
                '',
                '无结果',
                '',
                '',
                String(group.last_error || ''),
              ]);
              continue;
            }
            for (const output of outputs) {
              const reviewRaw = String(output.review?.verdict || '').trim().toLowerCase();
              const isUnsatisfied = reviewRaw === 'unsatisfied';
              if (onlyUnsatisfied && !isUnsatisfied) continue;
              const verdictLabel = isUnsatisfied ? '不满意' : pageDone ? '满意(默认)' : '未标注';
              pushRow([
                batchId,
                String(selectedBatchSession?.workflowVersionId || ''),
                String(selectedBatchSession?.workflowName || ''),
                String(batchLoraValue || ''),
                String(group.file_name || ''),
                String(group.input_url || ''),
                '',
                String(output.run_id || ''),
                String(output.run_status || ''),
                String(output.output_index || ''),
                String(output.url || ''),
                '',
                verdictLabel,
                isUnsatisfied ? String(output.review?.reason || '') : '',
                isUnsatisfied ? String(output.review?.note || '') : '',
                String(group.last_error || ''),
              ]);
            }
          }
        };

        if (totalPages === 0) {
          consumePage(firstPage, 1);
        } else {
          consumePage(firstPage, 1);
          for (let pageNo = 2; pageNo <= totalPages; pageNo += 1) {
            const pageResp = await evalApi.listBatchReviewGroups(batchId, { page: pageNo, page_size: 20 });
            consumePage(pageResp, pageNo);
          }
        }
        if (onlyUnsatisfied && rows.length <= 1) {
          pushNotice('info', '当前批次暂无“不满意”记录，未导出文件');
          return;
        }

        const escapeCsv = (value: string) => {
          const s = String(value || '');
          if (s.includes(',') || s.includes('"') || s.includes('\n')) {
            return `"${s.replace(/"/g, '""')}"`;
          }
          return s;
        };
        const csv = rows.map((r) => r.map(escapeCsv).join(',')).join('\n');
        const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const dt = new Date();
        const stamp = `${dt.getFullYear()}${String(dt.getMonth() + 1).padStart(2, '0')}${String(dt.getDate()).padStart(2, '0')}_${String(dt.getHours()).padStart(2, '0')}${String(dt.getMinutes()).padStart(2, '0')}${String(dt.getSeconds()).padStart(2, '0')}`;
        a.href = url;
        a.download = onlyUnsatisfied ? `lora_batch_unsatisfied_${stamp}.csv` : `lora_batch_comparison_${stamp}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        pushNotice('success', onlyUnsatisfied ? '已导出不满意样本 CSV' : '已导出对照集 CSV');
      } catch (err) {
        pushNotice('error', `导出失败：${String((err as any)?.message || err || '未知错误')}`);
      } finally {
        setBatchExporting('');
      }
    },
    [selectedBatchId, flushPendingBatchReviewSaves, selectedBatchSession, batchLoraValue, pushNotice],
  );

  const annotate = async (runId: string, rating: number, comment: string) => {
    try {
      await evalApi.createAnnotation(runId, { rating, comment: comment.trim() || undefined });
      await refreshMetrics();
      if (selectedTool) await loadRunsForTool(selectedTool.id);
      pushNotice('success', '已保存评分/备注');
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const filteredRuns = useMemo(() => {
    let out = toolRuns.slice();
    if (historyFocus === 'no_output') {
      out = out.filter((r) => isSucceededWithoutVisibleOutput(r));
    } else if (historyFocus === 'failed') {
      out = out.filter((r) => String(r.status || '').toLowerCase() === 'failed');
    } else if (historyFocus === 'running') {
      out = out.filter((r) => ['queued', 'running'].includes(String(r.status || '').toLowerCase()));
    } else if (historyFocus === 'succeeded') {
      out = out.filter((r) => ['succeeded', 'success', 'completed'].includes(String(r.status || '').toLowerCase()));
    }
    if (filterStatus !== 'all') {
      out = out.filter((r) => {
        const status = String(r.status || '').toLowerCase();
        if (filterStatus === 'succeeded') return ['succeeded', 'success', 'completed'].includes(status);
        if (filterStatus === 'queued') return status === 'queued';
        if (filterStatus === 'running') return status === 'running';
        return status === filterStatus;
      });
    }
    if (filterRating !== 'all') {
      const target = Number(filterRating);
      out = out.filter((r) => r.latest_annotation?.rating === target);
    }
    if (filterUnrated) {
      out = out.filter((r) => !r.latest_annotation?.rating);
    }
    const keyword = search.trim().toLowerCase();
    if (keyword) {
      out = out.filter((r) => {
        const comment = (r.latest_annotation?.comment || '').toLowerCase();
        const err = (r.error_message || '').toLowerCase();
        return comment.includes(keyword) || err.includes(keyword);
      });
    }
    return out;
  }, [toolRuns, historyFocus, filterStatus, filterRating, filterUnrated, search]);

  const historySummary = useMemo(() => {
    const isSuccess = (run: EvalRun) => ['succeeded', 'success', 'completed'].includes(String(run.status || '').toLowerCase());
    const isRunning = (run: EvalRun) => ['queued', 'running'].includes(String(run.status || '').toLowerCase());
    return {
      total: toolRuns.length,
      shown: filteredRuns.length,
      success: toolRuns.filter(isSuccess).length,
      failed: toolRuns.filter((run) => String(run.status || '').toLowerCase() === 'failed').length,
      running: toolRuns.filter(isRunning).length,
      noOutput: toolRuns.filter((run) => isSucceededWithoutVisibleOutput(run)).length,
      unrated: toolRuns.filter((run) => !run.latest_annotation?.rating).length,
    };
  }, [toolRuns, filteredRuns.length]);

  const promptAdminToken = useCallback(
    async (opts?: { force?: boolean }) => {
      const force = Boolean(opts?.force);
      const tokenInput =
        (!force && adminToken) || window.prompt('请输入 EVAL_ADMIN_TOKEN（仅管理员维护功能名/备注）') || '';
      if (!tokenInput.trim()) return;
      const token = tokenInput.trim();
      localStorage.setItem('podi_eval_admin_token', token);
      setAdminToken(token);
      setActiveView('admin');
      setSelectedTool(null);
      try {
        await loadAdminWorkflowList(token);
        pushNotice('success', '已加载维护列表');
      } catch (err) {
        console.error(err);
        pushNotice('error', String((err as any)?.message || err));
      }
    },
    [adminToken, loadAdminWorkflowList, pushNotice],
  );

  const promptOperationsHealthToken = useCallback(async () => {
    const tokenInput = adminToken || window.prompt('请输入 EVAL_ADMIN_TOKEN（用于查看链路健康）') || '';
    const token = tokenInput.trim();
    if (!token) return;
    localStorage.setItem('podi_eval_admin_token', token);
    setAdminToken(token);
    try {
      await Promise.all([loadOperationsHealth(token), loadComfyuiQueueSummary(token)]);
      pushNotice('success', '已刷新链路健康');
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  }, [adminToken, loadComfyuiQueueSummary, loadOperationsHealth, pushNotice]);

  const openAdmin = useCallback(async () => {
    void promptAdminToken();
  }, [promptAdminToken]);

  const headerNavValue = activeView === 'tool' ? 'home' : activeView;
  const showCategorySidebar = activeView === 'home' || activeView === 'tool';
  const shell = (content: ReactNode) => (
    <ConfigProvider globalConfig={zhCN}>
      <EvalShell
        title="PODI · 能力评测"
        subtitle="评测执行台 · 结果沉淀 · 任务追踪"
        theme={theme}
        showSidebar={showCategorySidebar}
        sidebarTitle="功能分类"
        sidebarSubtitle="仅在“功能评测”模块使用，用于筛选能力卡片。"
        navItems={orderedCategories.map((cat) => ({
          id: cat,
          label: cat,
          shortLabel: String(cat || "评测").slice(0, 2),
          icon: getCategoryNavIcon(cat),
          count: (grouped[cat] || []).length,
        }))}
        activeNav={activeCategory}
        onSelectNav={(next) => {
          setActiveCategory(next);
          setSelectedTool(null);
          setActiveView('home');
        }}
        headerTabs={
          <Tabs
            value={headerNavValue}
            onChange={(v) => {
              const next = String(v) as EvalView | 'admin';
              if (next === 'admin') {
                void openAdmin();
                return;
              }
              setActiveView(next as EvalView);
              setSelectedTool(null);
            }}
          >
            <Tabs.TabPanel value="home" label="功能评测" />
            <Tabs.TabPanel value="loraBatch" label="批量回归" />
            <Tabs.TabPanel value="tasks" label="任务追踪" />
            <Tabs.TabPanel value="docs" label="接口文档" />
            <Tabs.TabPanel value="admin" label="维护配置" />
          </Tabs>
        }
        headerActions={
          <>
            <Button variant="outline" onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}>
              {theme === 'dark' ? '深色' : '浅色'}
            </Button>
            <Typography.Text theme="secondary">
              raterId: <span style={{ fontFamily: 'monospace' }}>{raterId || '...'}</span>
            </Typography.Text>
          </>
        }
      >
        {content}
      </EvalShell>
      <Lightbox url={lightbox?.url || ''} title={lightbox?.title} onClose={() => setLightbox(null)} />
    </ConfigProvider>
  );

  if (activeView === 'admin') {
    return shell(
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>功能维护</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  维护各功能的名称/备注/分类/状态（需要 `EVAL_ADMIN_TOKEN`）。
                </Typography.Text>
              </div>
            </div>
            <Button
              variant="outline"
              disabled={!adminToken}
              onClick={async () => {
                if (!adminToken) return;
                await loadAdminWorkflowList(adminToken, { notifySuccess: true });
              }}
            >
              刷新列表
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void promptAdminToken({ force: true });
              }}
            >
              重新输入 Token
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {adminWorkflowStatus === 'loading' ? <Alert theme="info" message="正在加载维护功能列表…" /> : null}
          {adminWorkflowStatus === 'error' ? (
            <WorkflowListErrorState scope="admin" error={adminWorkflowError} onRetry={() => void loadAdminWorkflowList(adminToken)} />
          ) : null}
          {adminWorkflows.map((wf) => (
            <AdminWorkflowRow
              key={wf.id}
              wf={wf}
              adminToken={adminToken}
              onAuthInvalid={() => {
                localStorage.removeItem('podi_eval_admin_token');
                setAdminToken('');
                pushNotice('error', '认证已失效，请重新输入 EVAL_ADMIN_TOKEN');
              }}
              onSaved={(next) => {
                setAdminWorkflows((prev) => prev.map((x) => (x.id === next.id ? next : x)));
              }}
            />
          ))}
          {adminWorkflowStatus === 'success' && adminWorkflows.length === 0 ? (
            <Typography.Text theme="secondary">暂无数据。</Typography.Text>
          ) : null}
        </Space>
      </Card>,
    );
  }

  if (activeView === 'docs') {

    const paramColumns = [
      {
        colKey: 'name',
        title: '字段',
        cell: ({ row }: { row: SchemaField }) => (
          <Space direction="vertical" size={2}>
            <Typography.Text code>{row.name}</Typography.Text>
            {row.label ? (
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {row.label}
              </Typography.Text>
            ) : null}
          </Space>
        ),
      },
      {
        colKey: 'required',
        title: '必填',
        width: 70,
        cell: ({ row }: { row: SchemaField }) => (row.required ? '是' : '否'),
      },
      {
        colKey: 'type',
        title: '类型',
        width: 110,
        cell: ({ row }: { row: SchemaField }) => <Typography.Text code>{row.type || 'text'}</Typography.Text>,
      },
      {
        colKey: 'defaultValue',
        title: '默认值',
        width: 140,
        cell: ({ row }: { row: SchemaField }) => (row.defaultValue ? String(row.defaultValue) : '—'),
      },
      {
        colKey: 'options',
        title: '枚举值',
        cell: ({ row }: { row: SchemaField }) => renderOptionTags(row.options),
      },
      {
        colKey: 'description',
        title: '说明',
        cell: ({ row }: { row: SchemaField }) => (row.description ? row.description : '—'),
      },
    ];

    const outputColumns = [
      {
        colKey: 'name',
        title: '字段',
        cell: ({ row }: { row: SchemaField }) => (
          <Space direction="vertical" size={2}>
            <Typography.Text code>{row.name}</Typography.Text>
            {row.label ? (
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {row.label}
              </Typography.Text>
            ) : null}
          </Space>
        ),
      },
      {
        colKey: 'type',
        title: '类型',
        width: 110,
        cell: ({ row }: { row: SchemaField }) => <Typography.Text code>{row.type || 'text'}</Typography.Text>,
      },
      {
        colKey: 'description',
        title: '说明',
        cell: ({ row }: { row: SchemaField }) => (row.description ? row.description : '—'),
      },
    ];

    return shell(
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>开发文档 · Coze 工作流</Typography.Text>
              <div>
                      <Typography.Text theme="secondary">
                        从后端自动生成（active 工作流 + 入参/出参 schema）。
                        {docsGeneratedAt ? `生成时间：${fmtTime(docsGeneratedAt)}` : ''}
                      </Typography.Text>
              </div>
            </div>
            <Space align="center">
              <Button
                variant={docsView === 'structured' ? 'base' : 'outline'}
                onClick={() => setDocsView('structured')}
              >
                结构化
              </Button>
              <Button variant={docsView === 'markdown' ? 'base' : 'outline'} onClick={() => setDocsView('markdown')}>
                Markdown
              </Button>
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(docsMarkdown || '');
                    pushNotice('success', '已复制到剪贴板');
                  } catch (err) {
                    console.error(err);
                    pushNotice('error', '复制失败（浏览器不支持或权限不足）');
                  }
                }}
              >
                复制全文
              </Button>
            </Space>
          </Space>
        }
      >
        {docsLoading ? (
          <Typography.Text theme="secondary">加载中…</Typography.Text>
        ) : (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Alert
              theme="info"
              message="统一联调准则：状态只按“排队中、执行中、成功、失败”判断；队列满会给出明确错误码；成功但暂未回填图片时按“结果回填中”处理，不要直接判失败。"
            />
          {docsView === 'structured' && groupedDocs.length > 0 ? (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card bordered>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text strong>目录</Typography.Text>
                <Space style={{ flexWrap: 'wrap' }}>
                  {groupedDocs.map((group) => (
                    <a
                      key={group.category}
                      href={`#${toAnchorId(group.category)}`}
                      style={{ color: 'var(--td-text-color-primary)' }}
                    >
                      {group.category}（{group.items.length}）
                    </a>
                  ))}
                </Space>
              </Space>
            </Card>

            {groupedDocs.map((group) => (
              <Space key={group.category} direction="vertical" size="large" style={{ width: '100%' }}>
                <div id={toAnchorId(group.category)}>
                  <Typography.Title level="h3" style={{ margin: 0 }}>
                    {group.category}
                  </Typography.Title>
                </div>

                {group.items.map((wf) => {
                  const params = Array.isArray(wf.parameters) ? wf.parameters : [];
                  const outputs = Array.isArray(wf.outputs) ? wf.outputs : [];
                  const errors = Array.isArray(wf.errors) ? wf.errors : [];
                  const requestBody =
                    wf.request?.body ?? {
                      workflow_id: wf.workflow_id,
                      parameters: {},
                    };
                  const requestJson = JSON.stringify(requestBody, null, 2);
                  const requestPath = wf.request?.path || '/v1/workflow/run';
                  const requestMethod = wf.request?.method || 'POST';
                  const missingParams = params.length === 0;
                  const missingOutputs = outputs.length === 0;
                  const missingSchemaLabels = [
                    missingParams ? 'parameters_schema' : null,
                    missingOutputs ? 'output_schema' : null,
                  ].filter(Boolean);

                  return (
                    <Card key={wf.workflow_id} bordered>
                      <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                        <Space align="center" style={{ flexWrap: 'wrap' }}>
                          <Typography.Title level="h4" style={{ margin: 0 }}>
                            {wf.name}
                          </Typography.Title>
                          <Tag variant="light">输出类型: {wf.output_kind || 'image_url'}</Tag>
                        </Space>
                        <Typography.Text theme="secondary">workflow_id: {wf.workflow_id}</Typography.Text>
                        {wf.notes ? <Typography.Text>备注：{wf.notes}</Typography.Text> : null}
                        {missingSchemaLabels.length > 0 ? (
                          <Alert
                            theme="warning"
                            message={`Schema 缺失：${missingSchemaLabels.join(' / ')}。请在评测管理端补齐，避免文档与表单不完整。`}
                          />
                        ) : null}

                        <Space direction="vertical" size={4}>
                          <Typography.Text strong>调用方式</Typography.Text>
                          <Typography.Text theme="secondary">
                            {requestMethod} {requestPath}
                          </Typography.Text>
                          <pre
                            style={{
                              border: '1px solid var(--td-border-level-1-color)',
                              background: 'var(--td-bg-color-secondarycontainer)',
                              borderRadius: 8,
                              padding: 12,
                              fontFamily: 'monospace',
                              fontSize: 12,
                              whiteSpace: 'pre-wrap',
                              margin: 0,
                            }}
                          >
                            {requestJson}
                          </pre>
                        </Space>

                        <Space direction="vertical" size={4}>
                          <Typography.Text strong>入参 parameters</Typography.Text>
                          {params.length > 0 ? (
                            <Table rowKey="name" data={params} columns={paramColumns} size="small" bordered />
                          ) : (
                            <Typography.Text theme="secondary">无参数</Typography.Text>
                          )}
                        </Space>

                        <Space direction="vertical" size={4}>
                          <Typography.Text strong>出参 data</Typography.Text>
                          {outputs.length > 0 ? (
                            <Table rowKey="name" data={outputs} columns={outputColumns} size="small" bordered />
                          ) : (
                            <Typography.Text theme="secondary">默认关注 data.output（图片 URL 或回调 task id）</Typography.Text>
                          )}
                        </Space>

                        <Space direction="vertical" size={4}>
                          <Typography.Text strong>错误码</Typography.Text>
                          {errors.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: 20 }}>
                              {errors.map((item, idx) => (
                                <li key={`${wf.workflow_id}-err-${idx}`}>
                                  <Typography.Text theme="secondary">{item}</Typography.Text>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <Typography.Text theme="secondary">详见“Markdown”视图中的错误码总表。</Typography.Text>
                          )}
                        </Space>
                      </Space>
                    </Card>
                  );
                })}
              </Space>
            ))}
          </Space>
          ) : docsMarkdown ? (
          <div
            style={{
              maxHeight: '70vh',
              overflow: 'auto',
              border: '1px solid var(--td-border-level-1-color)',
              background: 'var(--td-bg-color-secondarycontainer)',
              borderRadius: 8,
              padding: 12,
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <Typography.Title level="h3">{children}</Typography.Title>,
                h2: ({ children }) => <Typography.Title level="h4">{children}</Typography.Title>,
                h3: ({ children }) => <Typography.Title level="h5">{children}</Typography.Title>,
                p: ({ children }) => <Typography.Paragraph>{children}</Typography.Paragraph>,
                code: ({ children }) => (
                  <code style={{ background: 'var(--td-bg-color-secondarycontainer)', padding: '0 4px', borderRadius: 4 }}>
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre
                    style={{
                      background: 'var(--td-bg-color-secondarycontainer)',
                      padding: 12,
                      borderRadius: 8,
                      overflow: 'auto',
                      fontSize: 12,
                    }}
                  >
                    {children}
                  </pre>
                ),
                table: ({ children }) => (
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 12 }}>{children}</table>
                ),
                th: ({ children }) => (
                  <th style={{ border: '1px solid var(--td-border-level-1-color)', padding: 6, textAlign: 'left' }}>
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td style={{ border: '1px solid var(--td-border-level-1-color)', padding: 6 }}>{children}</td>
                ),
                ul: ({ children }) => <ul style={{ paddingLeft: 20 }}>{children}</ul>,
                ol: ({ children }) => <ol style={{ paddingLeft: 20 }}>{children}</ol>,
              }}
            >
              {docsMarkdown}
            </ReactMarkdown>
          </div>
          ) : (
          <Typography.Text theme="secondary">暂无文档内容。</Typography.Text>
          )}
          </Space>
        )}
      </Card>,
    );
  }

  if (activeView === 'tasks') {
    return shell(<TaskTable runs={taskRuns} workflowMap={workflowMap} />);
  }

  if (activeView === 'loraBatch') {
    const workflowOptions = loraBatchWorkflows.map((item) => ({
      label: `${item.workflow.name}（${item.workflow.workflow_id}）`,
      value: item.workflow.id,
    }));
    const loraOptions = selectedBatchWorkflowMeta?.loraOptions || [];
    const selectedLoraLabel =
      loraOptions.find((opt) => opt.value === batchLoraValue)?.label || batchLoraValue || '—';
    return shell(
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card bordered>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Title level="h4" style={{ margin: 0 }}>
              LoRA 批量回归测试
            </Typography.Title>
            <Typography.Text theme="secondary">
              独立于左侧 5 个业务分类。用于批量验证“含 LoRA 的工作流”在多素材上的覆盖表现。
            </Typography.Text>
            <Typography.Text theme="secondary">
              规则：一次“上传+点击提交”就是一个测试任务（批次）；每张图会按“测试次数”重复提交，降低单次随机性影响。单批上限 {LORA_BATCH_MAX_TASKS} 条。
            </Typography.Text>
            <Typography.Text theme="secondary">
              执行顺序：先完成整批素材上传，再统一创建任务；上传失败素材会被自动跳过并标记失败，避免网络抖动影响任务创建一致性。
            </Typography.Text>
          </Space>
        </Card>
        <StepGuide
          title="批测流程"
          hint="按固定流程执行，便于业务同学复盘问题和导出结果。"
          steps={[
            { title: '选择工作流与 LoRA', description: '先确认工作流版本、LoRA 和重复次数。' },
            { title: '生成任务', description: '先完成整批素材上传，再统一创建任务。' },
            { title: '等待批次结束', description: '批次结束后再进入标注，避免页面抖动。' },
            { title: '结果标注', description: '仅标记不满意，按页完成并断点续标。' },
          ]}
        />
        <Card bordered>
          <Tabs value={loraBatchSubView} onChange={(v) => setLoraBatchSubView(String(v) as LoraBatchSubView)}>
            <Tabs.TabPanel value="generation" label="生成任务" />
            <Tabs.TabPanel value="annotation" label="结果标注" />
          </Tabs>
        </Card>

        {loraBatchSubView === 'generation' ? (
        <Row gutter={[12, 12]}>
          <Col xs={12} xl={5}>
            <Card bordered title="批测参数">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>
                    工作流 <Typography.Text theme="error">*</Typography.Text>
                  </Typography.Text>
                  <Select
                    value={batchWorkflowId}
                    options={workflowOptions}
                    onChange={(v) => {
                      setBatchWorkflowId(String(v));
                    }}
                    placeholder={workflowOptions.length === 0 ? '暂无可批测工作流' : '请选择工作流'}
                    disabled={workflowOptions.length === 0 || batchSubmitting}
                  />
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>
                    LoRA <Typography.Text theme="error">*</Typography.Text>
                  </Typography.Text>
                  {loraOptions.length > 0 ? (
                    <Select
                      value={batchLoraValue}
                      options={loraOptions}
                      onChange={(v) => setBatchLoraValue(String(v))}
                      placeholder="请选择 LoRA"
                      disabled={batchSubmitting}
                    />
                  ) : (
                    <Input
                      value={batchLoraValue}
                      onChange={(v) => setBatchLoraValue(String(v))}
                      placeholder="当前未配置枚举值，请手动输入 LoRA 名称"
                      disabled={batchSubmitting}
                    />
                  )}
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>
                    测试次数（每张图重复） <Typography.Text theme="error">*</Typography.Text>
                  </Typography.Text>
                  <Input
                    value={batchRepeatCount}
                    onChange={(v) => setBatchRepeatCount(String(v).replace(/[^\d]/g, ''))}
                    placeholder="建议 2-5 次"
                    disabled={batchSubmitting}
                  />
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>并发提交（建议 1-4）</Typography.Text>
                  <Input
                    value={batchConcurrency}
                    onChange={(v) => setBatchConcurrency(String(v).replace(/[^\d]/g, ''))}
                    placeholder="默认 3"
                    disabled={batchSubmitting}
                  />
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>输出尺寸策略</Typography.Text>
                  <Select
                    value={batchSizeMode}
                    options={[
                      { label: '原图大小（不传尺寸参数）', value: 'original' },
                      { label: '推荐 1K（速度优先）', value: 'preset_1k' },
                      { label: '自定义', value: 'custom' },
                    ]}
                    onChange={(v) => setBatchSizeMode(String(v) as any)}
                    disabled={batchSubmitting}
                  />
                  {batchSizeMode === 'preset_1k' ? (
                    <Typography.Text theme="secondary">
                      逻辑：优先使用 `resolution=1K`；若工作流仅支持宽高，则按原图比例换算为“最长边=1024”。
                    </Typography.Text>
                  ) : null}
                  {batchSizeMode === 'custom' ? (
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      {batchAspectField ? (
                        <Select
                          value={batchAspectRatio}
                          options={batchAspectOptions}
                          onChange={(v) => setBatchAspectRatio(String(v))}
                          placeholder="画幅比例"
                          disabled={batchSubmitting}
                        />
                      ) : (
                        <Input value="" placeholder="当前工作流不支持画幅比例" disabled />
                      )}
                      {batchResolutionField ? (
                        batchResolutionOptions.length > 0 ? (
                          <Select
                            value={batchResolution}
                            options={batchResolutionOptions}
                            onChange={(v) => setBatchResolution(String(v))}
                            placeholder="分辨率"
                            disabled={batchSubmitting}
                          />
                        ) : (
                          <Input
                            value={batchResolution}
                            onChange={(v) => setBatchResolution(String(v))}
                            placeholder="分辨率（如 1K）"
                            disabled={batchSubmitting}
                          />
                        )
                      ) : (
                        <Input value="" placeholder="当前工作流不支持分辨率" disabled />
                      )}
                      {!batchResolutionField && (batchWidthField || batchHeightField) ? (
                        <Space align="center" style={{ width: '100%' }}>
                          {batchWidthField ? (
                            <Input
                              value={batchCustomWidth}
                              onChange={(v) => setBatchCustomWidth(String(v).replace(/[^\d]/g, ''))}
                              placeholder="宽度（像素）"
                              disabled={batchSubmitting}
                            />
                          ) : (
                            <Input value="" placeholder="当前工作流无宽度参数" disabled />
                          )}
                          {batchHeightField ? (
                            <Input
                              value={batchCustomHeight}
                              onChange={(v) => setBatchCustomHeight(String(v).replace(/[^\d]/g, ''))}
                              placeholder="高度（像素）"
                              disabled={batchSubmitting}
                            />
                          ) : (
                            <Input value="" placeholder="当前工作流无高度参数" disabled />
                          )}
                        </Space>
                      ) : null}
                    </Space>
                  ) : null}
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text>
                    提示词（Prompt）
                    {batchPromptField?.required ? <Typography.Text theme="error"> *</Typography.Text> : null}
                  </Typography.Text>
                  {batchPromptField ? (
                    <Textarea
                      value={batchParamOverrides[batchPromptField.name] ?? ''}
                      onChange={(v) =>
                        setBatchParamOverrides((prev) => ({
                          ...prev,
                          [batchPromptField.name]: String(v),
                        }))
                      }
                      autosize={{ minRows: 3, maxRows: 8 }}
                      placeholder={batchPromptField.description || '请输入提示词'}
                      disabled={batchSubmitting}
                    />
                  ) : (
                    <Textarea value="" autosize={{ minRows: 3, maxRows: 6 }} placeholder="当前工作流不支持提示词" disabled />
                  )}
                </Space>

                {batchExtraFields.length > 0 ? (
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Typography.Text>其他入参（按工作流）</Typography.Text>
                    {batchExtraFields.map((field) => {
                      const options = normalizeFieldOptions(field);
                      const value = batchParamOverrides[field.name] ?? '';
                      const required = Boolean((field as any)?.required);
                      const title = (field as any)?.label || field.name;
                      const isTextarea = field.type === 'textarea' || field.type === 'longtext';
                      return (
                        <Space key={field.name} direction="vertical" size={4} style={{ width: '100%' }}>
                          <Typography.Text>
                            {title}
                            {required ? <Typography.Text theme="error"> *</Typography.Text> : null}
                          </Typography.Text>
                          {options.length > 0 ? (
                            <Select
                              value={value}
                              options={options}
                              onChange={(v) =>
                                setBatchParamOverrides((prev) => ({
                                  ...prev,
                                  [field.name]: String(v),
                                }))
                              }
                              placeholder={`请选择${title}`}
                              disabled={batchSubmitting}
                            />
                          ) : isTextarea ? (
                            <Textarea
                              value={value}
                              autosize={{ minRows: 2, maxRows: 6 }}
                              onChange={(v) =>
                                setBatchParamOverrides((prev) => ({
                                  ...prev,
                                  [field.name]: String(v),
                                }))
                              }
                              placeholder={field.description || `请输入${title}`}
                              disabled={batchSubmitting}
                            />
                          ) : (
                            <Input
                              value={value}
                              onChange={(v) =>
                                setBatchParamOverrides((prev) => ({
                                  ...prev,
                                  [field.name]: String(v),
                                }))
                              }
                              placeholder={field.description || `请输入${title}`}
                              disabled={batchSubmitting}
                            />
                          )}
                        </Space>
                      );
                    })}
                  </Space>
                ) : (
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text>其他入参（按工作流）</Typography.Text>
                    <Input value="" placeholder="当前工作流无其他可配置入参" disabled />
                  </Space>
                )}

                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Typography.Text>
                    批量图片 <Typography.Text theme="error">*</Typography.Text>
                  </Typography.Text>
                  <Space>
                    <Button
                      variant="outline"
                      onClick={() => batchFileInputRef.current?.click()}
                      disabled={batchSubmitting}
                    >
                      选择图片
                    </Button>
                    <Button
                      variant="outline"
                      theme="danger"
                      onClick={() => {
                        setBatchFiles([]);
                      }}
                      disabled={batchSubmitting || batchFiles.length === 0}
                    >
                      清空图片
                    </Button>
                  </Space>
                  <input
                    ref={batchFileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    style={{ display: 'none' }}
                    disabled={batchSubmitting}
                    onChange={(e) => {
                      const picked = Array.from(e.target.files || []);
                      if (picked.length === 0) return;
                      setBatchFiles((prev) => [...prev, ...picked]);
                      e.target.value = '';
                    }}
                  />
                  <Typography.Text theme="secondary">
                    已选择 {batchFiles.length} 张；当前 LoRA：{selectedLoraLabel}
                  </Typography.Text>
                </Space>

                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  {batchSubmitting ? (
                    <Button
                      theme="danger"
                      variant="outline"
                      onClick={() => {
                        batchStopRef.current = true;
                      }}
                    >
                      停止提交
                    </Button>
                  ) : null}
                  <Button
                    theme="primary"
                    onClick={() => void runLoraBatch()}
                    loading={batchSubmitting}
                    disabled={workflowOptions.length === 0 || batchFiles.length === 0}
                  >
                    开始批测
                  </Button>
                </Space>
              </Space>
            </Card>
          </Col>

          <Col xs={12} xl={7}>
            <Card bordered title="提交进度">
              <Row gutter={[12, 12]}>
                <Col xs={12}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text theme="secondary">
                        当前批次：{selectedBatchId || '未选择'}（点击下方列表切换）
                      </Typography.Text>
                      <Space>
                        <Button
                          size="small"
                          variant="outline"
                          loading={batchLoadingSessions}
                          onClick={() => void loadBatchSessions()}
                        >
                          刷新批次
                        </Button>
                      </Space>
                    </Space>
                    <Typography.Text theme="secondary">
                      {batchLoadingSessions ? '正在刷新批次列表…' : `历史批次 ${filteredBatchSessions.length} 个`}
                    </Typography.Text>
                    {batchSessionLoadError ? (
                      <Typography.Text theme="error">批次列表加载失败：{batchSessionLoadError}</Typography.Text>
                    ) : null}
                  </Space>
                </Col>
                <Col xs={12}>
                  <Table
                    size="small"
                    rowKey="batchId"
                    maxHeight={220}
                    data={filteredBatchSessions.slice(0, 20)}
                    onRowClick={(context: any) => setBatchSessionId(String(context?.row?.batchId || ''))}
                    rowClassName={({ row }: any) =>
                      String(row?.batchId || '') === selectedBatchId ? 'lora-batch-row lora-batch-row--active' : 'lora-batch-row'
                    }
                    empty={<Typography.Text theme="secondary">暂无历史批次。</Typography.Text>}
                    columns={[
                      {
                        colKey: 'batchId',
                        title: '批次',
                        minWidth: 220,
                        cell: ({ row }: any) => (
                          <span style={{ fontFamily: 'monospace' }}>
                            {row.batchId}
                            {String(row.batchId || '') === selectedBatchId ? '（当前）' : ''}
                          </span>
                        ),
                      },
                      {
                        colKey: 'status',
                        title: '状态',
                        width: 130,
                        cell: ({ row }: any) => (
                          <StatusBadge status={String(row.status || '').toLowerCase()} fallbackText={formatBatchSessionStatusDisplay(row as LoraBatchSession)} />
                        ),
                      },
                      {
                        colKey: 'progress',
                        title: '进度',
                        width: 180,
                        cell: ({ row }: any) => (
                          <Typography.Text theme="secondary">
                            {Number(row.completed || 0)}/{Number(row.expectedTotal || row.total || 0)}
                          </Typography.Text>
                        ),
                      },
                      {
                        colKey: 'updatedAt',
                        title: '最近更新',
                        minWidth: 170,
                        cell: ({ row }: any) => (
                          <Typography.Text theme="secondary">
                            {fmtTime(row.latestUpdatedAt || row.latestCreatedAt)}
                          </Typography.Text>
                        ),
                      },
                    ]}
                  />
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">样本图片数</Typography.Text>
                    <Typography.Text strong>{batchSummary.imageCount}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">每图测试次数</Typography.Text>
                    <Typography.Text strong>{batchSummary.repeatCount}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">计划执行条数</Typography.Text>
                    <Typography.Text strong>{batchSummary.plannedTotal}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">已入库执行</Typography.Text>
                    <Typography.Text strong>{batchSummary.submitted}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">已完成执行</Typography.Text>
                    <Typography.Text strong>{batchSummary.completed}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">有图完成</Typography.Text>
                    <Typography.Text strong>{batchSummary.generated}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">上传失败</Typography.Text>
                    <Typography.Text strong>{batchSummary.uploadFailed}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={12}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text theme="secondary">
                      当前测试任务：{selectedBatchId || '未提交'}；提交中：{batchSummary.active}；队列/生成中：{batchSummary.queuedOrRunning}；执行失败：{batchSummary.failed}；上传失败：{batchSummary.uploadFailed}；未入库：{batchSummary.missingSubmissions}。
                    </Typography.Text>
                    <Space>
                      <Button
                        size="small"
                        variant="outline"
                        disabled={!selectedBatchId}
                        onClick={() => setBatchDetailExpanded((prev) => !prev)}
                      >
                        {batchDetailExpanded ? '收起排查明细' : '展开排查明细'}
                      </Button>
                      <Button
                        size="small"
                        variant="outline"
                        loading={batchLoadingItems}
                        disabled={!selectedBatchId || !batchDetailExpanded}
                        onClick={() => selectedBatchId && batchDetailExpanded && void loadBatchItems(selectedBatchId)}
                      >
                        刷新明细
                      </Button>
                      <Button
                        theme="danger"
                        variant="outline"
                        disabled={!selectedBatchId || batchStopping || batchSummary.queuedOrRunning <= 0}
                        loading={batchStopping}
                        onClick={() => void stopSelectedBatch()}
                      >
                        停止本批次
                      </Button>
                    </Space>
                  </Space>
                </Col>
                {String(selectedBatchSession?.status || '').toLowerCase() === 'failed' ? (
                  <Col xs={12}>
                    <Typography.Text theme="warning">
                      状态说明：这里的“失败”表示本批次存在失败项（执行失败或上传失败），不代表全部条目都失败。
                    </Typography.Text>
                  </Col>
                ) : null}
                <Col xs={12}>
                  {batchUploadProgress.totalFiles > 0 &&
                  (!selectedBatchId || selectedBatchId === batchUploadProgress.batchId) ? (
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Typography.Text theme="secondary">
                        上传进度：文件 {batchUploadProgress.uploadedFiles + batchUploadProgress.failedFiles}/{batchUploadProgress.totalFiles}（成功 {batchUploadProgress.uploadedFiles}，失败 {batchUploadProgress.failedFiles}，上传中 {batchUploadProgress.activeFiles}）
                      </Typography.Text>
                      <div style={{ width: '100%', height: 8, borderRadius: 999, background: 'var(--td-bg-color-secondarycontainer)' }}>
                        <div
                          style={{
                            width: `${batchUploadFilePercent}%`,
                            height: '100%',
                            borderRadius: 999,
                            background: 'var(--td-brand-color)',
                            transition: 'width 0.2s ease',
                          }}
                        />
                      </div>
                      <Typography.Text theme="secondary">
                        上传字节：{batchUploadBytePercent}%（{Math.round((batchUploadProgress.uploadedBytes || 0) / 1024 / 1024)}MB /{' '}
                        {Math.round((batchUploadProgress.totalBytes || 0) / 1024 / 1024)}MB）
                      </Typography.Text>
                    </Space>
                  ) : batchUploadProgress.totalFiles > 0 && selectedBatchId && selectedBatchId !== batchUploadProgress.batchId ? (
                    <Typography.Text theme="secondary">该批次暂无本地上传进度，已切换为历史批次视图。</Typography.Text>
                  ) : (
                    <Typography.Text theme="secondary">上传进度：尚未开始。</Typography.Text>
                  )}
                </Col>
                {batchSummary.missingSubmissions > 0 ? (
                  <Col xs={12}>
                    <Typography.Text theme="warning">
                      检测到该批次有 {batchSummary.missingSubmissions} 条任务未入库（常见原因：上传失败或提交请求超时）。建议点击“刷新明细”后复测缺失样本。
                    </Typography.Text>
                  </Col>
                ) : null}
                {!batchDetailExpanded ? (
                  <Col xs={12}>
                    <Typography.Text theme="secondary">默认不自动拉取逐条明细，避免页面频繁刷新。需要排查时再点击“展开排查明细”。</Typography.Text>
                  </Col>
                ) : null}
              </Row>
            </Card>

            {batchDetailExpanded ? (
            <Card
              bordered
              title={
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>本批次明细（排查专用）</Typography.Text>
                  <Space>
                    {batchItemsLoadError ? <Typography.Text theme="error">明细加载失败：{batchItemsLoadError}</Typography.Text> : null}
                    <Typography.Text theme="secondary">本批次共 {visibleExecutionBatchItems.length} 条执行</Typography.Text>
                  </Space>
                </Space>
              }
            >
                {uploadFailedBatchItems.length > 0 ? (
                  <Alert
                    theme="warning"
                    message={`有 ${uploadFailedBatchItems.length} 条在上传阶段失败，未进入执行队列；请优先处理网络或上传凭证问题。`}
                  />
                ) : null}
                <Table
                  size="small"
                  rowKey="key"
                  data={visibleExecutionBatchItems}
                  loading={batchLoadingItems}
                  maxHeight={520}
                  empty={<Typography.Text theme="secondary">暂无批次任务。</Typography.Text>}
                columns={[
                  {
                    colKey: 'file',
                    title: '图片',
                    minWidth: 220,
                    cell: ({ row }: any) => (
                      <Space direction="vertical" size={2}>
                        <Typography.Text>{row.fileName}</Typography.Text>
                        <Typography.Text theme="secondary">第 {row.repeatIndex} 次</Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'status',
                    title: '状态',
                    width: 180,
                    cell: ({ row }: any) => {
                      const runStatus = String(row.runStatus || '');
                      const text =
                        row.status === 'submitted'
                          ? formatLoraBatchRunStatusLabel(row.runStatus, row.outputCount)
                          : formatLoraBatchStatusLabel(row.status);
                      const status = row.status === 'submitted' ? runStatus || row.status : row.status;
                      return (
                        <StatusBadge status={status} fallbackText={text} />
                      );
                    },
                  },
                  {
                    colKey: 'runId',
                    title: '执行ID',
                    minWidth: 210,
                    cell: ({ row }: any) => (
                      <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                        {row.runId || '—'}
                      </Typography.Text>
                    ),
                  },
                  {
                    colKey: 'error',
                    title: '错误信息',
                    minWidth: 260,
                    cell: ({ row }: any) => (
                      <Typography.Text theme={row.error ? 'error' : 'secondary'} ellipsis>
                        {row.error || row.runError || '—'}
                      </Typography.Text>
                    ),
                  },
                ]}
              />
            </Card>
            ) : null}
          </Col>
        </Row>
        ) : (
        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text strong>结果标注（分页）</Typography.Text>
              <Space>
                <Button
                  variant="outline"
                  disabled={!selectedBatchId || !selectedBatchIsTerminal || batchExporting !== ''}
                  loading={batchExporting === 'all'}
                  onClick={() => void exportBatchComparisonCsv(false)}
                >
                  导出全部
                </Button>
                <Button
                  variant="outline"
                  disabled={!selectedBatchId || !selectedBatchIsTerminal || batchExporting !== ''}
                  loading={batchExporting === 'unsatisfied'}
                  onClick={() => void exportBatchComparisonCsv(true)}
                >
                  导出不满意
                </Button>
              </Space>
            </Space>
          }
        >
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Space direction="vertical" size={4}>
                <Typography.Text theme="secondary">标注批次</Typography.Text>
                <Select
                  value={selectedBatchId || ''}
                  options={batchSessionOptions}
                  placeholder={batchSessionOptions.length > 0 ? '请选择批次' : '暂无可标注批次'}
                  onChange={(v) => setBatchSessionId(String(v))}
                  disabled={batchSessionOptions.length === 0}
                  style={{ width: 520, maxWidth: '100%' }}
                />
              </Space>
              <Space>
                <Button
                  size="small"
                  variant="outline"
                  loading={batchLoadingSessions}
                  onClick={() => void loadBatchSessions()}
                >
                  刷新批次
                </Button>
              </Space>
            </Space>
            {!selectedBatchId ? (
              <Alert theme="info" message="请先选择要标注的批次。" />
            ) : !selectedBatchIsTerminal ? (
              <Alert
                theme="warning"
                message={`当前批次状态为 ${formatBatchSessionStatusLabel(selectedBatchSession?.status)}，请等待批次结束后再标注。`}
              />
            ) : (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space direction="vertical" size={4}>
                  <Typography.Text theme="secondary">
                    已完成页：{Math.min(batchReviewProgress.completedPage, Math.max(1, batchReviewTotalPages || 1))}/{Math.max(1, batchReviewTotalPages || 1)}
                  </Typography.Text>
                  <Typography.Text theme="secondary">
                    当前页：第 {batchReviewPage} 页（共 {batchReviewTotalGroups} 组）
                  </Typography.Text>
                </Space>
                <Space>
                  <Button
                    variant="outline"
                    disabled={batchReviewPage <= 1 || batchReviewPageJumping || batchReviewGroupLoading}
                    onClick={() => void jumpToBatchReviewPage(batchReviewPage - 1)}
                  >
                    上一页
                  </Button>
                  <Select
                    value={batchReviewPage}
                    options={batchReviewPageOptions}
                    disabled={batchReviewTotalPages <= 0 || batchReviewPageJumping || batchReviewGroupLoading}
                    onChange={(v) => void jumpToBatchReviewPage(Number(v || 1))}
                    style={{ width: 140 }}
                  />
                  <Button
                    variant="outline"
                    disabled={batchReviewPage >= batchReviewTotalPages || batchReviewPageJumping || batchReviewGroupLoading}
                    onClick={() => void jumpToBatchReviewPage(batchReviewPage + 1)}
                  >
                    下一页
                  </Button>
                  <Button
                    theme="primary"
                    loading={batchReviewProgressSaving}
                    disabled={batchReviewTotalPages <= 0 || batchReviewGroupLoading}
                    onClick={() => void completeBatchReviewPage()}
                  >
                    本页完成
                  </Button>
                </Space>
              </Space>
              {batchReviewGroupError ? <Alert theme="error" message={`分页加载失败：${batchReviewGroupError}`} /> : null}
              {noOutputGroupCount > 0 ? (
                <Alert
                  theme="info"
                  message={
                    showNoOutputGroups
                      ? `本页有 ${noOutputGroupCount} 组无结果项（通常是上传/提交失败）。已展示用于排查。`
                      : `本页有 ${noOutputGroupCount} 组无结果项（通常是上传/提交失败），标注页默认隐藏。`
                  }
                  operation={
                    <Button size="small" variant="outline" onClick={() => setShowNoOutputGroups((prev) => !prev)}>
                      {showNoOutputGroups ? '隐藏无结果项' : '查看无结果项'}
                    </Button>
                  }
                />
              ) : null}
              {(showNoOutputGroups ? batchReviewGroups : actionableReviewGroups).length === 0 ? (
                <Typography.Text theme="secondary">本页无可标注结果图。</Typography.Text>
              ) : (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  {(showNoOutputGroups ? batchReviewGroups : actionableReviewGroups).map((group) => (
                    <div key={`${group.assetId}-${group.sourceKey}`} style={{ border: '1px solid var(--td-component-border)', borderRadius: 8, padding: 10 }}>
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Typography.Text strong>{group.fileName || '未命名素材'}</Typography.Text>
                          <Typography.Text theme="secondary">
                            状态：{formatLoraReviewGroupStatusLabel(group.groupStatus)}；完成 {group.completed}/{group.runTotal}；失败 {group.failed}；等待 {group.waiting}
                          </Typography.Text>
                        </Space>
                        <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 6 }}>
                          <div style={{ minWidth: 240 }}>
                            <Typography.Text theme="secondary">原图</Typography.Text>
                            {group.inputUrl ? (
                              <img
                                src={group.inputUrl}
                                alt="原图"
                                style={{ width: 240, height: 240, objectFit: 'contain', border: '1px solid var(--td-component-border)' }}
                                onClick={() => setLightbox({ url: group.inputUrl || '', title: '原图' })}
                              />
                            ) : (
                              <div style={{ width: 240, height: 240, border: '1px dashed var(--td-component-border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Typography.Text theme="secondary">无原图地址</Typography.Text>
                              </div>
                            )}
                          </div>
                          {group.outputs.map((output) => {
                            const review = batchReviewMap[output.reviewKey] || { verdict: 'pending' as LoraBatchReviewVerdict };
                            const isUnsatisfied = review.verdict === 'unsatisfied';
                            return (
                              <div key={output.reviewKey} style={{ minWidth: 300, maxWidth: 340 }}>
                                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                  <Typography.Text theme="secondary">
                                    结果图 {output.outputIndex}
                                    {output.runId ? ` · 执行ID ${output.runId}` : ''}
                                  </Typography.Text>
                                  <Button
                                    size="small"
                                    theme="danger"
                                    variant={isUnsatisfied ? 'base' : 'outline'}
                                    onClick={() =>
                                      updateBatchReview(output.reviewKey, {
                                        verdict: isUnsatisfied ? 'pending' : 'unsatisfied',
                                        reason: isUnsatisfied ? '' : review.reason,
                                        note: isUnsatisfied ? '' : review.note,
                                      })
                                    }
                                  >
                                    {isUnsatisfied ? '取消不满意' : '标记不满意'}
                                  </Button>
                                  <img
                                    src={output.url}
                                    alt={`结果图${output.outputIndex}`}
                                    style={{ width: 300, height: 240, objectFit: 'contain', border: '1px solid var(--td-component-border)' }}
                                    onClick={() => setLightbox({ url: output.url, title: `结果图 ${output.outputIndex}` })}
                                  />
                                  {isUnsatisfied ? (
                                    <>
                                      <Select
                                        value={review.reason || ''}
                                        options={batchReviewReasonOptions}
                                        placeholder="不满意原因（可选）"
                                        onChange={(v) =>
                                          updateBatchReview(output.reviewKey, {
                                            verdict: 'unsatisfied',
                                            reason: v == null ? '' : String(v),
                                          })
                                        }
                                        clearable
                                      />
                                      <Input
                                        value={review.note || ''}
                                        placeholder="备注（可选）"
                                        onChange={(v) =>
                                          updateBatchReview(output.reviewKey, {
                                            verdict: 'unsatisfied',
                                            note: v == null ? '' : String(v),
                                          })
                                        }
                                      />
                                    </>
                                  ) : (
                                    <Typography.Text theme="success">默认满意</Typography.Text>
                                  )}
                                </Space>
                              </div>
                            );
                          })}
                        </div>
                        {group.outputs.length === 0 ? (
                          <Alert theme="warning" message={group.lastError || '该组暂无结果图，暂不可标注。'} />
                        ) : null}
                      </Space>
                    </div>
                  ))}
                </Space>
              )}
              <Space align="center" style={{ justifyContent: 'flex-end', width: '100%' }}>
                <Typography.Text theme="secondary">底部翻页</Typography.Text>
                <Button
                  variant="outline"
                  disabled={batchReviewPage <= 1 || batchReviewPageJumping || batchReviewGroupLoading}
                  onClick={() => void jumpToBatchReviewPage(batchReviewPage - 1)}
                >
                  上一页
                </Button>
                <Button
                  variant="outline"
                  disabled={batchReviewPage >= batchReviewTotalPages || batchReviewPageJumping || batchReviewGroupLoading}
                  onClick={() => void jumpToBatchReviewPage(batchReviewPage + 1)}
                >
                  下一页
                </Button>
              </Space>
            </Space>
            )}
          </Space>
        </Card>
        )}
      </Space>,
    );
  }

  if (activeView === 'tool' && selectedTool) {
    const metric = metrics[selectedTool.id];
    const historyFocusMeta = getHistoryFocusMeta(historyFocus);
    const toolRuntimeHealth = getWorkflowRuntimeHealth(metric);
    const selectedToolAccent = getWorkflowAccent(selectedTool);
    const selectedToolReleaseDate = getWorkflowReleaseDate(selectedTool);
    const selectedToolInputSummary = getWorkflowInputSummary(selectedTool);
    const selectedToolOutputSummary = getWorkflowOutputSummary(selectedTool);
    const selectedToolRouting = getWorkflowRoutingGovernance(selectedTool);
    const selectedToolGovernance = getWorkflowGovernance(selectedTool);
    const selectedToolRoleTheme = getWorkflowGovernanceTheme(selectedToolGovernance?.role);
    const selectedToolRoutingTheme = getWorkflowRoutingGovernanceTheme(selectedToolRouting?.governanceStatus);
    const selectedToolExecutionLabel = String(selectedToolRouting?.executionLabel || '执行面待确认').trim();
    const selectedToolTrackingLabel = String(selectedToolRouting?.currentTrackingLabel || '追踪待确认').trim();
    const selectedToolRoleLabel = String(selectedToolGovernance?.roleLabel || '可测版本').trim();
    const selectedToolUsesBusinessApi = isBusinessApiWorkflow(selectedTool);
    const doc = isAiEditor
      ? buildAiEditorDoc(selectedTool, formUrl.trim(), editorPromptPreview, editorRefs)
      : selectedToolUsesBusinessApi
        ? buildBusinessApiDoc(selectedTool, formUrl.trim())
        : buildCozeDoc(selectedTool, formUrl.trim());
    const integrationDocTitle = selectedToolUsesBusinessApi
      ? '业务接入文档（中台业务 API）'
      : '业务接入文档（Coze OpenAPI）';
    const integrationDocDescription = selectedToolUsesBusinessApi
      ? '此功能不走 Coze 工作流，业务方应直接提交中台业务任务并用 runId 查询结果。'
      : '低频资料默认收起；需要给业务方核对参数时再展开。';
    const copyIntegrationDoc = async () => {
      try {
        await navigator.clipboard.writeText(doc);
        pushNotice('success', '已复制到剪贴板');
      } catch {
        pushNotice('error', '复制失败（浏览器不支持或权限不足）');
      }
    };
    return shell(
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Button
            variant="outline"
            onClick={() => {
              setActiveView('home');
              setSelectedTool(null);
            }}
          >
            返回功能列表
          </Button>
          <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }}>
            workflow_id: {selectedTool.workflow_id}
          </Typography.Text>
        </Space>

        <div
          className="podi-eval-tool-overview"
          style={{ '--podi-tool-accent': selectedToolAccent } as CSSProperties}
        >
          <div className="podi-eval-tool-overview__main">
            <Typography.Text className="podi-eval-tool-overview__eyebrow">当前功能工作台</Typography.Text>
            <Space direction="vertical" size={6} style={{ minWidth: 0, width: '100%' }}>
              <Typography.Title level="h4" style={{ margin: 0 }}>
                {getWorkflowOperationTitle(selectedTool)} · {getWorkflowCardTitle(selectedTool)}
              </Typography.Title>
              <Typography.Text theme="secondary">{getWorkflowUsageHint(selectedTool) || '—'}</Typography.Text>
              <Space breakLine>
                {getWorkflowBadges(selectedTool).map((badge) => (
                  <Tag key={badge} theme={getWorkflowBadgeTheme(badge)} variant="light">
                    {badge}
                  </Tag>
                ))}
                <Tag variant="light">{getWorkflowCategory(selectedTool)}</Tag>
                <Tag variant="light">{getWorkflowVersionLabel(selectedTool)}</Tag>
                {getWorkflowOperationLabel(selectedTool) ? <Tag variant="light">{getWorkflowOperationLabel(selectedTool)}</Tag> : null}
                <Tag theme={selectedToolRoleTheme} variant="light">
                  {selectedToolRoleLabel}
                </Tag>
                <Tag theme={selectedToolRoutingTheme} variant="light">
                  {selectedToolExecutionLabel}
                </Tag>
                <Tag theme={toolRuntimeHealth.theme} variant="light">
                  {toolRuntimeHealth.label}
                </Tag>
                {metric?.avgRating ? (
                  <Tag theme="warning" variant="light">
                    综合评分：{metric.avgRating.toFixed(2)} / 5（{metric.ratingCount}票）
                  </Tag>
                ) : (
                  <Tag variant="light">综合评分：暂无</Tag>
                )}
              </Space>
              <Typography.Text theme="secondary" style={{ fontSize: 13 }}>
                {toolRuntimeHealth.detail}
              </Typography.Text>
            </Space>
          </div>
          <div className="podi-eval-tool-overview__facts" aria-label="功能关键信息">
            <div>
              <span>发布时间</span>
              <strong>{selectedToolReleaseDate}</strong>
            </div>
            <div>
              <span>输入方式</span>
              <strong>{selectedToolInputSummary}</strong>
            </div>
            <div>
              <span>输出结果</span>
              <strong>{selectedToolOutputSummary}</strong>
            </div>
            <div>
              <span>任务追踪</span>
              <strong>{selectedToolTrackingLabel}</strong>
            </div>
          </div>
        </div>
        <StepGuide
          title="单次评测流程"
          hint="保持同一流程可以减少误操作，结果更容易横向对比。"
          steps={[
            { title: '准备输入', description: '填写 URL / 提示词 / 业务参数。' },
            { title: '提交运行', description: '点击开始生成并等待状态变更。' },
            { title: '查看结果', description: '右侧查看最新出图、错误信息与调试链接。' },
            { title: '历史打标', description: '在底部历史记录中评分并沉淀备注。' },
          ]}
        />

        <Row gutter={[16, 16]} className="podi-eval-workbench">
          {/* TDesign Grid uses a 12-column system; keep spans within 12 to avoid wrapping/empty gaps. */}
          <Col xs={12} xl={5}>
            <Card
              bordered
              className="podi-eval-panel podi-eval-panel--input"
              title={
                <div className="podi-panel-title">
                  <strong>输入与运行</strong>
                  <span>先补齐必填参数，再提交一次可复盘的测试。</span>
                </div>
              }
            >
              {isAiEditor ? (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text>
                      主图 URL <Typography.Text theme="error">*</Typography.Text>
                    </Typography.Text>
                    <Space align="center" style={{ width: '100%' }}>
                      <div style={{ flex: 1 }}>
                        <Input
                          value={formUrl}
                          onChange={(v) => setFormUrl(String(v))}
                          placeholder="支持粘贴 URL 或上传本地图片"
                          clearable
                        />
                      </div>
                      <Button variant="outline" loading={uploading} onClick={() => uploadInputRef.current?.click()}>
                        上传
                      </Button>
                      <input
                        ref={uploadInputRef}
                        type="file"
                        accept="image/*"
                        style={{ display: 'none' }}
                        disabled={uploading}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setUploading(true);
                          try {
                            const res = await evalApi.uploadImage(file);
                            setFormUrl(res.url);
                          } catch (err) {
                            console.error(err);
                            pushNotice('error', String((err as any)?.message || err));
                          } finally {
                            setUploading(false);
                            e.target.value = '';
                          }
                        }}
                      />
                    </Space>
                  </Space>

                  <Card bordered title="标注区域（点选 / 矩形 / 圆形 / 手绘）">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Space breakLine>
                        {(['point', 'rect', 'circle', 'freehand'] as EditorTool[]).map((tool) => (
                          <Button
                            key={tool}
                            size="small"
                            theme={editorTool === tool ? 'primary' : 'default'}
                            variant={editorTool === tool ? 'base' : 'outline'}
                            onClick={() => setEditorTool(tool)}
                          >
                            {formatEditorToolLabel(tool)}
                          </Button>
                        ))}
                        <Button
                          size="small"
                          variant="outline"
                          onClick={() => {
                            setEditorMarks([]);
                            setEditorDrawing(null);
                          }}
                        >
                          清空标注
                        </Button>
                      </Space>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        标注会生成 @标注1/@标注2…，可在提示词里直接使用。
                      </Typography.Text>
                      {formUrl.trim() ? (
                        <div
                          ref={editorContainerRef}
                          style={{
                            position: 'relative',
                            width: '100%',
                            border: '1px dashed var(--td-border-level-1-color)',
                            borderRadius: 8,
                            overflow: 'hidden',
                            cursor: 'crosshair',
                          }}
                          onMouseDown={handleEditorPointerDown}
                          onMouseMove={handleEditorPointerMove}
                          onMouseUp={finalizeEditorDrawing}
                          onMouseLeave={finalizeEditorDrawing}
                        >
                          <img
                            ref={editorImageRef}
                            src={formUrl.trim()}
                            alt="input"
                            style={{ width: '100%', height: 'auto', display: 'block' }}
                            onLoad={syncEditorImageMeta}
                          />
                          <svg
                            width={editorImageMeta.displayW || '100%'}
                            height={editorImageMeta.displayH || '100%'}
                            style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: '100%' }}
                          >
                            {[...editorMarks, ...(editorDrawing ? [editorDrawing] : [])].map((mark, idx) => {
                              const pts = mark.points.map(toEditorDisplayPoint);
                              const label = mark.name || `标注${idx + 1}`;
                              if (mark.type === 'point' && pts[0]) {
                                return (
                                  <g key={mark.id}>
                                    <circle cx={pts[0].x} cy={pts[0].y} r={4} fill="#f97316" />
                                    <text x={pts[0].x + 6} y={pts[0].y - 6} fontSize="12" fill="#f97316">
                                      @{label}
                                    </text>
                                  </g>
                                );
                              }
                              if ((mark.type === 'rect' || mark.type === 'circle') && pts.length >= 2) {
                                const a = pts[0];
                                const b = pts[1];
                                const left = Math.min(a.x, b.x);
                                const top = Math.min(a.y, b.y);
                                const w = Math.abs(a.x - b.x);
                                const h = Math.abs(a.y - b.y);
                                if (mark.type === 'rect') {
                                  return (
                                    <g key={mark.id}>
                                      <rect x={left} y={top} width={w} height={h} fill="none" stroke="#38bdf8" strokeWidth={2} />
                                      <text x={left + 4} y={top - 6} fontSize="12" fill="#38bdf8">
                                        @{label}
                                      </text>
                                    </g>
                                  );
                                }
                                const cx = (a.x + b.x) / 2;
                                const cy = (a.y + b.y) / 2;
                                const r = Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2) / 2;
                                return (
                                  <g key={mark.id}>
                                    <circle cx={cx} cy={cy} r={r} fill="none" stroke="#a855f7" strokeWidth={2} />
                                    <text x={cx + r + 4} y={cy} fontSize="12" fill="#a855f7">
                                      @{label}
                                    </text>
                                  </g>
                                );
                              }
                              if (mark.type === 'freehand' && pts.length > 1) {
                                const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
                                const first = pts[0];
                                return (
                                  <g key={mark.id}>
                                    <path d={path} fill="none" stroke="#22c55e" strokeWidth={2} />
                                    <text x={first.x + 6} y={first.y - 6} fontSize="12" fill="#22c55e">
                                      @{label}
                                    </text>
                                  </g>
                                );
                              }
                              return null;
                            })}
                          </svg>
                        </div>
                      ) : (
                        <Alert theme="info" message="请先上传主图，再进行标注。" />
                      )}
                    </Space>
                  </Card>

                  <Card bordered title={`标注列表（${editorMarks.length}）`}>
                    {editorMarks.length === 0 ? (
                      <Typography.Text theme="secondary">暂无标注。</Typography.Text>
                    ) : (
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {editorMarks.map((mark, idx) => (
                          <Space key={mark.id} align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
                            <Space align="center">
                              <Input
                                value={mark.name}
                                style={{ width: 140 }}
                                onChange={(v) =>
                                  setEditorMarks((prev) =>
                                    prev.map((m) => (m.id === mark.id ? { ...m, name: String(v) } : m)),
                                  )
                                }
                              />
                              <Tag variant="light">{formatEditorToolLabel(mark.type)}</Tag>
                            </Space>
                            <Space>
                              <Button
                                size="small"
                                variant="outline"
                                onClick={() =>
                                  setEditorPrompt((prev) =>
                                    `${prev}${prev.trim() ? ' ' : ''}@${mark.name || `标注${idx + 1}`}`.trim(),
                                  )
                                }
                              >
                                插入 @标注
                              </Button>
                              <Button
                                size="small"
                                theme="danger"
                                variant="outline"
                                onClick={() => setEditorMarks((prev) => prev.filter((m) => m.id !== mark.id))}
                              >
                                删除
                              </Button>
                            </Space>
                          </Space>
                        ))}
                      </Space>
                    )}
                  </Card>

                  <Card bordered title={`参考图（${editorRefs.length}）`}>
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Space align="center" style={{ width: '100%' }}>
                        <Input
                          value={editorRefDraft}
                          onChange={(v) => setEditorRefDraft(String(v))}
                          placeholder="粘贴参考图 URL 后点击添加"
                          clearable
                        />
                        <Button
                          variant="outline"
                          onClick={() => {
                            const url = editorRefDraft.trim();
                            if (!url) return;
                            setEditorRefs((prev) => (prev.includes(url) ? prev : [...prev, url]));
                            setEditorRefDraft('');
                          }}
                        >
                          添加
                        </Button>
                        <Button variant="outline" onClick={() => editorRefUploadRef.current?.click()}>
                          上传
                        </Button>
                        <input
                          ref={editorRefUploadRef}
                          type="file"
                          accept="image/*"
                          style={{ display: 'none' }}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            try {
                              const res = await evalApi.uploadImage(file);
                              setEditorRefs((prev) => [...prev, res.url]);
                            } catch (err) {
                              console.error(err);
                              pushNotice('error', String((err as any)?.message || err));
                            } finally {
                              e.target.value = '';
                            }
                          }}
                        />
                      </Space>
                      {editorRefs.length === 0 ? (
                        <Typography.Text theme="secondary">暂无参考图。</Typography.Text>
                      ) : (
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          {editorRefs.map((url, idx) => (
                            <Space key={`${url}-${idx}`} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                              <Space align="center">
                                <img
                                  src={url}
                                  alt={`ref-${idx + 1}`}
                                  style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, cursor: 'pointer' }}
                                  onClick={() => setLightbox({ url, title: `参考图 #${idx + 1}` })}
                                />
                                <Typography.Text theme="secondary">#{idx + 1}（图{idx + 2}）</Typography.Text>
                              </Space>
                              <Space>
                                <Button
                                  size="small"
                                  variant="outline"
                                  onClick={() =>
                                    setEditorPrompt((prev) => `${prev}${prev.trim() ? ' ' : ''}#${idx + 1}`.trim())
                                  }
                                >
                                  插入 #参考图
                                </Button>
                                <Button
                                  size="small"
                                  theme="danger"
                                  variant="outline"
                                  onClick={() => setEditorRefs((prev) => prev.filter((_, i) => i !== idx))}
                                >
                                  删除
                                </Button>
                              </Space>
                            </Space>
                          ))}
                        </Space>
                      )}
                    </Space>
                  </Card>

                  <Card bordered title="提示词（可用 @标注 / #参考图）">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Textarea
                        ref={editorPromptRef as any}
                        value={editorPrompt}
                        onChange={(v) => {
                          const next = String(v);
                          setEditorPrompt(next);
                          updateEditorPromptHint(next);
                        }}
                        onKeyup={() => updateEditorPromptHint(editorPromptRef.current?.value || editorPrompt)}
                        onClick={() => updateEditorPromptHint(editorPromptRef.current?.value || editorPrompt)}
                        autosize={{ minRows: 4, maxRows: 10 }}
                        placeholder="例如：@标注1 把这段文字改成“新年快乐”，参考 #1 的字体风格"
                      />
                      {editorPromptHint ? (
                        <div
                          style={{
                            border: '1px solid var(--td-border-level-1-color)',
                            borderRadius: 8,
                            padding: 10,
                            background: 'var(--td-bg-color-container)',
                          }}
                        >
                          <Space direction="vertical" size={6} style={{ width: '100%' }}>
                            <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                              {editorPromptHint.type === 'mark' ? '选择可用标注' : '选择参考图（模型侧=图2/图3…）'}
                            </Typography.Text>
                            {promptHintOptions.length === 0 ? (
                              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                                {editorPromptHint.type === 'mark' ? '暂无标注可选。' : '暂无参考图可选。'}
                              </Typography.Text>
                            ) : (
                              <Space breakLine>
                                {promptHintOptions.map((item) => (
                                  <Button
                                    key={item.label}
                                    size="small"
                                    variant="outline"
                                    onClick={() => applyPromptHint(item.token)}
                                  >
                                    {item.label}
                                  </Button>
                                ))}
                              </Space>
                            )}
                          </Space>
                        </div>
                      ) : null}
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        提示词会自动拼接“图像编号 + 标注说明 + 参考图映射 + 原图尺寸”，并将 #1/#2 改写为 图2/图3。
                      </Typography.Text>
                    </Space>
                  </Card>

                  <Card bordered title="提示词重组预览（发送给 Coze）">
                    <pre
                      style={{
                        maxHeight: 240,
                        overflow: 'auto',
                        border: '1px solid var(--td-border-level-1-color)',
                        background: 'var(--td-bg-color-secondarycontainer)',
                        borderRadius: 8,
                        padding: 12,
                        fontFamily: 'monospace',
                        fontSize: 12,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {editorPromptPreview || '（暂无内容）'}
                    </pre>
                  </Card>

                  <Card bordered title="高级参数（可选）">
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      {toolFields
                        .filter((f) => !['url', 'Url', 'prompt', 'image_urls'].includes(f.name))
                        .map((f) => (
                          <ParamField
                            key={f.name}
                            field={f}
                            value={formParams[f.name] ?? ''}
                            onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: v }))}
                          />
                        ))}
                    </Space>
                  </Card>

                  <div className="podi-run-action-bar">
                    <div>
                      <Typography.Text strong>{formUrl.trim() ? '输入已就绪' : '等待主图'}</Typography.Text>
                      <div>
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {formUrl.trim() ? '可提交运行；建议单次先看结果，再批量放量。' : '请先上传或粘贴主图 URL。'}
                        </Typography.Text>
                      </div>
                    </div>
                    <Button
                      theme="primary"
                      loading={isRunning}
                      disabled={isRunning || !formUrl.trim()}
                      onClick={() => void runTool()}
                    >
                      开始生成
                    </Button>
                  </div>

                  <IntegrationDocBlock
                    doc={doc}
                    title={integrationDocTitle}
                    description={integrationDocDescription}
                    expanded={showIntegrationDoc}
                    onToggle={() => setShowIntegrationDoc((prev) => !prev)}
                    onCopy={copyIntegrationDoc}
                  />
                </Space>
              ) : (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  {requiresImage ? (
                    <>
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        <Typography.Text>
                          图片 URL <Typography.Text theme="error">*</Typography.Text>
                        </Typography.Text>
                        <Space align="center" style={{ width: '100%' }}>
                          <div style={{ flex: 1 }}>
                            <Input
                              value={formUrl}
                              onChange={(v) => setFormUrl(String(v))}
                              placeholder="支持粘贴 URL 或上传本地图片"
                              clearable
                            />
                          </div>
                          <Button variant="outline" loading={uploading} onClick={() => uploadInputRef.current?.click()}>
                            上传
                          </Button>
                          <input
                            ref={uploadInputRef}
                            type="file"
                            accept="image/*"
                            style={{ display: 'none' }}
                            disabled={uploading}
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              setUploading(true);
                              try {
                                const res = await evalApi.uploadImage(file);
                                setFormUrl(res.url);
                              } catch (err) {
                                console.error(err);
                                pushNotice('error', String((err as any)?.message || err));
                              } finally {
                                setUploading(false);
                                e.target.value = '';
                              }
                            }}
                          />
                        </Space>
                      </Space>

                      {formUrl.trim() ? (
                        <Card bordered title="原图预览">
                          <img
                            src={formUrl.trim()}
                            alt="input"
                            style={{ height: 240, width: '100%', objectFit: 'contain', cursor: 'pointer' }}
                            onClick={() => setLightbox({ url: formUrl.trim(), title: '原图' })}
                          />
                        </Card>
                      ) : null}
                    </>
                  ) : null}

                  <Space direction="vertical" size="large" style={{ width: '100%' }}>
                    {toolFields
                      .filter((f) => f.name !== 'url' && f.name !== 'Url')
                      .filter((f) => !(isShengtuWorkflow && f.name === 'image_urls'))
                      .map((f) => {
                        const modelAware = modelAwareFieldMap.get(f.name);
                        if (f.name === 'image_urls') {
                          const urls = parseImageUrlList(formParams[f.name] ?? '');
                          return (
                            <Card key={f.name} bordered title={f.label ?? '辅图 URLs'}>
                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                <Textarea
                                  value={formParams[f.name] ?? ''}
                                  onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: String(v) }))}
                                  autosize={{ minRows: 3, maxRows: 8 }}
                                  placeholder="支持粘贴 URL，或上传图2/图3（每行一张）"
                                  disabled={Boolean(modelAware?.disabled) || extraImageUploading}
                                />
                                <Space align="center" style={{ width: '100%' }}>
                                  <Button
                                    variant="outline"
                                    loading={extraImageUploading}
                                    disabled={Boolean(modelAware?.disabled)}
                                    onClick={() => extraImagesInputRef.current?.click()}
                                  >
                                    上传图2/图3
                                  </Button>
                                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                                    最多支持 2 张辅图，英文逗号或换行分隔。
                                  </Typography.Text>
                                  <input
                                    ref={extraImagesInputRef}
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    style={{ display: 'none' }}
                                    disabled={extraImageUploading || Boolean(modelAware?.disabled)}
                                    onChange={async (e) => {
                                      const files = Array.from(e.target.files || []).slice(0, 2);
                                      if (!files.length) return;
                                      setExtraImageUploading(true);
                                      try {
                                        const uploaded: string[] = [];
                                        for (const file of files) {
                                          const res = await evalApi.uploadImage(file);
                                          uploaded.push(res.url);
                                        }
                                        appendImageUrls(uploaded);
                                      } catch (err) {
                                        console.error(err);
                                        pushNotice('error', String((err as any)?.message || err));
                                      } finally {
                                        setExtraImageUploading(false);
                                        e.target.value = '';
                                      }
                                    }}
                                  />
                                </Space>
                                {urls.length > 0 ? (
                                  <Space breakLine>
                                    {urls.slice(0, 2).map((item, idx) => (
                                      <Tag
                                        key={`${f.name}-${idx}`}
                                        closable
                                        onClose={() => removeImageUrlAt(idx)}
                                        style={{ maxWidth: 320 }}
                                      >
                                        图{idx + 2}
                                      </Tag>
                                    ))}
                                  </Space>
                                ) : null}
                                {modelAware?.description ? <Typography.Text theme="secondary">{modelAware.description}</Typography.Text> : null}
                              </Space>
                            </Card>
                          );
                        }
                        if (f.name === 'image_url_2' || f.name === 'image_url_3') {
                          return (
                            <Card key={f.name} bordered title={f.label ?? f.name}>
                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                                <Input
                                  value={formParams[f.name] ?? ''}
                                  onChange={(v) => setSingleImageField(f.name, String(v))}
                                  placeholder={f.name === 'image_url_2' ? '支持粘贴辅图 1 URL 或上传本地图片' : '支持粘贴辅图 2 URL 或上传本地图片'}
                                  clearable
                                  disabled={Boolean(modelAware?.disabled) || extraImageUploading}
                                />
                                <Space align="center" style={{ width: '100%' }}>
                                  <Button
                                    variant="outline"
                                    loading={extraImageUploading && extraImageFieldTarget === f.name}
                                    disabled={Boolean(modelAware?.disabled)}
                                    onClick={() => {
                                      setExtraImageFieldTarget(f.name);
                                      extraImagesInputRef.current?.click();
                                    }}
                                  >
                                    上传{f.name === 'image_url_2' ? '辅图1' : '辅图2'}
                                  </Button>
                                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                                    {f.name === 'image_url_2' ? '对应新 workflow 的节点 106（image2）。' : '对应新 workflow 的节点 108（image3）。'}
                                  </Typography.Text>
                                  <input
                                    ref={extraImagesInputRef}
                                    type="file"
                                    accept="image/*"
                                    style={{ display: 'none' }}
                                    disabled={extraImageUploading || Boolean(modelAware?.disabled)}
                                    onChange={async (e) => {
                                      const file = e.target.files?.[0];
                                      const targetField = extraImageFieldTarget;
                                      if (!file || !targetField) return;
                                      setExtraImageUploading(true);
                                      try {
                                        const res = await evalApi.uploadImage(file);
                                        setSingleImageField(targetField, res.url);
                                      } catch (err) {
                                        console.error(err);
                                        pushNotice('error', String((err as any)?.message || err));
                                      } finally {
                                        setExtraImageUploading(false);
                                        setExtraImageFieldTarget(null);
                                        e.target.value = '';
                                      }
                                    }}
                                  />
                                </Space>
                                {modelAware?.description ? <Typography.Text theme="secondary">{modelAware.description}</Typography.Text> : null}
                              </Space>
                            </Card>
                          );
                        }
                        return (
                          <ParamField
                            key={f.name}
                            field={f}
                            value={formParams[f.name] ?? ''}
                            onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: v }))}
                            optionsOverride={modelAware?.optionsOverride}
                            disabled={Boolean(modelAware?.disabled)}
                            description={modelAware?.description}
                          />
                        );
                      })}
                  </Space>

                  <div className="podi-run-action-bar">
                    <div>
                      <Typography.Text strong>{requiresImage && !formUrl.trim() ? '等待主图' : '参数已就绪'}</Typography.Text>
                      <div>
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {requiresImage && !formUrl.trim() ? '请先上传或粘贴主图 URL。' : '可提交运行；下方文档只用于业务接入核对。'}
                        </Typography.Text>
                      </div>
                    </div>
                    <Button
                      theme="primary"
                      loading={isRunning}
                      disabled={isRunning || (requiresImage ? !formUrl.trim() : false)}
                      onClick={() => void runTool()}
                    >
                      开始生成
                    </Button>
                  </div>

                  <IntegrationDocBlock
                    doc={doc}
                    title={integrationDocTitle}
                    description={integrationDocDescription}
                    expanded={showIntegrationDoc}
                    onToggle={() => setShowIntegrationDoc((prev) => !prev)}
                    onCopy={copyIntegrationDoc}
                  />
                </Space>
              )}
            </Card>
          </Col>

          <Col xs={12} xl={7}>
            <Card
              bordered
              className="podi-eval-panel podi-eval-panel--result"
              title={
                <div className="podi-panel-title">
                  <strong>结果与排障</strong>
                  <span>看当前任务状态、出图数量、调试链接和失败提示。</span>
                </div>
              }
            >
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Typography.Text theme="secondary">图片可放大预览；视频、文字/VL 和结构化结果会单独展示。下方历史可筛选/打标。</Typography.Text>
	                {(() => {
	                  const latest = toolRuns[0] || null;
	                  const status = String(latest?.status || '');
	                  const rawCount = Number((latest?.parameters_json as any)?.count);
	                  const expectedCount =
	                    Number.isFinite(rawCount) && rawCount > 1 ? Math.min(Math.max(rawCount, 2), 12) : latest ? 1 : 0;
	                  const latestOutput = latest ? getRunOutputDescriptor(latest) : null;
	                  const imgs = latestOutput?.imageUrls || [];
	                  const videos = latestOutput?.videoUrls || [];
	                  const remain = latest ? Math.max(0, expectedCount - imgs.length) : 0;
	                  const outputIp = latest ? extractOutputField((latest as any).result_output_json, 'ip') : '';

                  return (
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      <Card bordered title="当前运行状态">
                        {!latest ? (
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Alert theme="info" message="暂无记录（先在左侧运行一次）。" />
                            <Typography.Text theme="secondary">
                              提示：多数工作流 50~80s 出图；如长时间无输出，可点右上 debug_url 排查。
                            </Typography.Text>
                          </Space>
                        ) : (
                          <Row gutter={[12, 12]}>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">状态</Typography.Text>
                                <StatusBadge status={status} />
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">测评记录</Typography.Text>
                                <Typography.Text style={{ fontFamily: 'monospace' }} ellipsis>
                                  {latest.id}
                                </Typography.Text>
                              </Space>
                            </Col>
                            {latest.podi_task_id ? (
                              <Col xs={12} md={4}>
                                <Space direction="vertical" size={2}>
                                  <Typography.Text theme="secondary">中台任务</Typography.Text>
                                  <Typography.Text style={{ fontFamily: 'monospace' }} ellipsis>
                                    {latest.podi_task_id}
                                  </Typography.Text>
                                </Space>
                              </Col>
                            ) : null}
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">预期出图</Typography.Text>
                                <Typography.Text>{expectedCount || '—'}</Typography.Text>
                              </Space>
                            </Col>
	                            <Col xs={12} md={4}>
	                              <Space direction="vertical" size={2}>
	                                <Typography.Text theme="secondary">已完成</Typography.Text>
	                                <Typography.Text>{latestOutput?.label || imgs.length}</Typography.Text>
	                              </Space>
	                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">创建时间</Typography.Text>
                                <Typography.Text>{fmtTime(latest.created_at)}</Typography.Text>
                              </Space>
                            </Col>
                            {outputIp ? (
                              <Col xs={12} md={4}>
                                <Space direction="vertical" size={2}>
                                  <Typography.Text theme="secondary">执行节点</Typography.Text>
                                  <Typography.Text style={{ fontFamily: 'monospace' }}>{outputIp}</Typography.Text>
                                </Space>
                              </Col>
                            ) : null}
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">操作</Typography.Text>
                                <Space>
                                  {latest.coze_debug_url ? (
                                    <Button
                                      size="small"
                                      variant="outline"
                                      onClick={() => window.open(latest.coze_debug_url!, '_blank', 'noreferrer')}
                                    >
                                      调试链接
                                    </Button>
                                  ) : null}
                                  {latest.error_message ? (
                                    <Button
                                      size="small"
                                      variant="outline"
                                      theme="danger"
                                      onClick={() => pushNotice('error', latest.error_message || '生成失败')}
                                    >
                                      查看错误
                                    </Button>
                                  ) : null}
                                </Space>
                              </Space>
                            </Col>
                            {latest.error_message ? (
                              <Col span={12}>
                                <Alert theme="error" message={toDisplayErrorMessage(latest.error_message)} />
                              </Col>
                            ) : null}
                          </Row>
                        )}
                      </Card>

                      <div className="podi-latest-output-grid">
                        {!latest ? (
                          <Card bordered title="输出">
                            <Typography.Text theme="secondary">
                              暂无运行记录，先在左侧填写参数并点击“开始生成”。
                            </Typography.Text>
                          </Card>
                        ) : status === 'queued' || status === 'running' ? (
                          <>
                            {imgs.map((img, idx) => (
                              <ImageTile
                                key={`latest-${latest.id}-${idx}`}
                                url={img}
                                title={`最新结果 #${idx + 1}`}
                                onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
                              />
                            ))}
                            {Array.from({ length: remain }).map((_, idx) => (
                              <SkeletonTile
                                key={`sk-${latest.id}-${idx}`}
                                title={`生成中… #${imgs.length + idx + 1}`}
                                subtitle={`run: ${latest.id}`}
                              />
                            ))}
                          </>
	                        ) : status === 'failed' ? (
	                          <Alert theme="error" message={`生成失败（run: ${latest.id}）：${toDisplayErrorMessage(latest.error_message || '—')}`} />
	                        ) : imgs.length > 0 ? (
	                          imgs.map((img, idx) => (
	                            <ImageTile
	                              key={`latest-${idx}`}
	                              url={img}
	                              title={`最新结果 #${idx + 1}`}
	                              onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
	                            />
	                          ))
	                        ) : videos.length > 0 ? (
	                          videos.map((video, idx) => (
	                            <Card key={`latest-video-${idx}`} bordered title={`结果视频 #${idx + 1}`}>
	                              <Space direction="vertical" size="small" style={{ width: '100%' }}>
	                                <Typography.Text theme="secondary" ellipsis>
	                                  {video}
	                                </Typography.Text>
	                                <Button size="small" variant="outline" onClick={() => window.open(video, '_blank', 'noreferrer')}>
	                                  打开视频
	                                </Button>
	                              </Space>
	                            </Card>
	                          ))
	                        ) : (
	                          <Card bordered title="输出">
	                            {(() => {
	                              const jsonPreview = latestOutput?.preview || '';
	                              return jsonPreview ? (
                                <pre
                                  style={{
                                    maxHeight: 420,
                                    overflow: 'auto',
                                    border: '1px solid var(--td-border-level-1-color)',
                                    background: 'var(--td-bg-color-secondarycontainer)',
                                    borderRadius: 8,
                                    padding: 12,
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    whiteSpace: 'pre-wrap',
                                  }}
                                >
                                  {jsonPreview}
                                </pre>
                              ) : (
	                                <Typography.Text theme="secondary">该次运行无图片输出。</Typography.Text>
	                              );
	                            })()}
	                          </Card>
	                        )}
                      </div>
                    </Space>
                  );
                })()}
              </Space>
            </Card>
          </Col>
        </Row>

        <Card bordered title={<Typography.Text strong>历史记录（打标区）</Typography.Text>}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {historyFocusMeta ? (
              <Alert
                theme={historyFocusMeta.theme}
                message={`${historyFocusMeta.label}：${historyFocusMeta.message}`}
                operation={
                  <Button
                    size="small"
                    variant="text"
                    onClick={() => {
                      setHistoryFocus('all');
                      setFilterStatus('all');
                    }}
                  >
                    查看全部记录
                  </Button>
                }
              />
            ) : null}
            <div className="podi-history-summary-board" aria-label="历史复盘汇总">
              <button
                type="button"
                className="podi-history-summary-card"
                onClick={() => {
                  setHistoryFocus('all');
                  setFilterStatus('all');
                  setFilterRating('all');
                  setFilterUnrated(false);
                }}
              >
                <span>当前显示</span>
                <strong>{historySummary.shown} / {historySummary.total}</strong>
                <em>全部记录</em>
              </button>
              <button
                type="button"
                className="podi-history-summary-card podi-history-summary-card--success"
                onClick={() => {
                  setHistoryFocus('succeeded');
                  setFilterStatus('all');
                }}
              >
                <span>成功</span>
                <strong>{historySummary.success}</strong>
                <em>可用于质量对照</em>
              </button>
              <button
                type="button"
                className="podi-history-summary-card podi-history-summary-card--warning"
                onClick={() => {
                  setHistoryFocus('no_output');
                  setFilterStatus('all');
                }}
              >
                <span>成功无回填</span>
                <strong>{historySummary.noOutput}</strong>
                <em>优先查回调链路</em>
              </button>
              <button
                type="button"
                className="podi-history-summary-card podi-history-summary-card--danger"
                onClick={() => {
                  setHistoryFocus('failed');
                  setFilterStatus('all');
                }}
              >
                <span>失败</span>
                <strong>{historySummary.failed}</strong>
                <em>优先看错误码</em>
              </button>
              <button
                type="button"
                className="podi-history-summary-card podi-history-summary-card--primary"
                onClick={() => {
                  setHistoryFocus('running');
                  setFilterStatus('all');
                }}
              >
                <span>排队/运行</span>
                <strong>{historySummary.running}</strong>
                <em>观察是否卡住</em>
              </button>
              <button
                type="button"
                className="podi-history-summary-card"
                onClick={() => {
                  setHistoryFocus('all');
                  setFilterUnrated(true);
                }}
              >
                <span>未打分</span>
                <strong>{historySummary.unrated}</strong>
                <em>待人工复盘</em>
              </button>
            </div>
            <FilterBar
              title="筛选器"
              description="每条记录包含原图 + 结果图；支持筛选、评分与备注。"
              controls={
                <>
                  <Select
                    value={filterStatus}
                    onChange={(v) => {
                      setHistoryFocus('all');
                      setFilterStatus(String(v));
                    }}
                    style={{ width: 140 }}
                    options={[
                      { label: '全部状态', value: 'all' },
                      { label: '排队中', value: 'queued' },
                      { label: '执行中', value: 'running' },
                      { label: '成功', value: 'succeeded' },
                      { label: '失败', value: 'failed' },
                    ]}
                  />
                  <Select
                    value={filterRating}
                    onChange={(v) => setFilterRating(String(v))}
                    style={{ width: 140 }}
                    options={[
                      { label: '全部评分', value: 'all' },
                      ...[1, 2, 3, 4, 5].map((n) => ({ label: String(n), value: String(n) })),
                    ]}
                  />
                  <div className="podi-inline">
                    <Switch value={filterUnrated} onChange={(v) => setFilterUnrated(Boolean(v))} />
                    <Typography.Text theme="secondary">未打分</Typography.Text>
                  </div>
                  <Input
                    value={search}
                    onChange={(v) => setSearch(String(v))}
                    style={{ width: 240 }}
                    placeholder="搜索备注/错误…"
                    clearable
                  />
                </>
              }
            />
            {filteredRuns.map((run) => (
              <HistoryRow
                key={run.id}
                run={run}
                onAnnotate={annotate}
                onOpenImage={(url, title) => setLightbox({ url, title })}
              />
            ))}
            {filteredRuns.length === 0 ? <Typography.Text theme="secondary">暂无记录。</Typography.Text> : null}
          </Space>
        </Card>
      </Space>,
    );
  }

  // Home (toolbox) view
  const categorySummaries = orderedCategories.map((category) => {
    const items = grouped[category] || [];
    let recentRunCount = 0;
    let recentSuccessCount = 0;
    let recentFailureCount = 0;
    let recentRunningCount = 0;
    let recentNoOutputCount = 0;
    for (const wf of items) {
      const metric = metrics[wf.id];
      recentRunCount += Number(metric?.recentRunCount || 0);
      recentSuccessCount += Number(metric?.recentSuccessCount || 0);
      recentFailureCount += Number(metric?.recentFailureCount || 0);
      recentRunningCount += Number(metric?.recentRunningCount || 0);
      recentNoOutputCount += Number(metric?.recentNoOutputCount || 0);
    }
    let theme: 'default' | 'success' | 'warning' | 'danger' | 'primary' = 'default';
    let label = recentRunCount > 0 ? '有评测记录' : '暂无近期记录';
    if (recentNoOutputCount > 0) {
      theme = 'warning';
      label = '有未回填';
    } else if (recentFailureCount > 0 && recentSuccessCount <= 0) {
      theme = 'danger';
      label = '最近失败';
    } else if (recentFailureCount > 0) {
      theme = 'warning';
      label = '有失败样本';
    } else if (recentRunningCount > 0 && recentSuccessCount <= 0) {
      theme = 'primary';
      label = '运行中';
    } else if (recentSuccessCount > 0) {
      theme = 'success';
      label = '最近可用';
    }
    return {
      category,
      count: items.length,
      visual: getCategoryVisual(category),
      recentRunCount,
      recentSuccessCount,
      recentFailureCount,
      recentNoOutputCount,
      theme,
      label,
    };
  });
  return shell(
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {bootstrapLoading || workflowListStatus === 'loading' ? <Alert theme="info" message="正在加载功能清单和评分数据…" /> : null}
      {workflowListStatus === 'error' ? (
        <WorkflowListErrorState scope="public" error={workflowListError} onRetry={() => void loadWorkflowList()} />
      ) : null}
      <div className="podi-eval-category-board" aria-label="业务分类总览">
        {categorySummaries.map((item) => (
          <button
            key={item.category}
            type="button"
            className={`podi-eval-category-tile${item.category === activeCategory ? ' podi-eval-category-tile--active' : ''}`}
            style={{ '--podi-category-accent': item.visual.accent } as CSSProperties}
            onClick={() => setActiveCategory(item.category)}
          >
            <span className="podi-eval-category-tile__icon">{item.visual.icon}</span>
            <span className="podi-eval-category-tile__body">
              <span className="podi-eval-category-tile__name">{item.category}</span>
              <span className="podi-eval-category-tile__summary">{item.visual.summary}</span>
              <span className="podi-eval-category-tile__meta">
                {item.count} 个功能 · 近 72 小时成功 {item.recentSuccessCount} 次
              </span>
            </span>
            <Tag theme={item.theme} variant="light">
              {item.label}
            </Tag>
          </button>
        ))}
      </div>
      <ActionBar
        title={`功能卡片 · ${toolList.length} 个`}
        description="直接选择要评测的功能；链路健康和队列问题统一到任务追踪中查看。"
        actions={
          <Space>
            <Button variant="outline" onClick={() => void refreshMetrics()}>
              刷新评分
            </Button>
            <Button variant="outline" onClick={() => setActiveView('tasks')}>
              查看任务追踪
            </Button>
          </Space>
        }
      />
      {!bootstrapLoading && workflowListStatus === 'success' && toolList.length === 0 ? (
        <Alert theme="info" message="该分类暂无功能。" />
      ) : null}
      <div className="podi-tool-grid">
        {toolList.map((wf) => (
          <ToolCard
            key={wf.id}
            wf={wf}
            active={false}
            metric={metrics[wf.id]}
            onClick={() => openTool(wf)}
            onOpenRecent={(focus) => openTool(wf, focus)}
          />
        ))}
      </div>
    </Space>
  );
}

function HistoryRow({
  run,
  onAnnotate,
  onOpenImage,
}: {
  run: RunWithLatest;
  onAnnotate: (runId: string, rating: number, comment: string) => Promise<void>;
  onOpenImage: (url: string, title?: string) => void;
}) {
  const inputUrl = (run.input_oss_urls_json || [])[0] || '';
  const output = getRunOutputDescriptor(run);
  const outputs = output.imageUrls;
  const [rating, setRating] = useState<number>(run.latest_annotation?.rating || 0);
  const [savedComment, setSavedComment] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [commentDraft, setCommentDraft] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [savingRating, setSavingRating] = useState(false);
  const [savingComment, setSavingComment] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string>('');
  const [rowError, setRowError] = useState<string>('');

  const commentDirty = commentDraft !== savedComment;
  const jsonPreview = output.preview;
  const displayParams = filterDisplayParams(run.parameters_json as Record<string, unknown> | null);
  const paramsPreview = formatJsonPreview(displayParams, 1000);
  const outputIp = extractOutputField((run as any).result_output_json, 'ip');
  const submitStage = run.submit_status || (run.coze_execute_id || run.podi_task_id ? 'submitted' : '');
  const callbackStage =
    run.callback_status ||
    (outputs.length > 0 || jsonPreview
      ? 'success'
      : run.status === 'failed'
        ? 'failed'
        : run.status === 'running' || run.status === 'queued'
          ? 'waiting'
          : '');
  const finalStage = run.final_status || run.status;
  const outputLabel =
    outputs.length > 0
      ? output.label
      : output.hasOutput
        ? output.label
        : isSucceededWithoutVisibleOutput(run)
          ? '成功无回填'
          : run.status === 'running' || run.status === 'queued'
            ? '等待结果'
            : '无结果';
  const stageItems = [
    { label: '提交', value: formatEvalStageStatus('submit', submitStage), tone: getEvalStageTone(submitStage) },
    { label: '回填', value: formatEvalStageStatus('callback', callbackStage), tone: getEvalStageTone(callbackStage) },
    { label: '最终', value: formatEvalStageStatus('final', finalStage), tone: getEvalStageTone(finalStage) },
    { label: '输出', value: outputLabel, tone: getOutputTone(outputLabel) },
  ];

  // Sync state when the latest annotation changes due to refresh/polling.
  // Do not clobber an in-progress comment draft.
  useEffect(() => {
    const nextRating = run.latest_annotation?.rating || 0;
    const nextComment = String(run.latest_annotation?.comment || '');
    setRating(nextRating);
    setSavedComment(nextComment);
    setCommentDraft((prev) => (prev === savedComment ? nextComment : prev));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.latest_annotation?.created_at]);

  return (
    <Card bordered>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div className="podi-history-row-head">
          <div className="podi-history-row-head__meta">
            <Typography.Text strong style={{ fontFamily: 'monospace' }} ellipsis>
              记录：{run.id}
            </Typography.Text>
            <div className="podi-history-row-head__meta-line">
              <StatusBadge status={run.status} />
              <Typography.Text theme="secondary">耗时：{formatDuration(run.duration_ms)}</Typography.Text>
              <Typography.Text theme="secondary">{fmtTime(run.created_at)}</Typography.Text>
              {run.podi_task_id ? (
                <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                  中台：{run.podi_task_id}
                </Typography.Text>
              ) : null}
              <Typography.Text theme="secondary">成本：{formatEvalRunCost(run)}</Typography.Text>
              {outputIp ? (
                <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                  节点：{outputIp}
                </Typography.Text>
              ) : null}
              {run.coze_debug_url ? (
                <Button
                  size="small"
                  variant="text"
                  onClick={() => window.open(run.coze_debug_url || '', '_blank', 'noreferrer')}
                >
                  调试链接
                </Button>
              ) : null}
            </div>
            <div className="podi-history-stage-strip" aria-label="任务阶段状态">
              {stageItems.map((item) => (
                <div key={`${run.id}-${item.label}`} className={`podi-history-stage podi-history-stage--${item.tone}`}>
                  <span>{item.label}</span>
                  <strong title={item.value}>{item.value}</strong>
                </div>
              ))}
            </div>
            {run.error_message ? <Alert theme="error" message={toDisplayErrorMessage(run.error_message)} /> : null}
          </div>

          <div className="podi-history-row-head__rate">
            <div className="podi-inline">
              <Typography.Text theme="secondary">评分</Typography.Text>
              <Rate
                value={rating}
                onChange={async (v) => {
                  const next = Number(v) || 0;
                  if (savingRating || savingComment) return;
                  setRating(next);
                  setSavingRating(true);
                  setRowError('');
                  try {
                    await onAnnotate(run.id, next, savedComment);
                    setLastSavedAt(new Date().toISOString());
                  } catch (err) {
                    console.error(err);
                    setRowError(String((err as any)?.message || err));
                  } finally {
                    setSavingRating(false);
                  }
                }}
              />
            </div>
            <Typography.Text theme="secondary" style={{ fontSize: 12, textAlign: 'right' }}>
              {savingRating || savingComment ? '保存中…' : lastSavedAt ? `已保存 ${fmtTime(lastSavedAt)}` : rating ? '已评分' : '未评分'}
            </Typography.Text>
          </div>
        </div>

        <Row gutter={[12, 12]} className="podi-history-row-grid">
          <Col xs={24} lg={8} className="podi-history-row-col">
            <Card
              bordered
              title={
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>备注</Typography.Text>
                  <Button
                    size="small"
                    theme="primary"
                    disabled={!commentDirty || savingRating || savingComment}
                    loading={savingComment}
                    onClick={async () => {
                      if (!rating) {
                        setRowError('请先评分（1-5），再保存备注。');
                        return;
                      }
                      setSavingComment(true);
                      setRowError('');
                      try {
                        await onAnnotate(run.id, rating, commentDraft);
                        setSavedComment(commentDraft);
                        setLastSavedAt(new Date().toISOString());
                      } catch (err) {
                        console.error(err);
                        setRowError(String((err as any)?.message || err));
                      } finally {
                        setSavingComment(false);
                      }
                    }}
                  >
                    保存
                  </Button>
                </Space>
              }
            >
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                {rowError ? <Alert theme="error" message={rowError} /> : null}
                <Textarea
                  value={commentDraft}
                  onChange={(v) => setCommentDraft(String(v))}
                  autosize={{ minRows: 3, maxRows: 8 }}
                  placeholder="问题描述/优化建议…"
                />
                <div className="podi-history-row-params">
                  <Typography.Text theme="secondary">参数</Typography.Text>
                  {paramsPreview ? (
                    <pre className="podi-history-row-params__pre">{paramsPreview}</pre>
                  ) : (
                    <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                      当前记录仅包含图片 URL。
                    </Typography.Text>
                  )}
                </div>
              </Space>
            </Card>
          </Col>
          <Col xs={24} lg={16} className="podi-history-row-col">
            <Card bordered title="原图 / 结果">
              <div className="podi-image-grid">
                {inputUrl ? (
                  <Button
                    variant="outline"
                    onClick={() => onOpenImage(inputUrl, '原图')}
                    style={{ padding: 6, height: 'auto' }}
                  >
                    <img src={inputUrl} alt="input" style={{ height: 128, width: '100%', objectFit: 'contain' }} />
                  </Button>
                ) : null}

                {outputs.length > 0 ? (
                  outputs.map((u, idx) => (
                    <Button
                      key={`${run.id}-out-${idx}`}
                      variant="outline"
                      onClick={() => onOpenImage(u, `结果图 #${idx + 1}`)}
                      style={{ padding: 6, height: 'auto' }}
                    >
                      <img src={u} alt="output" loading="lazy" style={{ height: 128, width: '100%', objectFit: 'contain' }} />
                    </Button>
                  ))
                ) : output.videoUrls.length > 0 ? (
                  output.videoUrls.map((u, idx) => (
                    <Button
                      key={`${run.id}-video-${idx}`}
                      variant="outline"
                      onClick={() => window.open(u, '_blank', 'noreferrer')}
                      style={{ padding: 12, height: 'auto', minHeight: 96 }}
                    >
                      <Space direction="vertical" size={2}>
                        <Typography.Text strong>结果视频 #{idx + 1}</Typography.Text>
                        <Typography.Text theme="secondary" ellipsis style={{ maxWidth: 260 }}>
                          {u}
                        </Typography.Text>
                      </Space>
                    </Button>
                  ))
                ) : run.status !== 'running' && run.status !== 'queued' ? (
                  jsonPreview ? (
                    <pre
                      className="podi-image-grid__full"
                      style={{
                        maxHeight: 280,
                        overflow: 'auto',
                        border: '1px solid var(--td-border-level-1-color)',
                        background: 'var(--td-bg-color-secondarycontainer)',
                        borderRadius: 8,
                        padding: 12,
                        fontFamily: 'monospace',
                        fontSize: 12,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {jsonPreview}
                    </pre>
                  ) : (
                    <Typography.Text theme="secondary">暂无输出</Typography.Text>
                  )
                ) : (
                  <Typography.Text theme="secondary">生成中…</Typography.Text>
                )}
              </div>
            </Card>
          </Col>
        </Row>
      </Space>
    </Card>
  );
}

function AdminWorkflowRow({
  wf,
  adminToken,
  onSaved,
  onAuthInvalid,
}: {
  wf: EvalWorkflowVersion;
  adminToken: string;
  onSaved: (next: EvalWorkflowVersion) => void;
  onAuthInvalid: () => void;
}) {
  const [name, setName] = useState(wf.name);
  const [notes, setNotes] = useState(wf.notes || '');
  const [category, setCategory] = useState(getWorkflowCategory(wf));
  const [status, setStatus] = useState(wf.status);
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState<string>('');

  const dirty = name !== wf.name || notes !== (wf.notes || '') || category !== getWorkflowCategory(wf) || status !== wf.status;
  const missingParamsSchema = !wf.parameters_schema || (Array.isArray(wf.parameters_schema) && wf.parameters_schema.length === 0);
  const missingOutputSchema = !wf.output_schema || (Array.isArray(wf.output_schema) && wf.output_schema.length === 0);
  const schemaMissingLabels = [
    missingParamsSchema ? 'parameters_schema' : null,
    missingOutputSchema ? 'output_schema' : null,
  ].filter(Boolean);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-slate-500">workflow_id</div>
          <div className="mt-1 font-mono text-xs text-slate-300 break-all">{wf.workflow_id}</div>
          {schemaMissingLabels.length > 0 ? (
            <Alert
              theme="warning"
              message={`Schema 缺失：${schemaMissingLabels.join(' / ')}。请补齐以完善文档与表单。`}
            />
          ) : null}

          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <label className="block">
              <div className="text-xs text-slate-300">名称</div>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              />
            </label>
            <label className="block">
              <div className="text-xs text-slate-300">分类</div>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              >
                {CATEGORY_ORDER.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="block mt-3">
            <div className="text-xs text-slate-300">备注</div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
            />
          </label>
        </div>

        <div className="shrink-0 w-full lg:w-56">
          <label className="block">
            <div className="text-xs text-slate-300">状态</div>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </label>

          <button
            type="button"
            disabled={!dirty || saving}
            onClick={async () => {
              setSaving(true);
              setRowError('');
              try {
                const next = await evalApi.adminUpdateWorkflowVersion(adminToken, wf.id, {
                  name,
                  notes,
                  category,
                  status,
                });
                onSaved(next);
              } catch (err) {
                console.error(err);
                const message = String((err as any)?.message || err);
                setRowError(message);
                if (message.includes('认证已失效')) {
                  onAuthInvalid();
                }
              } finally {
                setSaving(false);
              }
            }}
            className={`mt-3 w-full rounded-xl px-3 py-2 text-sm font-semibold transition ${
              !dirty || saving ? 'bg-slate-700/40 text-slate-400' : 'bg-emerald-500/80 text-white hover:bg-emerald-500'
            }`}
          >
            {saving ? '保存中…' : '保存'}
          </button>
          {rowError ? <div className="mt-2 text-xs text-rose-300 break-words">{rowError}</div> : null}

          <div className="mt-3 text-xs text-slate-500">
            更新时间：{fmtTime(wf.updated_at)}
          </div>
        </div>
      </div>
    </div>
  );
}
