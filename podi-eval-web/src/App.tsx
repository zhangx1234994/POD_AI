import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode, MouseEvent as ReactMouseEvent } from 'react';
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
import zhCN from 'tdesign-react/es/locale/zh_CN';
import { evalApi } from './api';
import type { EvalRun, EvalWorkflowVersion, SchemaField, WorkflowDoc } from './types';

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

type LoraBatchWorkflowMeta = {
  workflow: EvalWorkflowVersion;
  urlFieldName: string;
  loraField: SchemaField | null;
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

type LoraBatchItem = {
  key: string;
  batchId?: string;
  sourceKey?: string;
  fileName: string;
  repeatIndex: number;
  status: LoraBatchItemStatus;
  runId?: string;
  inputUrl?: string;
  error?: string;
  runStatus?: LoraBatchRunStatus;
  outputCount?: number;
  runError?: string;
  outputUrls?: string[];
  runPrompt?: string;
};

type LoraBatchSession = {
  batchId: string;
  workflowVersionId?: string | null;
  workflowName?: string | null;
  total: number;
  completed: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  latestCreatedAt?: string | null;
  latestUpdatedAt?: string | null;
};

// Keep the evaluation UI sidebar fixed to these 5 business-facing groups.
const CATEGORY_ORDER = ['花纹提取类', '图延伸类', '四方/两方连续图类', '图裂变', '通用类'];

const AI_EDITOR_WORKFLOW_ID = '7604714915110060032';
const LORA_BATCH_MAX_TASKS = 5000;

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

const normalizeCategory = (category: string | undefined | null): string => {
  const c = String(category || '').trim();
  if (!c) return '通用类';
  if (CATEGORY_ORDER.includes(c)) return c;
  // Legacy/internal keys -> business labels
  if (c === 'pattern_extract' || c === 'pattern' || c === 'pattern-extract') return '花纹提取类';
  if (c === 'image_extend' || c === 'image_extension' || c === '图扩展' || c === '图延伸') return '图延伸类';
  if (c === 'continuous_pattern' || c === 'continuous' || c === 'lianxu') return '四方/两方连续图类';
  if (c === '图裂变' || c === 'variation' || c === 'image_variation' || c === 'liebain' || c === 'liebiam') return '图裂变';
  if (c === 'general' || c === 'common') return '通用类';
  return '通用类';
};

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
  imageSize: { width: number; height: number };
}): string => {
  const { rawPrompt, marks, refUrls, imageSize } = args;
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
  normalizeCategory(wf?.category) === '图裂变';

const sanitizeWorkflowDoc = (wf: WorkflowDoc): WorkflowDoc => {
  if (normalizeCategory(wf.category) !== '图裂变') return wf;
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

const filterImageUrls = (urls: unknown): string[] => {
  if (!Array.isArray(urls)) return [];
  return urls
    .filter((u) => typeof u === 'string')
    .map((u) => u.trim())
    .filter((u) => u && isLikelyImageUrl(u));
};

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
}: {
  wf: EvalWorkflowVersion;
  active: boolean;
  metric?: { ratingCount: number; avgRating: number | null };
  onClick: () => void;
}) {
  const ratingText = metric?.avgRating ? metric.avgRating.toFixed(2) : '—';
  const ratingCountText = metric?.ratingCount ? `${metric.ratingCount}票` : '未评分';
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick();
      }}
      style={{ cursor: 'pointer', height: '100%' }}
    >
      <Card
        bordered
        style={{
          height: '100%',
          borderColor: active ? 'var(--td-brand-color)' : undefined,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={2} style={{ minWidth: 0 }}>
              <Typography.Text strong ellipsis>
                {wf.name}
              </Typography.Text>
              <Typography.Text theme="secondary" style={{ fontSize: 12 }} ellipsis>
                {wf.workflow_id}
              </Typography.Text>
            </Space>
            <Space direction="vertical" size={2} style={{ alignItems: 'flex-end' }}>
              <Typography.Text>{ratingText}</Typography.Text>
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {ratingCountText}
              </Typography.Text>
            </Space>
          </Space>

          <div
            className="podi-clamp-2"
            style={{
              marginTop: 8,
              fontSize: 12,
              lineHeight: '18px',
              minHeight: 36, // Reserve exactly 2 lines so all cards align.
              color: 'var(--td-text-color-secondary)',
            }}
          >
            {wf.notes || '—'}
          </div>

          <div style={{ marginTop: 12 }}>
            <Space breakLine>
              <Tag variant="light">{wf.version}</Tag>
              <Tag variant="light">{normalizeCategory(wf.category)}</Tag>
            </Space>
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
}: {
  field: SchemaField;
  value: string;
  onChange: (v: string) => void;
}) {
  const label = field.label ?? field.name;
  const required = Boolean(field.required);
  const options = Array.isArray((field as any).options) ? ((field as any).options as any[]) : null;
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
          options={options.map((opt) => ({ label: String(opt.label ?? opt.value), value: String(opt.value) }))}
        />
      </Space>
    );
  }

  if (type === 'textarea') {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text>
          {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
        </Typography.Text>
        <Textarea value={value} onChange={(v) => onChange(String(v))} autosize={{ minRows: 3, maxRows: 8 }} />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Typography.Text>
        {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
      </Typography.Text>
      <Input value={value} onChange={(v) => onChange(String(v))} />
    </Space>
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
                实时刷新：queued/running 会持续轮询；ComfyUI 类回调出图后才算完成。
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
                <Tag variant="light">{row.status}</Tag>
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  耗时：{formatDuration(row.duration_ms)}
                </Typography.Text>
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
              const outputs = filterImageUrls(row.result_image_urls_json);
              const jsonPreview = formatJsonPreview((row as any).result_output_json, 240);
              if (outputs.length > 0) {
                return (
                  <Space breakLine>
                    <Typography.Text theme="secondary">{outputs.length} 张</Typography.Text>
                    <Button size="small" variant="text" onClick={() => window.open(outputs[0], '_blank', 'noreferrer')}>
                      打开首张
                    </Button>
                  </Space>
                );
              }
              if (jsonPreview) {
                return (
                  <Typography.Text theme="secondary" style={{ fontFamily: 'monospace', fontSize: 12 }} ellipsis>
                    {jsonPreview}
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
                    debug_url
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
      className="relative block rounded-2xl border border-slate-800 bg-slate-950/30 p-2 hover:border-slate-700"
    >
      {!loaded && !failed ? (
        <div className="absolute inset-2 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-center text-xs text-slate-400">
          加载中…
        </div>
      ) : null}
      {failed ? (
        <div className="absolute inset-2 rounded-xl border border-rose-500/30 bg-rose-500/5 flex flex-col items-center justify-center gap-2 text-xs text-rose-200 px-3">
          <div className="font-semibold">图片加载失败</div>
          <div className="break-all text-[10px] text-rose-300/80">{url}</div>
        </div>
      ) : null}
      <img
        src={url}
        alt={title}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className="h-56 w-full rounded-xl object-contain"
      />
    </button>
  );
}

function SkeletonTile({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="relative block rounded-2xl border border-slate-800 bg-slate-950/30 p-2">
      <div className="h-56 w-full rounded-xl border border-slate-800 bg-slate-950/60 animate-pulse" />
      <div className="mt-2 px-1">
        <div className="text-xs font-semibold text-slate-200">{title}</div>
        {subtitle ? <div className="mt-1 text-[11px] text-slate-500 break-all">{subtitle}</div> : null}
      </div>
    </div>
  );
}

type ThemeMode = 'light' | 'dark';

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem('podi.eval.theme');
  return stored === 'dark' ? 'dark' : 'light';
}

export function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme());
  useEffect(() => {
    const isDark = theme === 'dark';
    // TDesign dark mode is driven by `t-theme-dark` class.
    document.documentElement.classList.toggle('t-theme-dark', isDark);
    // Keep Tailwind dark variants working during migration.
    document.documentElement.classList.toggle('dark', isDark);
    window.localStorage.setItem('podi.eval.theme', theme);
  }, [theme]);

  const pushNotice = useCallback((type: 'error' | 'success' | 'info', message: string) => {
    const content = message || '未知错误';
    if (type === 'error') MessagePlugin.error({ content, duration: 5000 });
    else if (type === 'success') MessagePlugin.success({ content, duration: 3500 });
    else MessagePlugin.info({ content, duration: 3500 });
  }, []);

  const [raterId, setRaterId] = useState<string>('');
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [metrics, setMetrics] = useState<Record<string, { ratingCount: number; avgRating: number | null }>>({});

  const [activeCategory, setActiveCategory] = useState<string>('通用类');
  const [activeView, setActiveView] = useState<'home' | 'tool' | 'tasks' | 'admin' | 'docs' | 'loraBatch'>('home');
  const [selectedTool, setSelectedTool] = useState<EvalWorkflowVersion | null>(null);

  const [formUrl, setFormUrl] = useState('');
  const [formParams, setFormParams] = useState<Record<string, string>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

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
  const [search, setSearch] = useState<string>('');
  const [lightbox, setLightbox] = useState<{ url: string; title?: string } | null>(null);

  // Simple "private" admin token stored in localStorage.
  const [adminToken, setAdminToken] = useState<string>(() => localStorage.getItem('podi_eval_admin_token') || '');
  const [adminWorkflows, setAdminWorkflows] = useState<EvalWorkflowVersion[]>([]);
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
  const [batchSessionId, setBatchSessionId] = useState<string>('');
  const [batchSessions, setBatchSessions] = useState<LoraBatchSession[]>([]);
  const [batchItems, setBatchItems] = useState<LoraBatchItem[]>([]);
  const [batchReviewMap, setBatchReviewMap] = useState<Record<string, LoraBatchReview>>({});
  const [batchSubmitting, setBatchSubmitting] = useState<boolean>(false);
  const [batchLoadingSessions, setBatchLoadingSessions] = useState<boolean>(false);
  const [batchLoadingItems, setBatchLoadingItems] = useState<boolean>(false);
  const [batchSessionLoadError, setBatchSessionLoadError] = useState<string>('');
  const [batchItemsLoadError, setBatchItemsLoadError] = useState<string>('');
  const [batchStopping, setBatchStopping] = useState<boolean>(false);
  const batchStopRef = useRef<boolean>(false);
  const batchFileInputRef = useRef<HTMLInputElement | null>(null);
  const batchItemsRef = useRef<LoraBatchItem[]>([]);
  const batchPollCursorRef = useRef<number>(0);

  const workflowMap = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion> = {};
    for (const wf of workflows) m[wf.id] = wf;
    return m;
  }, [workflows]);

  const grouped = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion[]> = {};
    for (const wf of workflows) {
      const key = normalizeCategory(wf.category);
      m[key] = m[key] || [];
      m[key].push(wf);
    }
    return m;
  }, [workflows]);

  const orderedCategories = useMemo(() => {
    // Always show the fixed business categories in sidebar.
    return CATEGORY_ORDER.slice();
  }, [grouped]);

  const toolList = useMemo(() => {
    const list = (grouped[activeCategory] || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    return list;
  }, [grouped, activeCategory]);

  const loraBatchWorkflows = useMemo<LoraBatchWorkflowMeta[]>(() => {
    const metas: LoraBatchWorkflowMeta[] = [];
    for (const wf of workflows) {
      const fields = getFields(wf);
      const urlField = fields.find((f) => f.name === 'url' || f.name === 'Url') || null;
      if (!urlField) continue;
      const loraField =
        fields.find((f) => String(f.name || '').toLowerCase() === 'lora') ||
        fields.find((f) => String(f.name || '').toLowerCase().includes('lora')) ||
        null;
      if (!loraField) continue;
      metas.push({
        workflow: wf,
        urlFieldName: urlField.name,
        loraField,
        loraOptions: normalizeFieldOptions(loraField),
      });
    }
    metas.sort((a, b) => String(a.workflow.name || '').localeCompare(String(b.workflow.name || '')));
    return metas;
  }, [workflows]);

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
  const batchSessionOptions = useMemo(
    () =>
      batchSessions.map((item) => ({
        label: `${item.workflowName ? `${item.workflowName} · ` : ''}${item.batchId}（完成 ${item.completed}/${item.total}）`,
        value: item.batchId,
      })),
    [batchSessions],
  );
  const selectedBatchId = useMemo(() => {
    if (batchSessionId && batchSessions.some((item) => item.batchId === batchSessionId)) return batchSessionId;
    return String(batchSessions[0]?.batchId || '');
  }, [batchSessionId, batchSessions]);
  const visibleBatchItems = useMemo(
    () => (selectedBatchId ? batchItems.filter((item) => item.batchId === selectedBatchId) : []),
    [batchItems, selectedBatchId],
  );
  const batchSummary = useMemo(() => {
    const total = visibleBatchItems.length;
    const imageCount = new Set(visibleBatchItems.map((item) => item.sourceKey || item.fileName)).size;
    const repeatCount = imageCount > 0 ? Math.max(...visibleBatchItems.map((item) => item.repeatIndex || 1), 1) : 0;
    const submitted = visibleBatchItems.filter((item) => item.status === 'submitted' && Boolean(item.runId)).length;
    const completed = visibleBatchItems.filter((item) => item.runStatus === 'succeeded' || item.runStatus === 'failed').length;
    const generated = visibleBatchItems.filter((item) => item.runStatus === 'succeeded' && (item.outputCount || 0) > 0).length;
    const failed = visibleBatchItems.filter((item) => item.status === 'failed' || item.runStatus === 'failed').length;
    const active = visibleBatchItems.filter((item) => item.status === 'uploading' || item.status === 'submitting').length;
    const queuedOrRunning = visibleBatchItems.filter(
      (item) =>
        item.status === 'submitted' &&
        (!item.runStatus || item.runStatus === 'queued' || item.runStatus === 'running' || item.runStatus === 'unknown'),
    ).length;
    return { total, imageCount, repeatCount, submitted, completed, generated, failed, active, queuedOrRunning };
  }, [visibleBatchItems]);
  const buildBatchReviewKey = useCallback((runId: string, outputIndex: number) => `${runId}::${outputIndex}`, []);
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
  const batchComparisonGroups = useMemo(() => {
    const map = new Map<
      string,
      {
        key: string;
        fileName: string;
        inputUrl: string;
        totalRuns: number;
        completedRuns: number;
        failedRuns: number;
        waitingRuns: number;
        outputCount: number;
        lastError: string;
        outputs: Array<{ reviewKey: string; runId: string; outputIndex: number; url: string }>;
      }
    >();
    for (const item of visibleBatchItems) {
      if (!item.inputUrl) continue;
      const key = `${item.fileName}::${item.inputUrl}`;
      if (!map.has(key)) {
        map.set(key, {
          key,
          fileName: item.fileName,
          inputUrl: item.inputUrl,
          totalRuns: 0,
          completedRuns: 0,
          failedRuns: 0,
          waitingRuns: 0,
          outputCount: 0,
          lastError: '',
          outputs: [],
        });
      }
      const group = map.get(key)!;
      group.totalRuns += 1;
      if (item.runStatus === 'succeeded' || item.runStatus === 'failed') {
        group.completedRuns += 1;
      } else if (
        item.status === 'submitted' &&
        (!item.runStatus || item.runStatus === 'queued' || item.runStatus === 'running' || item.runStatus === 'unknown')
      ) {
        group.waitingRuns += 1;
      }
      if (item.status === 'failed' || item.runStatus === 'failed') {
        group.failedRuns += 1;
      }
      if (!group.lastError) {
        const msg = String(item.runError || item.error || '').trim();
        if (msg) group.lastError = msg;
      }
      const outputUrls = Array.isArray(item.outputUrls) ? item.outputUrls : [];
      for (let idx = 0; idx < outputUrls.length; idx += 1) {
        const outputIndex = idx + 1;
        const runRef = String(item.runId || item.key);
        group.outputs.push({
          reviewKey: buildBatchReviewKey(runRef, outputIndex),
          runId: String(item.runId || ''),
          outputIndex,
          url: outputUrls[idx],
        });
      }
      group.outputCount += outputUrls.length;
    }
    const out = Array.from(map.values());
    out.sort((a, b) => a.fileName.localeCompare(b.fileName));
    return out;
  }, [visibleBatchItems, buildBatchReviewKey]);

  const toolFields = useMemo(() => getFields(selectedTool), [selectedTool]);
  const requiresImage = useMemo(
    () => toolFields.some((f) => f.name === 'url' || f.name === 'Url'),
    [toolFields],
  );
  const isAiEditor = selectedTool?.workflow_id === AI_EDITOR_WORKFLOW_ID;
  const editorPromptPreview = useMemo(() => {
    if (!isAiEditor) return '';
    return buildEditorPrompt({
      rawPrompt: editorPrompt,
      marks: editorMarks,
      refUrls: editorRefs,
      imageSize: { width: editorImageMeta.naturalW, height: editorImageMeta.naturalH },
    });
  }, [editorPrompt, editorMarks, editorRefs, editorImageMeta, isAiEditor]);

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

  const loadBootstrap = async () => {
    try {
      const me = await evalApi.me();
      setRaterId(me.raterId);
      const wfs = await evalApi.listWorkflowVersions();
      setWorkflows(wfs || []);
      if (wfs && wfs.length > 0) {
        const counts: Record<string, number> = {};
        for (const wf of wfs) {
          const k = normalizeCategory(wf.category);
          counts[k] = (counts[k] || 0) + 1;
        }
        const firstNonEmpty = CATEGORY_ORDER.find((k) => (counts[k] || 0) > 0);
        setActiveCategory(firstNonEmpty || '通用类');
      }
      await refreshMetrics();
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

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

  useEffect(() => {
    void loadBootstrap();
  }, []);

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
    batchItemsRef.current = batchItems;
  }, [batchItems]);

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

  const mapRunToBatchItem = useCallback((run: EvalRun): LoraBatchItem | null => {
    const params = ((run.parameters_json || {}) as Record<string, unknown>) || {};
    const batchId = String(params.__batch_session_id || '').trim();
    if (!batchId) return null;
    const inputUrl =
      String(
        params.url ||
          params.Url ||
          params.URL ||
          (Array.isArray(run.input_oss_urls_json) ? run.input_oss_urls_json[0] : '') ||
          '',
      ).trim() || '';
    const fileName = String(params.__batch_file_name || '').trim() || inferFileNameFromUrl(inputUrl);
    const sourceKey =
      String(params.__batch_source_key || '').trim() || `${fileName}::${inputUrl || run.id}`;
    const repeatIndexRaw = Number(params.__batch_repeat_index || 1);
    const repeatIndex = Number.isFinite(repeatIndexRaw) && repeatIndexRaw > 0 ? Math.floor(repeatIndexRaw) : 1;
    const statusRaw = String(run.status || '').toLowerCase();
    let runStatus: LoraBatchRunStatus = 'unknown';
    if (statusRaw === 'queued') runStatus = 'queued';
    else if (statusRaw === 'running') runStatus = 'running';
    else if (statusRaw === 'failed') runStatus = 'failed';
    else if (statusRaw === 'succeeded' || statusRaw === 'success') runStatus = 'succeeded';
    const outputUrls = Array.isArray(run.result_image_urls_json)
      ? run.result_image_urls_json.map((u) => String(u || '').trim()).filter((u) => Boolean(u))
      : [];
    return {
      key: run.id,
      batchId,
      sourceKey,
      fileName,
      repeatIndex,
      status: runStatus === 'failed' ? 'failed' : 'submitted',
      runId: run.id,
      inputUrl,
      error: runStatus === 'failed' ? String(run.error_message || '') : undefined,
      runStatus,
      outputCount: outputUrls.length,
      outputUrls,
      runPrompt: String(params.prompt || ''),
      runError: runStatus === 'failed' ? String(run.error_message || '') : undefined,
    };
  }, []);

  const loadBatchSessions = useCallback(async (opts?: { silent?: boolean }) => {
    setBatchLoadingSessions(true);
    try {
      const res = await evalApi.listRunBatches({
        mine_only: true,
        limit: 200,
        offset: 0,
      });
      const items = Array.isArray(res.items) ? (res.items as LoraBatchSession[]) : [];
      setBatchSessions(items);
      setBatchSessionLoadError('');
      if (!batchSessionId && items[0]?.batchId) {
        setBatchSessionId(items[0].batchId);
      } else if (batchSessionId && !items.some((item) => item.batchId === batchSessionId)) {
        setBatchSessionId(items[0]?.batchId || '');
      }
    } catch (err) {
      const msg = String((err as any)?.message || err || '');
      setBatchSessionLoadError(msg || '加载失败');
      if (!opts?.silent) pushNotice('error', `加载批次列表失败：${msg}`);
    } finally {
      setBatchLoadingSessions(false);
    }
  }, [batchSessionId, pushNotice]);

  const loadBatchItems = useCallback(
    async (batchId: string, opts?: { silent?: boolean }) => {
      const id = String(batchId || '').trim();
      if (!id) return;
      if (!opts?.silent) setBatchLoadingItems(true);
      try {
        const pageSize = 200;
        let offset = 0;
        let total = 0;
        const all: EvalRun[] = [];
        do {
          const res = await evalApi.listRuns({
            batch_session_id: id,
            batch_mode: true,
            mine_only: true,
            limit: pageSize,
            offset,
          });
          const items = Array.isArray(res.items) ? res.items : [];
          total = Number(res.total || 0);
          all.push(...items);
          offset += items.length;
          if (items.length === 0) break;
          if (offset >= 6000) break;
        } while (offset < total);
        const mapped = all
          .map((run) => mapRunToBatchItem(run))
          .filter((item): item is LoraBatchItem => Boolean(item))
          .sort((a, b) => {
            const source = String(a.sourceKey || '').localeCompare(String(b.sourceKey || ''));
            if (source !== 0) return source;
            return (a.repeatIndex || 1) - (b.repeatIndex || 1);
          });
        setBatchItems((prev) => {
          const others = prev.filter((item) => item.batchId !== id);
          const localUnsubmitted = prev.filter((item) => item.batchId === id && !item.runId);
          return [...mapped, ...localUnsubmitted, ...others];
        });
        setBatchItemsLoadError('');
      } catch (err) {
        const msg = String((err as any)?.message || err || '');
        setBatchItemsLoadError(msg || '加载失败');
        if (!opts?.silent) pushNotice('error', `加载批次明细失败：${msg}`);
      } finally {
        if (!opts?.silent) setBatchLoadingItems(false);
      }
    },
    [mapRunToBatchItem, pushNotice],
  );

  const refreshBatchRunStatus = useCallback(async () => {
    const source = batchItemsRef.current || [];
    const candidates = source.filter(
      (item) =>
        item.status === 'submitted' &&
        !!item.runId &&
        (!item.runStatus || item.runStatus === 'queued' || item.runStatus === 'running' || item.runStatus === 'unknown'),
    );
    if (candidates.length === 0) return;

    const pageSize = 24;
    const start = batchPollCursorRef.current % candidates.length;
    const page: LoraBatchItem[] = [];
    for (let i = 0; i < Math.min(pageSize, candidates.length); i += 1) {
      page.push(candidates[(start + i) % candidates.length]);
    }
    batchPollCursorRef.current += page.length;

    const chunks: Array<LoraBatchItem[]> = [];
    const queryConcurrency = 6;
    for (let i = 0; i < page.length; i += queryConcurrency) {
      chunks.push(page.slice(i, i + queryConcurrency));
    }

    const patchMap = new Map<string, Partial<LoraBatchItem>>();
    for (const chunk of chunks) {
      const results = await Promise.all(
        chunk.map(async (item) => {
          try {
            const run = await evalApi.getRun(String(item.runId || ''));
            const statusRaw = String(run.status || '').toLowerCase();
            let runStatus: LoraBatchRunStatus = 'unknown';
            if (statusRaw === 'queued') runStatus = 'queued';
            else if (statusRaw === 'running') runStatus = 'running';
            else if (statusRaw === 'failed') runStatus = 'failed';
            else if (statusRaw === 'succeeded' || statusRaw === 'success') runStatus = 'succeeded';
            const outputUrls = Array.isArray(run.result_image_urls_json)
              ? run.result_image_urls_json.map((u) => String(u || '').trim()).filter((u) => Boolean(u))
              : [];
            return {
              key: item.key,
              patch: {
                runStatus,
                outputCount: outputUrls.length,
                outputUrls,
                runPrompt: String((run.parameters_json as any)?.prompt || ''),
                runError: runStatus === 'failed' ? String(run.error_message || '') : undefined,
              } satisfies Partial<LoraBatchItem>,
            };
          } catch (err) {
            return {
              key: item.key,
              patch: {
                runStatus: 'unknown',
                runError: String((err as any)?.message || err || '状态查询失败'),
              } satisfies Partial<LoraBatchItem>,
            };
          }
        }),
      );
      for (const item of results) {
        patchMap.set(item.key, item.patch);
      }
    }

    if (patchMap.size === 0) return;
    setBatchItems((prev) =>
      prev.map((item) => {
        const patch = patchMap.get(item.key);
        return patch ? { ...item, ...patch } : item;
      }),
    );
  }, []);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    void loadBatchSessions();
    const timer = window.setInterval(() => {
      void loadBatchSessions({ silent: true });
    }, 6000);
    return () => window.clearInterval(timer);
  }, [activeView, loadBatchSessions]);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    if (!selectedBatchId) return;
    void loadBatchItems(selectedBatchId);
  }, [activeView, selectedBatchId, loadBatchItems]);

  useEffect(() => {
    if (activeView !== 'loraBatch') return;
    const timer = window.setInterval(() => {
      void refreshBatchRunStatus();
      if (selectedBatchId) {
        void loadBatchItems(selectedBatchId, { silent: true });
      }
    }, 3000);
    void refreshBatchRunStatus();
    if (selectedBatchId) {
      void loadBatchItems(selectedBatchId, { silent: true });
    }
    return () => window.clearInterval(timer);
  }, [activeView, refreshBatchRunStatus, selectedBatchId, loadBatchItems]);

  useEffect(() => {
    if (activeView !== 'tool' || !selectedTool) return;
    void loadRunsForTool(selectedTool.id);
    const timer = window.setInterval(() => {
      const hasPending = toolRuns.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasPending) void loadRunsForTool(selectedTool.id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeView, selectedTool?.id, filterStatus, filterUnrated, toolRuns]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeView !== 'tasks') return;
    void loadTasks();
    const timer = window.setInterval(() => void loadTasks(), 2000);
    return () => window.clearInterval(timer);
  }, [activeView]);

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

  const openTool = (wf: EvalWorkflowVersion) => {
    setSelectedTool(wf);
    setFormUrl('');
    // Prevent showing previous tool's results while the new tool's history is loading.
    setToolRuns([]);
    setFilterStatus('all');
    setFilterRating('all');
    setFilterUnrated(false);
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
      const v = String((formParams as any)?.[f.name] ?? '').trim();
      if (!v) missing.push((f as any).label || f.name);
    }
    if (missing.length > 0) {
      pushNotice('error', `请补齐必填参数：${missing.join('、')}`);
      return;
    }

    setIsRunning(true);
    try {
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

      const parameters: Record<string, unknown> = {};
      if (requiresImage && url) {
        parameters.url = url;
      }
      if (isAiEditor) {
        const prompt = buildEditorPrompt({
          rawPrompt: editorPrompt,
          marks: editorMarks,
          refUrls: editorRefs,
          imageSize: { width: editorImageMeta.naturalW, height: editorImageMeta.naturalH },
        });
        parameters.prompt = prompt;
        if (editorRefs.length > 0) {
          parameters.image_urls = editorRefs.join(',');
        }
      }
      for (const [k, v] of Object.entries(formParams)) {
        if (isAiEditor && (k === 'prompt' || k === 'image_urls')) continue;
        if (v === '') continue;
        if (isAiEditor && k === 'aspect_ratio' && String(v).trim() === 'auto') continue;
        if (isAiEditor && k === 'resolution' && String(v).trim() === '1K') continue;
        if (typeof v === 'string') {
          parameters[k] = normalizeNumericParam(k, v);
        } else {
          parameters[k] = v;
        }
      }
      await evalApi.createRun({
        workflow_version_id: selectedTool.id,
        input_oss_urls_json: requiresImage && url ? [url] : [],
        parameters_json: parameters,
      });
      await loadRunsForTool(selectedTool.id);
      await refreshMetrics();
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

    const currentBatchId = `batch_${Date.now()}`;
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

    const fileSizeMap = new Map<string, { width: number; height: number } | null>();
    await Promise.all(
      fileOrder.map(async ({ file, sourceKey }) => {
        const size = await loadImageSizeFromFile(file);
        fileSizeMap.set(sourceKey, size);
      }),
    );

    const buildParameters = (
      url: string,
      imageSize?: { width: number; height: number } | null,
      planMeta?: { fileName: string; sourceKey: string; repeatIndex: number },
    ): Record<string, unknown> => {
      const parameters: Record<string, unknown> = {
        [selectedBatchWorkflowMeta.urlFieldName]: url,
        __eval_batch_mode: '1',
        __batch_session_id: currentBatchId,
      };
      if (planMeta) {
        parameters.__batch_file_name = String(planMeta.fileName || '');
        parameters.__batch_source_key = String(planMeta.sourceKey || '');
        parameters.__batch_repeat_index = String(planMeta.repeatIndex || 1);
      }
      if (selectedBatchWorkflowMeta.urlFieldName !== 'url') {
        // Keep lower-case url for backward compatibility in existing workflow handlers.
        parameters.url = url;
      }
      for (const [k, v] of Object.entries(effectiveParams)) {
        if (k === 'url' || k === 'Url') continue;
        if (isBatchSizeFieldName(k)) continue;
        const raw = String(v ?? '').trim();
        if (!raw) continue;
        parameters[k] = normalizeNumericParam(k, raw);
      }

      const chooseAutoAspect = (): string | undefined => {
        if (!batchAspectField) return undefined;
        if (batchAspectOptions.some((o) => o.value === '')) return '';
        const autoOpt = batchAspectOptions.find((o) => o.value.toLowerCase() === 'auto');
        if (autoOpt) return autoOpt.value;
        if (imageSize && batchAspectOptions.length > 0) {
          const target = imageSize.width / imageSize.height;
          let best: { value: string; score: number } | null = null;
          for (const opt of batchAspectOptions) {
            const v = String(opt.value || '').trim();
            const m = v.match(/^(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)$/);
            if (!m) continue;
            const a = Number(m[1]);
            const b = Number(m[2]);
            if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) continue;
            const ratio = a / b;
            const score = Math.abs(ratio - target);
            if (!best || score < best.score) best = { value: v, score };
          }
          if (best) return best.value;
        }
        return undefined;
      };

      if (batchSizeMode === 'preset_1k') {
        if (batchResolutionField) {
          const oneK = batchResolutionOptions.find((o) => String(o.value).toLowerCase() === '1k')?.value;
          parameters[batchResolutionField.name] = oneK || '1K';
          if (batchAspectField) {
            const aspectValue = chooseAutoAspect();
            if (aspectValue != null) parameters[batchAspectField.name] = aspectValue;
          }
        } else if (batchWidthField && batchHeightField && imageSize) {
          const fit = fitLongestEdge(imageSize.width, imageSize.height, 1024);
          if (fit) {
            parameters[batchWidthField.name] = String(fit.width);
            parameters[batchHeightField.name] = String(fit.height);
          }
        } else if (batchWidthField && batchHeightField) {
          parameters[batchWidthField.name] = '1024';
          parameters[batchHeightField.name] = '1024';
        }
      } else if (batchSizeMode === 'custom') {
        if (batchAspectField && batchAspectRatio !== '') {
          parameters[batchAspectField.name] = batchAspectRatio.trim();
        }
        if (batchResolutionField && batchResolution.trim()) {
          parameters[batchResolutionField.name] = batchResolution.trim();
        }
        if (!batchResolutionField && batchWidthField && batchCustomWidth.trim()) {
          parameters[batchWidthField.name] = normalizeNumericParam(batchWidthField.name, batchCustomWidth.trim());
        }
        if (!batchResolutionField && batchHeightField && batchCustomHeight.trim()) {
          parameters[batchHeightField.name] = normalizeNumericParam(batchHeightField.name, batchCustomHeight.trim());
        }
      }
      return parameters;
    };

    batchStopRef.current = false;
    setBatchSubmitting(true);
    let cursor = 0;
    const nextFile = (): { file: File; sourceKey: string } | null => {
      if (cursor >= fileOrder.length) return null;
      const entry = fileOrder[cursor];
      cursor += 1;
      return entry;
    };

    const runWorker = async () => {
      while (!batchStopRef.current) {
        const fileEntry = nextFile();
        if (!fileEntry) break;
        const file = fileEntry.file;
        const fileKey = fileEntry.sourceKey;
        const imageSize = fileSizeMap.get(fileKey) || null;
        const filePlans = (planByFile.get(fileKey) || []).sort((a, b) => a.repeatIndex - b.repeatIndex);
        const keys = filePlans.map((item) => item.key);
        updateItems(keys, { status: 'uploading', error: undefined });
        let inputUrl = '';
        try {
          const upload = await evalApi.uploadImage(file);
          inputUrl = String(upload.url || '');
          if (!inputUrl) throw new Error('上传成功但未返回 URL');
        } catch (err) {
          updateItems(keys, {
            status: 'failed',
            error: String((err as any)?.message || err || '上传失败'),
          });
          continue;
        }

        for (const plan of filePlans) {
          if (batchStopRef.current) break;
          updateItems([plan.key], { status: 'submitting', inputUrl, error: undefined });
          try {
            const run = await evalApi.createRun({
              workflow_version_id: selectedBatchWorkflow.id,
              input_oss_urls_json: [inputUrl],
              parameters_json: buildParameters(inputUrl, imageSize, {
                fileName: plan.fileName,
                sourceKey: fileKey,
                repeatIndex: plan.repeatIndex,
              }),
            });
            updateItems([plan.key], {
              status: 'submitted',
              runId: run.id,
              inputUrl,
              runStatus: 'queued',
              runError: undefined,
            });
          } catch (err) {
            updateItems([plan.key], {
              status: 'failed',
              error: String((err as any)?.message || err || '提交失败'),
              inputUrl,
              runStatus: undefined,
            });
          }
        }
      }
    };

    try {
      await Promise.all(Array.from({ length: workerCount }, () => runWorker()));
      if (batchStopRef.current) {
        setBatchItems((prev) =>
          prev.map((item) =>
            item.status === 'pending'
              ? { ...item, status: 'failed', error: '已手动停止（未提交）' }
              : item,
          ),
        );
        pushNotice('info', '批量提交已停止');
      } else {
        pushNotice('success', '批量提交完成，系统会自动刷新“已完成”进度');
      }
      await loadBatchSessions();
      await loadBatchItems(currentBatchId, { silent: true });
    } catch (err) {
      pushNotice('error', String((err as any)?.message || err || '批量提交失败'));
    } finally {
      setBatchSubmitting(false);
    }
  };

  const updateBatchReview = useCallback((key: string, patch: Partial<LoraBatchReview>) => {
    setBatchReviewMap((prev) => {
      const current: LoraBatchReview = prev[key] || { verdict: 'pending' };
      return {
        ...prev,
        [key]: {
          ...current,
          ...patch,
        },
      };
    });
  }, []);

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
    (onlyUnsatisfied: boolean) => {
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

      for (const item of visibleBatchItems) {
        const runId = String(item.runId || '');
        const outputs = Array.isArray(item.outputUrls) ? item.outputUrls : [];
        if (outputs.length === 0) {
          const verdict = 'pending';
          if (onlyUnsatisfied) continue;
          pushRow([
            String(item.batchId || selectedBatchId || ''),
            String(selectedBatchWorkflow?.workflow_id || ''),
            String(selectedBatchWorkflow?.name || ''),
            String(batchLoraValue || ''),
            item.fileName,
            String(item.inputUrl || ''),
            String(item.repeatIndex),
            runId,
            String(item.runStatus || ''),
            '',
            '',
            String(item.runPrompt || ''),
            formatLoraReviewVerdictLabel(verdict),
            '',
            '',
            String(item.error || item.runError || ''),
          ]);
          continue;
        }
        outputs.forEach((outputUrl, idx) => {
          const reviewKey = buildBatchReviewKey(runId, idx + 1);
          const review = batchReviewMap[reviewKey] || { verdict: 'pending' as LoraBatchReviewVerdict };
          if (onlyUnsatisfied && review.verdict !== 'unsatisfied') return;
          pushRow([
            String(item.batchId || selectedBatchId || ''),
            String(selectedBatchWorkflow?.workflow_id || ''),
            String(selectedBatchWorkflow?.name || ''),
            String(batchLoraValue || ''),
            item.fileName,
            String(item.inputUrl || ''),
            String(item.repeatIndex),
            runId,
            String(item.runStatus || ''),
            String(idx + 1),
            String(outputUrl || ''),
            String(item.runPrompt || ''),
            formatLoraReviewVerdictLabel(review.verdict),
            String(review.reason || ''),
            String(review.note || ''),
            String(item.error || item.runError || ''),
          ]);
        });
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
    },
    [
      visibleBatchItems,
      selectedBatchWorkflow,
      batchLoraValue,
      selectedBatchId,
      buildBatchReviewKey,
      batchReviewMap,
      pushNotice,
    ],
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
    if (filterRating !== 'all') {
      const target = Number(filterRating);
      out = out.filter((r) => r.latest_annotation?.rating === target);
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
  }, [toolRuns, filterRating, search]);

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
        const list = await evalApi.adminListWorkflowVersions(token);
        setAdminWorkflows(list);
        pushNotice('success', '已加载维护列表');
      } catch (err) {
        console.error(err);
        pushNotice('error', String((err as any)?.message || err));
      }
    },
    [adminToken, pushNotice],
  );

  const openAdmin = useCallback(async () => {
    void promptAdminToken();
  }, [promptAdminToken]);

  const headerNavValue = activeView === 'tool' ? 'home' : activeView;

  const header = (
    <Layout.Header
      style={{
        borderBottom: '1px solid var(--td-component-border)',
        background: 'var(--td-bg-color-container)',
        padding: '0 24px',
      }}
    >
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', height: '100%' }}>
        <Space direction="vertical" size={2}>
          <Typography.Text strong>PODI · 能力评测</Typography.Text>
          <Typography.Text theme="secondary">工具箱式评测 · 免登录 · 评分沉淀</Typography.Text>
        </Space>
        <Space align="center">
          <Tabs
            value={headerNavValue}
            onChange={(v) => {
              const next = String(v) as any;
              if (next === 'admin') {
                void openAdmin();
                return;
              }
              setActiveView(next);
              setSelectedTool(null);
            }}
          >
            <Tabs.TabPanel value="home" label="工具箱" />
            <Tabs.TabPanel value="loraBatch" label="LoRA批测" />
            <Tabs.TabPanel value="tasks" label="任务管理" />
            <Tabs.TabPanel value="docs" label="文档" />
            <Tabs.TabPanel value="admin" label="维护" />
          </Tabs>
          <Button variant="outline" onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}>
            {theme === 'dark' ? '深色' : '浅色'}
          </Button>
          <Typography.Text theme="secondary">
            raterId:{' '}
            <span style={{ fontFamily: 'monospace' }}>{raterId || '...'}</span>
          </Typography.Text>
        </Space>
      </Space>
    </Layout.Header>
  );

  const shell = (content: ReactNode) => (
    <ConfigProvider globalConfig={zhCN}>
      <Layout style={{ height: '100vh' }}>
        {header}
        <Layout>
          <Layout.Aside
            style={{
              width: 260,
              borderRight: '1px solid var(--td-component-border)',
              background: 'var(--td-bg-color-container)',
              padding: 16,
              overflow: 'auto',
            }}
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Typography.Text theme="secondary">导航</Typography.Text>
                <Typography.Title level="h5" style={{ margin: '6px 0 0' }}>
                  测试大类
                </Typography.Title>
                <Typography.Text theme="secondary">选择分类后，右侧展示对应能力卡片。</Typography.Text>
              </div>
              <Menu
                value={activeCategory}
                theme={theme === 'dark' ? 'dark' : 'light'}
                onChange={(value: string | number) => {
                  const next = String(value);
                  setActiveCategory(next);
                  // Categories are the primary navigation for the toolbox.
                  setSelectedTool(null);
                  setActiveView('home');
                }}
              >
                {CATEGORY_ORDER.map((cat) => (
                  <Menu.MenuItem key={cat} value={cat}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <span>{cat}</span>
                      <Typography.Text theme="secondary">{(grouped[cat] || []).length}</Typography.Text>
                    </Space>
                  </Menu.MenuItem>
                  ))}
                </Menu>
            </Space>
          </Layout.Aside>
          <Layout.Content style={{ padding: 24, background: 'var(--td-bg-color-page)', overflow: 'auto' }}>
            <div style={{ maxWidth: 1400, margin: '0 auto' }}>{content}</div>
          </Layout.Content>
        </Layout>
      </Layout>
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
                try {
                  const list = await evalApi.adminListWorkflowVersions(adminToken);
                  setAdminWorkflows(list);
                  pushNotice('success', '已刷新列表');
                } catch (err) {
                  console.error(err);
                  pushNotice('error', String((err as any)?.message || err));
                }
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
          {adminWorkflows.length === 0 ? <Typography.Text theme="secondary">暂无数据。</Typography.Text> : null}
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
        ) : docsView === 'structured' && groupedDocs.length > 0 ? (
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
          </Space>
        </Card>

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
                      <Typography.Text theme="secondary">查看批次</Typography.Text>
                      <Button
                        size="small"
                        variant="outline"
                        loading={batchLoadingSessions}
                        onClick={() => void loadBatchSessions()}
                      >
                        刷新批次
                      </Button>
                    </Space>
                    <Select
                      value={selectedBatchId || ''}
                      options={batchSessionOptions}
                      placeholder={batchSessionOptions.length > 0 ? '请选择批次' : '暂无批次'}
                      onChange={(v) => setBatchSessionId(String(v))}
                      disabled={batchSessionOptions.length === 0}
                    />
                    <Typography.Text theme="secondary">
                      {batchLoadingSessions ? '正在刷新批次列表…' : `历史批次 ${batchSessions.length} 个`}
                    </Typography.Text>
                    {batchSessionLoadError ? (
                      <Typography.Text theme="error">批次列表加载失败：{batchSessionLoadError}</Typography.Text>
                    ) : null}
                  </Space>
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
                    <Typography.Text strong>{batchSummary.total}</Typography.Text>
                  </Space>
                </Col>
                <Col xs={6} md={3}>
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">已提交执行</Typography.Text>
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
                <Col xs={12}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text theme="secondary">
                      当前测试任务：{selectedBatchId || '未提交'}；提交中：{batchSummary.active}；队列/生成中：{batchSummary.queuedOrRunning}；失败：{batchSummary.failed}。
                    </Typography.Text>
                    <Space>
                      <Button
                        size="small"
                        variant="outline"
                        loading={batchLoadingItems}
                        disabled={!selectedBatchId}
                        onClick={() => selectedBatchId && void loadBatchItems(selectedBatchId)}
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
              </Row>
            </Card>

            <Card
              bordered
              title={
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>本批次明细</Typography.Text>
                  <Space>
                    {batchItemsLoadError ? <Typography.Text theme="error">明细加载失败：{batchItemsLoadError}</Typography.Text> : null}
                    <Typography.Text theme="secondary">本批次共 {visibleBatchItems.length} 条执行</Typography.Text>
                  </Space>
                </Space>
              }
            >
                <Table
                  size="small"
                  rowKey="key"
                  data={visibleBatchItems}
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
                      const statusTheme = row.status === 'failed' || runStatus === 'failed' ? 'danger' : runStatus === 'succeeded' ? 'success' : 'warning';
                      const text =
                        row.status === 'submitted'
                          ? formatLoraBatchRunStatusLabel(row.runStatus, row.outputCount)
                          : formatLoraBatchStatusLabel(row.status);
                      return (
                        <Tag variant="light" theme={statusTheme}>
                          {text}
                        </Tag>
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
          </Col>
        </Row>

        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text strong>原图-结果对照与标注</Typography.Text>
              <Space>
                <Button
                  variant="outline"
                  disabled={visibleBatchItems.length === 0}
                  onClick={() => exportBatchComparisonCsv(false)}
                >
                  导出全部对照集
                </Button>
                <Button
                  variant="outline"
                  disabled={visibleBatchItems.length === 0}
                  onClick={() => exportBatchComparisonCsv(true)}
                >
                  导出不满意样本
                </Button>
              </Space>
            </Space>
          }
        >
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Typography.Text theme="secondary">
              目的：把“本批次中的原图 + 多次结果 + 满意度标注”沉淀成可分析数据，后续用于定位 LoRA 素材覆盖缺口。
            </Typography.Text>
            {batchComparisonGroups.length > 0 ? (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {batchComparisonGroups.map((group) => (
                  <div key={group.key} style={{ border: '1px solid var(--td-component-border)', borderRadius: 8, padding: 10 }}>
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Typography.Text strong>{group.fileName}</Typography.Text>
                      <Typography.Text theme="secondary">
                        完成 {group.completedRuns}/{group.totalRuns}；结果 {group.outputCount} 张；等待 {group.waitingRuns}；失败 {group.failedRuns}
                      </Typography.Text>
                      <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 6 }}>
                        <div style={{ minWidth: 260 }}>
                          <Typography.Text theme="secondary">原图</Typography.Text>
                          <img
                            src={group.inputUrl}
                            alt="原图"
                            style={{ width: 260, height: 260, objectFit: 'contain', border: '1px solid var(--td-component-border)' }}
                            onClick={() => setLightbox({ url: group.inputUrl, title: '原图' })}
                          />
                        </div>
                        {group.outputs.map((output) => {
                          const review = batchReviewMap[output.reviewKey] || { verdict: 'pending' as LoraBatchReviewVerdict };
                          return (
                            <div key={output.reviewKey} style={{ minWidth: 280, maxWidth: 320 }}>
                              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                <Typography.Text theme="secondary">
                                  结果图 {output.outputIndex}
                                  {output.runId ? ` · 执行ID ${output.runId}` : ''}
                                </Typography.Text>
                                <Space>
                                  <Button
                                    size="small"
                                    variant={review.verdict === 'satisfied' ? 'base' : 'outline'}
                                    theme="success"
                                    onClick={() => updateBatchReview(output.reviewKey, { verdict: 'satisfied' })}
                                  >
                                    满意
                                  </Button>
                                  <Button
                                    size="small"
                                    variant={review.verdict === 'unsatisfied' ? 'base' : 'outline'}
                                    theme="danger"
                                    onClick={() => updateBatchReview(output.reviewKey, { verdict: 'unsatisfied' })}
                                  >
                                    不满意
                                  </Button>
                                </Space>
                                <img
                                  src={output.url}
                                  alt={`结果图${output.outputIndex}`}
                                  style={{ width: 280, height: 260, objectFit: 'contain', border: '1px solid var(--td-component-border)' }}
                                  onClick={() => setLightbox({ url: output.url, title: `结果图 ${output.outputIndex}` })}
                                />
                                <Select
                                  value={review.reason || ''}
                                  options={batchReviewReasonOptions}
                                  placeholder="问题原因（可选）"
                                  onChange={(v) => updateBatchReview(output.reviewKey, { reason: String(v) })}
                                  clearable
                                />
                                <Input
                                  value={review.note || ''}
                                  placeholder="备注（可选）"
                                  onChange={(v) => updateBatchReview(output.reviewKey, { note: String(v) })}
                                />
                              </Space>
                            </div>
                          );
                        })}
                      </div>
                      {group.outputCount === 0 ? (
                        <Alert theme="warning" message={group.lastError || '当前还没有结果图，请继续等待或检查失败原因。'} />
                      ) : null}
                    </Space>
                  </div>
                ))}
              </Space>
            ) : (
              <Typography.Text theme="secondary">暂无可对照样本。请先提交批测并等待任务生成结果。</Typography.Text>
            )}
          </Space>
        </Card>
      </Space>,
    );
  }

  if (activeView === 'tool' && selectedTool) {
    const metric = metrics[selectedTool.id];
    const doc = isAiEditor
      ? buildAiEditorDoc(selectedTool, formUrl.trim(), editorPromptPreview, editorRefs)
      : buildCozeDoc(selectedTool, formUrl.trim());
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

        <Card bordered>
          <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={4} style={{ minWidth: 0 }}>
              <Typography.Title level="h4" style={{ margin: 0 }}>
                {selectedTool.name}
              </Typography.Title>
              <Typography.Text theme="secondary">{selectedTool.notes || '—'}</Typography.Text>
              <Space breakLine>
                <Tag variant="light">{normalizeCategory(selectedTool.category)}</Tag>
                <Tag variant="light">{selectedTool.version}</Tag>
                {metric?.avgRating ? (
                  <Tag theme="warning" variant="light">
                    综合评分：{metric.avgRating.toFixed(2)} / 5（{metric.ratingCount}票）
                  </Tag>
                ) : (
                  <Tag variant="light">综合评分：暂无</Tag>
                )}
              </Space>
            </Space>
          </Space>
        </Card>

        <Row gutter={[12, 12]}>
          {/* TDesign Grid uses a 12-column system; keep spans within 12 to avoid wrapping/empty gaps. */}
          <Col xs={12} xl={5}>
            <Card bordered title="测试参数">
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

                  <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                    <Button
                      theme="primary"
                      loading={isRunning}
                      disabled={isRunning || !formUrl.trim()}
                      onClick={() => void runTool()}
                    >
                      开始生成
                    </Button>
                  </Space>

                  <Card
                    bordered
                    title={
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>业务接入文档（Coze OpenAPI）</Typography.Text>
                        <Button
                          size="small"
                          variant="outline"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(doc);
                              pushNotice('success', '已复制到剪贴板');
                            } catch {
                              pushNotice('error', '复制失败（浏览器不支持或权限不足）');
                            }
                          }}
                        >
                          复制
                        </Button>
                      </Space>
                    }
                  >
                    <pre
                      style={{
                        maxHeight: 260,
                        overflow: 'auto',
                        border: '1px solid var(--td-border-level-1-color)',
                        background: 'var(--td-bg-color-secondarycontainer)',
                        borderRadius: 8,
                        padding: 12,
                        fontFamily: 'monospace',
                        fontSize: 12,
                        whiteSpace: 'pre',
                      }}
                    >
                      {doc}
                    </pre>
                  </Card>
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
                      .map((f) => (
                        <ParamField
                          key={f.name}
                          field={f}
                          value={formParams[f.name] ?? ''}
                          onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: v }))}
                        />
                      ))}
                  </Space>

                  <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                    <Button
                      theme="primary"
                      loading={isRunning}
                      disabled={isRunning || (requiresImage ? !formUrl.trim() : false)}
                      onClick={() => void runTool()}
                    >
                      开始生成
                    </Button>
                  </Space>

                  <Card
                    bordered
                    title={
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>业务接入文档（Coze OpenAPI）</Typography.Text>
                        <Button
                          size="small"
                          variant="outline"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(doc);
                              pushNotice('success', '已复制到剪贴板');
                            } catch {
                              pushNotice('error', '复制失败（浏览器不支持或权限不足）');
                            }
                          }}
                        >
                          复制
                        </Button>
                      </Space>
                    }
                  >
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
                        whiteSpace: 'pre',
                      }}
                    >
                      {doc}
                    </pre>
                  </Card>
                </Space>
              )}
            </Card>
          </Col>

          <Col xs={12} xl={7}>
            <Card bordered title="生成结果">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Typography.Text theme="secondary">点击图片可放大预览；下方历史可筛选/打标。</Typography.Text>
                {(() => {
                  const latest = toolRuns[0] || null;
                  const status = String(latest?.status || '');
                  const statusTheme = status === 'failed' ? 'danger' : status === 'succeeded' ? 'success' : 'warning';
                  const rawCount = Number((latest?.parameters_json as any)?.count);
                  const expectedCount =
                    Number.isFinite(rawCount) && rawCount > 1 ? Math.min(Math.max(rawCount, 2), 12) : latest ? 1 : 0;
                  const imgs = latest ? filterImageUrls(latest.result_image_urls_json) : [];
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
                                <Tag theme={statusTheme as any} variant="light">
                                  {status || '—'}
                                </Tag>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">run</Typography.Text>
                                <Typography.Text style={{ fontFamily: 'monospace' }} ellipsis>
                                  {latest.id}
                                </Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">预期出图</Typography.Text>
                                <Typography.Text>{expectedCount || '—'}</Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">已完成</Typography.Text>
                                <Typography.Text>{imgs.length}</Typography.Text>
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
                                      debug_url
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
                                <Alert theme="error" message={latest.error_message} />
                              </Col>
                            ) : null}
                          </Row>
                        )}
                      </Card>

                      <div className="grid gap-3 lg:grid-cols-3">
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
                          <Alert theme="error" message={`生成失败（run: ${latest.id}）：${latest.error_message || '—'}`} />
                        ) : imgs.length === 0 ? (
                          <Card bordered title="输出">
                            {(() => {
                              const jsonPreview = formatJsonPreview((latest as any).result_output_json, 2400);
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
                        ) : (
                          imgs.map((img, idx) => (
                            <ImageTile
                              key={`latest-${idx}`}
                              url={img}
                              title={`最新结果 #${idx + 1}`}
                              onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
                            />
                          ))
                        )}
                      </div>
                    </Space>
                  );
                })()}
              </Space>
            </Card>
          </Col>
        </Row>

        <Card
          bordered
          title={
            <div className="podi-card-titlebar">
              <div className="podi-card-titlebar__left">
                <Typography.Text strong>历史记录（打标区）</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">每条记录包含原图 + 结果图；支持筛选与备注。</Typography.Text>
                </div>
              </div>
              <div className="podi-card-titlebar__right">
                <Select
                  value={filterStatus}
                  onChange={(v) => setFilterStatus(String(v))}
                  style={{ width: 140 }}
                  options={[
                    { label: '全部状态', value: 'all' },
                    { label: 'queued', value: 'queued' },
                    { label: 'running', value: 'running' },
                    { label: 'succeeded', value: 'succeeded' },
                    { label: 'failed', value: 'failed' },
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
              </div>
            </div>
          }
        >
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
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
  return shell(
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level="h4" style={{ margin: 0 }}>
          {normalizeCategory(activeCategory)}
        </Typography.Title>
        <Typography.Text theme="secondary">
          点击卡片进入该功能的评测页面（左侧测试，右侧出图，底部打标）。
        </Typography.Text>
      </div>
      {toolList.length === 0 ? <Alert theme="info" message="该分类暂无功能。" /> : null}
      <div className="podi-tool-grid">
        {toolList.map((wf) => (
          <ToolCard key={wf.id} wf={wf} active={false} metric={metrics[wf.id]} onClick={() => openTool(wf)} />
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
  const outputs = filterImageUrls(run.result_image_urls_json);
  const [rating, setRating] = useState<number>(run.latest_annotation?.rating || 0);
  const [savedComment, setSavedComment] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [commentDraft, setCommentDraft] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [savingRating, setSavingRating] = useState(false);
  const [savingComment, setSavingComment] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string>('');
  const [rowError, setRowError] = useState<string>('');

  const commentDirty = commentDraft !== savedComment;
  const jsonPreview = formatJsonPreview((run as any).result_output_json, 1200);
  const displayParams = filterDisplayParams(run.parameters_json as Record<string, unknown> | null);
  const paramsPreview = formatJsonPreview(displayParams, 1000);
  const outputIp = extractOutputField((run as any).result_output_json, 'ip');

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
              run: {run.id}
            </Typography.Text>
            <div className="podi-history-row-head__meta-line">
              <Tag size="small" variant="light">
                {run.status}
              </Tag>
              <Typography.Text theme="secondary">耗时：{formatDuration(run.duration_ms)}</Typography.Text>
              <Typography.Text theme="secondary">{fmtTime(run.created_at)}</Typography.Text>
              {run.podi_task_id ? (
                <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                  task: {run.podi_task_id}
                </Typography.Text>
              ) : null}
              {outputIp ? (
                <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                  ip: {outputIp}
                </Typography.Text>
              ) : null}
              {run.coze_debug_url ? (
                <Button
                  size="small"
                  variant="text"
                  onClick={() => window.open(run.coze_debug_url || '', '_blank', 'noreferrer')}
                >
                  debug_url
                </Button>
              ) : null}
            </div>
            {run.error_message ? <Alert theme="error" message={run.error_message} /> : null}
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
  const [category, setCategory] = useState(normalizeCategory(wf.category));
  const [status, setStatus] = useState(wf.status);
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState<string>('');

  const dirty = name !== wf.name || notes !== (wf.notes || '') || category !== normalizeCategory(wf.category) || status !== wf.status;
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
