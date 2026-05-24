import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import { Alert, Button, Input, Select, Space, Textarea, Typography } from 'tdesign-react';
import { ImageEditIcon } from 'tdesign-icons-react';
import './image-edit.css';
import {
  DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS,
  formatEditorToolLabel,
  formatEditorMarkMention,
  formatEditorReferenceMention,
  getImageEditQuickPrompts,
  IMAGE_EDIT_OUTPAINT_ANCHOR_OPTIONS,
  IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS,
  IMAGE_EDIT_QUALITY_OPTIONS,
  IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS,
  IMAGE_EDIT_SIZE_OPTIONS,
  IMAGE_EDIT_SKILL_OPTIONS,
  normalizeImageEditQuality,
  summarizeEditorMarkGeometry,
} from './model';
import type { ImageEditMark, ImageEditOutpaintSettings, ImageEditPoint, ImageEditTool } from './model';

export type ImageEditWorkbenchValue = {
  imageUrl: string;
  editSkill: string;
  instruction: string;
  marks: ImageEditMark[];
  referenceUrls: string[];
  maskUrl: string;
  outpaint: ImageEditOutpaintSettings;
  size: string;
  quality: string;
  outputFormat: string;
};

export type ImageEditWorkbenchProps = {
  value: ImageEditWorkbenchValue;
  onChange: (next: ImageEditWorkbenchValue) => void;
  onUploadImage: (file: File) => Promise<string>;
  onPreviewImage?: (url: string, title?: string) => void;
  onSubmit: () => void;
  submitting?: boolean;
  uploading?: boolean;
  blockingReason?: string;
  advancedSlot?: ReactNode;
  onImageMetaChange?: (meta: { displayW: number; displayH: number; naturalW: number; naturalH: number }) => void;
};

const normalizeSkill = (value: string): string => {
  const raw = String(value || '').trim();
  if (IMAGE_EDIT_SKILL_OPTIONS.some((item) => item.value === raw)) return raw;
  return IMAGE_EDIT_SKILL_OPTIONS[0].value;
};

const getMarkColor = (tool: ImageEditTool): string => {
  if (tool === 'point') return '#f97316';
  if (tool === 'rect') return '#0ea5e9';
  if (tool === 'circle') return '#8b5cf6';
  return '#16a34a';
};

const clampOutpaintPixels = (value: unknown): number => {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(2048, Math.round(number)));
};

const roundUpTo16 = (value: number): number => Math.ceil(Math.max(1, value) / 16) * 16;

export function ImageEditWorkbench(props: ImageEditWorkbenchProps) {
  const {
    value,
    onChange,
    onUploadImage,
    onPreviewImage,
    onSubmit,
    submitting = false,
    uploading = false,
    blockingReason = '',
    advancedSlot,
    onImageMetaChange,
  } = props;

  const [activeTool, setActiveTool] = useState<ImageEditTool>('rect');
  const [drawing, setDrawing] = useState<ImageEditMark | null>(null);
  const [referenceDraft, setReferenceDraft] = useState('');
  const [mentionMenu, setMentionMenu] = useState<'mark' | 'reference' | null>(null);
  const [imageMeta, setImageMeta] = useState({ displayW: 0, displayH: 0, naturalW: 0, naturalH: 0 });
  const [workspaceZoom, setWorkspaceZoom] = useState(1);
  const [focusMode, setFocusMode] = useState(false);
  const [selectedReferenceIndex, setSelectedReferenceIndex] = useState(0);
  const [referenceZoom, setReferenceZoom] = useState(1);
  const [referenceFormOpen, setReferenceFormOpen] = useState(false);
  const [outputPanelOpen, setOutputPanelOpen] = useState(false);
  const idRef = useRef(1);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const referenceInputRef = useRef<HTMLInputElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const valueRef = useRef(value);
  const drawingRef = useRef<ImageEditMark | null>(null);
  valueRef.current = value;

  const emit = useCallback(
    (patch: Partial<ImageEditWorkbenchValue>) => {
      onChange({ ...valueRef.current, ...patch });
    },
    [onChange],
  );

  const selectedSkill = normalizeSkill(value.editSkill);
  const selectedSkillConfig = useMemo(
    () => IMAGE_EDIT_SKILL_OPTIONS.find((item) => item.value === selectedSkill) || IMAGE_EDIT_SKILL_OPTIONS[0],
    [selectedSkill],
  );
  const isCanvasOutpaint = selectedSkill === 'canvas_outpaint';
  const outpaint = useMemo(
    () => ({
      ...DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS,
      ...(value.outpaint || {}),
      expandLeft: clampOutpaintPixels((value.outpaint || {}).expandLeft ?? DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandLeft),
      expandRight: clampOutpaintPixels((value.outpaint || {}).expandRight ?? DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandRight),
      expandTop: clampOutpaintPixels((value.outpaint || {}).expandTop ?? DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandTop),
      expandBottom: clampOutpaintPixels((value.outpaint || {}).expandBottom ?? DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandBottom),
      anchor: String((value.outpaint || {}).anchor || DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.anchor),
      preserveOriginal: Boolean((value.outpaint || {}).preserveOriginal ?? DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.preserveOriginal),
    }),
    [value.outpaint],
  );
  const outpaintPreview = useMemo(() => {
    const sourceW = Math.round(imageMeta.naturalW || 0);
    const sourceH = Math.round(imageMeta.naturalH || 0);
    if (!sourceW || !sourceH) return null;
    const requestedW = sourceW + outpaint.expandLeft + outpaint.expandRight;
    const requestedH = sourceH + outpaint.expandTop + outpaint.expandBottom;
    const targetW = roundUpTo16(requestedW);
    const targetH = roundUpTo16(requestedH);
    const extraW = targetW - requestedW;
    const extraH = targetH - requestedH;
    const actualLeft = outpaint.expandLeft + (outpaint.expandLeft === outpaint.expandRight ? Math.floor(extraW / 2) : 0);
    const actualRight = outpaint.expandRight + (outpaint.expandLeft === outpaint.expandRight ? extraW - Math.floor(extraW / 2) : extraW);
    const actualTop = outpaint.expandTop + (outpaint.expandTop === outpaint.expandBottom ? Math.floor(extraH / 2) : 0);
    const actualBottom = outpaint.expandBottom + (outpaint.expandTop === outpaint.expandBottom ? extraH - Math.floor(extraH / 2) : extraH);
    const displaySourceW = imageMeta.displayW || sourceW;
    const displaySourceH = imageMeta.displayH || sourceH;
    const scale = Math.min(1, displaySourceW / sourceW, displaySourceH / sourceH);
    return {
      sourceW,
      sourceH,
      targetW,
      targetH,
      requestedW,
      requestedH,
      actualLeft,
      actualRight,
      actualTop,
      actualBottom,
      displayTargetW: Math.max(displaySourceW, Math.round(targetW * scale)),
      displayTargetH: Math.max(displaySourceH, Math.round(targetH * scale)),
      displaySourceW: Math.round(sourceW * scale),
      displaySourceH: Math.round(sourceH * scale),
      displayLeft: Math.round(actualLeft * scale),
      displayTop: Math.round(actualTop * scale),
    };
  }, [imageMeta.displayH, imageMeta.displayW, imageMeta.naturalH, imageMeta.naturalW, outpaint]);
  const quickPrompts = useMemo(() => getImageEditQuickPrompts(selectedSkill), [selectedSkill]);
  const referenceRequired = IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS.has(selectedSkill);
  const outputSize = String(value.size || 'auto');
  const outputQuality = normalizeImageEditQuality(value.quality);
  const outputFormat = String(value.outputFormat || 'png');
  const customSizeValue = IMAGE_EDIT_SIZE_OPTIONS.some((item) => item.value === outputSize) ? '' : outputSize;
  const markMentionItems = useMemo(
    () =>
      value.marks.map((mark, index) => ({
        id: mark.id,
        token: formatEditorMarkMention(mark, index),
        label: `标注 ${index + 1}`,
        meta: `${formatEditorToolLabel(mark.type)} · ${summarizeEditorMarkGeometry(mark)}`,
      })),
    [value.marks],
  );
  const referenceMentionItems = useMemo(
    () =>
      value.referenceUrls.map((url, index) => ({
        id: `${url}-${index}`,
        token: formatEditorReferenceMention(index),
        label: `参考图 ${index + 1}`,
        meta: url,
      })),
    [value.referenceUrls],
  );

  const syncImageMeta = useCallback(() => {
    const img = imageRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const zoom = Math.max(0.5, workspaceZoom || 1);
    const displayW = img.offsetWidth || rect.width / zoom;
    const displayH = img.offsetHeight || rect.height / zoom;
    if (!displayW || !displayH) return;
    const nextMeta = {
      displayW,
      displayH,
      naturalW: img.naturalWidth || displayW,
      naturalH: img.naturalHeight || displayH,
    };
    setImageMeta(nextMeta);
    onImageMetaChange?.(nextMeta);
  }, [onImageMetaChange, workspaceZoom]);

  useEffect(() => {
    if (!value.imageUrl.trim()) return;
    syncImageMeta();
    const handleResize = () => syncImageMeta();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [syncImageMeta, value.imageUrl]);

  useEffect(() => {
    if (selectedReferenceIndex >= value.referenceUrls.length) {
      setSelectedReferenceIndex(Math.max(0, value.referenceUrls.length - 1));
    }
  }, [selectedReferenceIndex, value.referenceUrls.length]);

  useEffect(() => {
    if (referenceRequired && value.referenceUrls.length === 0) {
      setReferenceFormOpen(true);
    }
  }, [referenceRequired, value.referenceUrls.length]);

  useEffect(() => {
    drawingRef.current = drawing;
  }, [drawing]);

  const getDisplayPoint = (evt: ReactMouseEvent): ImageEditPoint | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const rect = stage.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const zoom = Math.max(0.5, workspaceZoom || 1);
    const width = stage.offsetWidth || rect.width / zoom;
    const height = stage.offsetHeight || rect.height / zoom;
    return {
      x: Math.max(0, Math.min(width, (evt.clientX - rect.left) / zoom)),
      y: Math.max(0, Math.min(height, (evt.clientY - rect.top) / zoom)),
    };
  };

  const toOrigPoint = (point: ImageEditPoint): ImageEditPoint => {
    if (!imageMeta.displayW || !imageMeta.displayH) return point;
    return {
      x: (point.x * imageMeta.naturalW) / imageMeta.displayW,
      y: (point.y * imageMeta.naturalH) / imageMeta.displayH,
    };
  };

  const toDisplayPoint = (point: ImageEditPoint): ImageEditPoint => {
    if (!imageMeta.naturalW || !imageMeta.naturalH) return point;
    return {
      x: (point.x * imageMeta.displayW) / imageMeta.naturalW,
      y: (point.y * imageMeta.displayH) / imageMeta.naturalH,
    };
  };

  const createMark = (tool: ImageEditTool, points: ImageEditPoint[]): ImageEditMark => {
    const seq = idRef.current++;
    return {
      id: `image_edit_mark_${Date.now()}_${seq}`,
      name: `标注${seq}`,
      type: tool,
      points,
      created_at: Date.now(),
    };
  };

  const upsertMark = useCallback(
    (mark: ImageEditMark) => {
      const marks = valueRef.current.marks;
      const exists = marks.some((item) => item.id === mark.id);
      emit({ marks: exists ? marks.map((item) => (item.id === mark.id ? mark : item)) : [...marks, mark] });
    },
    [emit],
  );

  const removeMarkById = useCallback(
    (markId: string) => {
      emit({ marks: valueRef.current.marks.filter((item) => item.id !== markId) });
    },
    [emit],
  );

  const handlePointerDown = (evt: ReactMouseEvent) => {
    if (!value.imageUrl.trim()) return;
    if (isCanvasOutpaint) return;
    const displayPoint = getDisplayPoint(evt);
    if (!displayPoint) return;
    const point = toOrigPoint(displayPoint);
    if (activeTool === 'point') {
      emit({ marks: [...valueRef.current.marks, createMark('point', [point])] });
      return;
    }
    const mark = createMark(activeTool, [point]);
    drawingRef.current = mark;
    setDrawing(mark);
  };

  const handlePointerMove = (evt: ReactMouseEvent) => {
    if (!drawingRef.current) return;
    const displayPoint = getDisplayPoint(evt);
    if (!displayPoint) return;
    const point = toOrigPoint(displayPoint);
    setDrawing((prev) => {
      const current = prev || drawingRef.current;
      if (!current) return prev;
      let next = current;
      if (current.type === 'freehand') {
        const last = current.points[current.points.length - 1];
        if (last && Math.hypot(point.x - last.x, point.y - last.y) < 4) return prev;
        next = { ...current, points: [...current.points, point] };
      } else {
        next = { ...current, points: [current.points[0], point] };
      }
      drawingRef.current = next;
      if (next.points.length >= 2) upsertMark(next);
      return next;
    });
  };

  const finalizeDrawing = () => {
    const mark = drawingRef.current;
    if (!mark) return;
    drawingRef.current = null;
    let shouldAdd = true;
    if ((mark.type === 'rect' || mark.type === 'circle') && mark.points.length >= 2) {
      const a = mark.points[0];
      const b = mark.points[1];
      shouldAdd = Math.hypot(a.x - b.x, a.y - b.y) >= 6;
    }
    if ((mark.type === 'rect' || mark.type === 'circle') && mark.points.length < 2) shouldAdd = false;
    if (mark.type === 'freehand' && mark.points.length < 2) shouldAdd = false;
    if (shouldAdd) upsertMark(mark);
    else removeMarkById(mark.id);
    setDrawing(null);
  };

  const uploadMainImage = async (file: File | undefined) => {
    if (!file) return;
    const url = await onUploadImage(file);
    emit({ imageUrl: url, marks: [] });
  };

  const uploadReferenceImage = async (file: File | undefined) => {
    if (!file) return;
    const url = await onUploadImage(file);
    setSelectedReferenceIndex(value.referenceUrls.length);
    setReferenceZoom(1);
    setReferenceFormOpen(false);
    emit({ referenceUrls: [...value.referenceUrls, url] });
  };

  const addReferenceDraft = () => {
    const url = referenceDraft.trim();
    if (!url) return;
    const existingIndex = value.referenceUrls.indexOf(url);
    if (existingIndex >= 0) {
      setSelectedReferenceIndex(existingIndex);
    } else {
      setSelectedReferenceIndex(value.referenceUrls.length);
      emit({ referenceUrls: [...value.referenceUrls, url] });
    }
    setReferenceZoom(1);
    setReferenceFormOpen(false);
    setReferenceDraft('');
  };

  const removeReference = (index: number) => {
    const nextReferences = value.referenceUrls.filter((_, idx) => idx !== index);
    setSelectedReferenceIndex(Math.min(index, Math.max(0, nextReferences.length - 1)));
    setReferenceZoom(1);
    if (referenceRequired && nextReferences.length === 0) setReferenceFormOpen(true);
    emit({ referenceUrls: nextReferences });
  };

  const updateOutpaint = (patch: Partial<ImageEditOutpaintSettings>) => {
    emit({ outpaint: { ...outpaint, ...patch } });
  };

  const applyOutpaintPreset = (patch: Partial<ImageEditOutpaintSettings>) => {
    updateOutpaint({
      expandLeft: DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandLeft,
      expandRight: DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandRight,
      expandTop: DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandTop,
      expandBottom: DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS.expandBottom,
      ...patch,
    });
  };

  const updateInstruction = (next: string) => {
    emit({ instruction: next });
    const trimmedTail = next.slice(Math.max(0, next.length - 24));
    if (/@[^\s@#]*$/.test(trimmedTail)) {
      setMentionMenu('mark');
      return;
    }
    if (/#[^\s@#]*$/.test(trimmedTail)) {
      setMentionMenu('reference');
      return;
    }
    setMentionMenu(null);
  };

  const insertMention = (token: string) => {
    const text = String(value.instruction || '');
    const prefix = token.startsWith('@') ? '@' : '#';
    const lastIndex = text.lastIndexOf(prefix);
    let next = '';
    if (lastIndex >= 0 && !/\s/.test(text.slice(lastIndex))) {
      next = `${text.slice(0, lastIndex)}${token} `;
    } else {
      next = `${text}${text && !text.endsWith(' ') ? ' ' : ''}${token} `;
    }
    emit({ instruction: next });
    setMentionMenu(null);
  };

  const removeMark = (markId: string) => {
    emit({ marks: value.marks.filter((item) => item.id !== markId) });
  };

  const renderMark = (mark: ImageEditMark, index: number) => {
    const points = mark.points.map(toDisplayPoint);
    const label = formatEditorMarkMention(mark, index);
    const color = getMarkColor(mark.type);
    if (mark.type === 'point' && points[0]) {
      return (
        <g key={mark.id}>
          <circle cx={points[0].x} cy={points[0].y} r={5} fill={color} />
          <text x={points[0].x + 8} y={points[0].y - 8} fontSize="12" fill={color}>
            {label}
          </text>
        </g>
      );
    }
    if ((mark.type === 'rect' || mark.type === 'circle') && points.length >= 2) {
      const a = points[0];
      const b = points[1];
      const left = Math.min(a.x, b.x);
      const top = Math.min(a.y, b.y);
      const width = Math.abs(a.x - b.x);
      const height = Math.abs(a.y - b.y);
      if (mark.type === 'rect') {
        return (
          <g key={mark.id}>
            <rect x={left} y={top} width={width} height={height} fill="rgba(14, 165, 233, 0.08)" stroke={color} strokeWidth={2} />
            <text x={left + 6} y={Math.max(14, top - 8)} fontSize="12" fill={color}>
              {label}
            </text>
          </g>
        );
      }
      const cx = (a.x + b.x) / 2;
      const cy = (a.y + b.y) / 2;
      const r = Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2) / 2;
      return (
        <g key={mark.id}>
          <circle cx={cx} cy={cy} r={r} fill="rgba(139, 92, 246, 0.08)" stroke={color} strokeWidth={2} />
          <text x={cx + r + 6} y={cy} fontSize="12" fill={color}>
            {label}
          </text>
        </g>
      );
    }
    if (mark.type === 'freehand' && points.length > 1) {
      const path = points.map((point, idx) => `${idx === 0 ? 'M' : 'L'}${point.x},${point.y}`).join(' ');
      return (
        <g key={mark.id}>
          <path d={path} fill="none" stroke={color} strokeWidth={2} />
          <text x={points[0].x + 8} y={points[0].y - 8} fontSize="12" fill={color}>
            {label}
          </text>
        </g>
      );
    }
    return null;
  };

  const updateWorkspaceZoom = (delta: number) => {
    setWorkspaceZoom((current) => Math.min(1.35, Math.max(0.75, Number((current + delta).toFixed(2)))));
  };
  const updateReferenceZoom = (delta: number) => {
    setReferenceZoom((current) => Math.min(2, Math.max(0.6, Number((current + delta).toFixed(2)))));
  };
  const workspaceZoomPercent = Math.round(workspaceZoom * 100);
  const referenceZoomPercent = Math.round(referenceZoom * 100);
  const selectedReferenceUrl = value.referenceUrls[selectedReferenceIndex] || value.referenceUrls[0] || '';

  return (
    <div className={`podi-image-edit-workbench${focusMode ? ' is-focus-mode' : ''}`}>
      <div className="podi-image-edit-workbench__header">
        <div className="podi-image-edit-workbench__title">
          <span className="podi-image-edit-workbench__icon">
            <ImageEditIcon />
          </span>
          <div>
            <Typography.Text strong>AI 图编辑工作台</Typography.Text>
            <Typography.Text theme="secondary">把主图、标注/蒙版、参考图和改图目标说清楚，中台会统一编译成可追踪任务。</Typography.Text>
          </div>
        </div>
        <Button theme="primary" loading={submitting} disabled={submitting || Boolean(blockingReason)} onClick={onSubmit}>
          开始改图
        </Button>
      </div>

      <div className="podi-image-edit-workbench__editor-shell">
        <div className="podi-image-edit-workbench__workspace-bar">
          <div className="podi-image-edit-workbench__zoom-controls" aria-label="画布缩放">
            <button type="button" onClick={() => setFocusMode((open) => !open)}>
              {focusMode ? '退出大画布' : '打开大画布'}
            </button>
            <button type="button" aria-label="画布缩小" onClick={() => updateWorkspaceZoom(-0.1)}>
              -
            </button>
            <strong>{workspaceZoomPercent}%</strong>
            <button type="button" aria-label="画布放大" onClick={() => updateWorkspaceZoom(0.1)}>
              +
            </button>
            <button type="button" aria-label="画布重置" onClick={() => setWorkspaceZoom(1)}>
              重置
            </button>
          </div>
        </div>

        <div className="podi-image-edit-workbench__viewport">
          <div className="podi-image-edit-workbench__surface">
            <div className="podi-image-edit-workbench__canvas" style={{ '--podi-image-edit-zoom': workspaceZoom } as CSSProperties}>
              <div className="podi-image-edit-workbench__canvas-toolbar">
                <Input
                  value={value.imageUrl}
                  onChange={(next) => emit({ imageUrl: String(next), marks: [] })}
                  placeholder="粘贴主图 URL，或点击上传"
                  clearable
                />
                <Button variant="outline" loading={uploading} onClick={() => imageInputRef.current?.click()}>
                  上传主图
                </Button>
                <input
                  ref={imageInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  disabled={uploading}
                  onChange={async (event) => {
                    try {
                      await uploadMainImage(event.target.files?.[0]);
                    } finally {
                      event.currentTarget.value = '';
                    }
                  }}
                />
              </div>

              {isCanvasOutpaint ? (
                <div className="podi-image-edit-workbench__outpaint-panel">
                  <div className="podi-image-edit-workbench__outpaint-head">
                    <div>
                      <Typography.Text strong>扩展画布</Typography.Text>
                      <Typography.Text theme="secondary">
                        直接设置外扩像素，中台会生成目标画布和蒙版，只补全外扩区域。
                      </Typography.Text>
                    </div>
                    <Select
                      value={outpaint.anchor}
                      options={IMAGE_EDIT_OUTPAINT_ANCHOR_OPTIONS}
                      onChange={(next) => updateOutpaint({ anchor: String(next || 'center') })}
                    />
                  </div>
                  <div className="podi-image-edit-workbench__outpaint-presets">
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 128, expandRight: 128, expandTop: 128, expandBottom: 128 })}>
                      四周 +128
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 256, expandRight: 256, expandTop: 256, expandBottom: 256 })}>
                      四周 +256
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 512, expandRight: 512, expandTop: 512, expandBottom: 512 })}>
                      四周 +512
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 0, expandRight: 512, expandTop: 0, expandBottom: 0, anchor: 'left' })}>
                      向右 +512
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 512, expandRight: 0, expandTop: 0, expandBottom: 0, anchor: 'right' })}>
                      向左 +512
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 0, expandRight: 0, expandTop: 0, expandBottom: 512, anchor: 'top' })}>
                      向下 +512
                    </Button>
                    <Button size="small" variant="outline" onClick={() => applyOutpaintPreset({ expandLeft: 0, expandRight: 0, expandTop: 512, expandBottom: 0, anchor: 'bottom' })}>
                      向上 +512
                    </Button>
                  </div>
                  <div className="podi-image-edit-workbench__outpaint-grid">
                    {[
                      ['左', 'expandLeft'],
                      ['右', 'expandRight'],
                      ['上', 'expandTop'],
                      ['下', 'expandBottom'],
                    ].map(([label, key]) => (
                      <label key={key}>
                        <span>{label}</span>
                        <Input
                          value={String(outpaint[key as keyof ImageEditOutpaintSettings] ?? 0)}
                          onChange={(next) => updateOutpaint({ [key]: clampOutpaintPixels(next) } as Partial<ImageEditOutpaintSettings>)}
                          placeholder="像素"
                        />
                      </label>
                    ))}
                    <label className="is-switch">
                      <span>保持原图</span>
                      <Button
                        size="small"
                        theme={outpaint.preserveOriginal ? 'primary' : 'default'}
                        variant={outpaint.preserveOriginal ? 'base' : 'outline'}
                        onClick={() => updateOutpaint({ preserveOriginal: !outpaint.preserveOriginal })}
                      >
                        {outpaint.preserveOriginal ? '开启' : '关闭'}
                      </Button>
                    </label>
                  </div>
                  {outpaintPreview ? (
                    <div className="podi-image-edit-workbench__outpaint-summary">
                      实际输出 {outpaintPreview.targetW}×{outpaintPreview.targetH}；左 {outpaintPreview.actualLeft} / 右 {outpaintPreview.actualRight} / 上 {outpaintPreview.actualTop} / 下 {outpaintPreview.actualBottom}
                      。尺寸已按 16 倍数取整。
                    </div>
                  ) : (
                    <div className="podi-image-edit-workbench__outpaint-summary">上传主图后显示实际输出尺寸。</div>
                  )}
                </div>
              ) : (
                <div className="podi-image-edit-workbench__tool-row">
                  {(['point', 'rect', 'circle', 'freehand'] as ImageEditTool[]).map((tool) => (
                    <Button
                      key={tool}
                      size="small"
                      theme={activeTool === tool ? 'primary' : 'default'}
                      variant={activeTool === tool ? 'base' : 'outline'}
                      onClick={() => setActiveTool(tool)}
                    >
                      {formatEditorToolLabel(tool)}
                    </Button>
                  ))}
                  <Button size="small" variant="outline" onClick={() => emit({ marks: [] })}>
                    清空区域
                  </Button>
                  <Typography.Text theme="secondary">
                    {value.marks.length > 0 ? `已标注 ${value.marks.length} 个区域` : '可不标注，模型会按整图理解'}
                  </Typography.Text>
                </div>
              )}

              <div
                ref={stageRef}
                className={`podi-image-edit-workbench__stage ${value.imageUrl.trim() ? '' : 'is-empty'}${isCanvasOutpaint ? ' is-outpaint' : ''}`}
                onMouseDown={handlePointerDown}
                onMouseMove={handlePointerMove}
                onMouseUpCapture={finalizeDrawing}
                onMouseUp={finalizeDrawing}
                onMouseLeave={finalizeDrawing}
              >
                {value.imageUrl.trim() ? (
                  isCanvasOutpaint && outpaintPreview ? (
                    <div
                      className="podi-image-edit-workbench__outpaint-stage"
                      style={{ width: outpaintPreview.displayTargetW, height: outpaintPreview.displayTargetH }}
                    >
                      <div
                        className="podi-image-edit-workbench__outpaint-source"
                        style={{
                          left: outpaintPreview.displayLeft,
                          top: outpaintPreview.displayTop,
                          width: outpaintPreview.displaySourceW,
                          height: outpaintPreview.displaySourceH,
                        }}
                      >
                        <img ref={imageRef} src={value.imageUrl.trim()} alt="主图" onLoad={syncImageMeta} />
                      </div>
                      <span className="podi-image-edit-workbench__outpaint-badge">透明区域会由模型补全</span>
                    </div>
                  ) : (
                    <>
                      <img
                        ref={imageRef}
                        src={value.imageUrl.trim()}
                        alt="主图"
                        onLoad={syncImageMeta}
                        onClick={(event) => {
                          if (activeTool !== 'point') return;
                          event.stopPropagation();
                        }}
                      />
                      <svg width={imageMeta.displayW || '100%'} height={imageMeta.displayH || '100%'}>
                        {[...value.marks, ...(drawing && !value.marks.some((mark) => mark.id === drawing.id) ? [drawing] : [])].map(renderMark)}
                      </svg>
                    </>
                  )
                ) : (
                  <div className="podi-image-edit-workbench__empty">
                    <Typography.Text strong>先提供一张主图</Typography.Text>
                    <Typography.Text theme="secondary">组件会围绕这张图完成选择区域、参考图和改图指令。</Typography.Text>
                    <Button variant="outline" onClick={() => imageInputRef.current?.click()}>
                      上传主图
                    </Button>
                  </div>
                )}
              </div>

              <div className="podi-image-edit-workbench__region-panel">
                <div className="podi-image-edit-workbench__region-head">
                  <strong>@ 标注区域</strong>
                  <span>{value.marks.length}</span>
                </div>
                {value.marks.length === 0 ? (
                  <div className="podi-image-edit-workbench__region-empty">暂无标注。使用点选、矩形、圆形或手绘在图上标出要修改的位置。</div>
                ) : (
                  <div className="podi-image-edit-workbench__region-list">
                    {value.marks.map((mark, index) => (
                      <div key={mark.id} className="podi-image-edit-workbench__region-card">
                        <span className="podi-image-edit-workbench__region-dot" style={{ backgroundColor: getMarkColor(mark.type) }} />
                        <div>
                          <strong>{formatEditorMarkMention(mark, index)}</strong>
                          <small>
                            {formatEditorToolLabel(mark.type)} · {summarizeEditorMarkGeometry(mark)}
                          </small>
                        </div>
                        <button type="button" onClick={() => insertMention(formatEditorMarkMention(mark, index))}>
                          {formatEditorMarkMention(mark, index)}
                        </button>
                        <button type="button" aria-label="删除标注" onClick={() => removeMark(mark.id)}>
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <section className="podi-image-edit-workbench__prompt-dock">
                <div className="podi-image-edit-workbench__prompt-head">
                  <div>
                    <Typography.Text strong>改图指令</Typography.Text>
                    <Typography.Text theme="secondary">看完图、圈好位置后，在这里说清楚要怎么改。</Typography.Text>
                  </div>
                  <div className="podi-image-edit-workbench__prompt-actions">
                    <Select
                      value={selectedSkill}
                      options={IMAGE_EDIT_SKILL_OPTIONS.map((item) => ({
                        label: item.label,
                        value: item.value,
                      }))}
                      onChange={(next) => emit({ editSkill: String(next || 'local_modify') })}
                    />
                    <button type="button" aria-expanded={outputPanelOpen} onClick={() => setOutputPanelOpen((open) => !open)}>
                      {outputPanelOpen ? '收起输出设置' : '输出设置'}
                    </button>
                  </div>
                </div>

                <div className="podi-image-edit-workbench__composer podi-image-edit-workbench__composer--command">
                  <Textarea
                    value={value.instruction}
                    onChange={(next) => updateInstruction(String(next))}
                    autosize={{ minRows: 3, maxRows: 6 }}
                    placeholder={
                      isCanvasOutpaint
                        ? '可选：说明外扩区域希望长什么样。不填则自然延展原图背景、纹理和光照。'
                        : '例如：把 @标注1 改成蓝色陶瓷材质，其他区域保持不变。输入 @ 选择标注，输入 # 选择参考图。'
                    }
                    onFocus={() => {
                      if (/@[^\s@#]*$/.test(value.instruction)) setMentionMenu('mark');
                      if (/#[^\s@#]*$/.test(value.instruction)) setMentionMenu('reference');
                    }}
                  />
                  {mentionMenu ? (
                    <div className="podi-image-edit-workbench__mention-menu">
                      {(mentionMenu === 'mark' ? markMentionItems : referenceMentionItems).length === 0 ? (
                        <div className="podi-image-edit-workbench__mention-empty">
                          {mentionMenu === 'mark' ? '暂无标注区域，先在主图上点选或框选。' : '暂无参考图，先上传或粘贴参考图。'}
                        </div>
                      ) : (
                        (mentionMenu === 'mark' ? markMentionItems : referenceMentionItems).map((item) => (
                          <button key={item.id} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => insertMention(item.token)}>
                            <strong>{item.token}</strong>
                            <span>{item.label}</span>
                            <small>{item.meta}</small>
                          </button>
                        ))
                      )}
                    </div>
                  ) : null}
                </div>

                <div className="podi-image-edit-workbench__prompt-foot">
                  <Typography.Text theme={referenceRequired ? 'warning' : 'secondary'}>
                    {referenceRequired ? '当前改图意图需要参考图；上传后可用 #参考图1 引用。' : selectedSkillConfig.description}
                  </Typography.Text>
                  <div className="podi-image-edit-workbench__composer-hint">
                    <span>可引用：</span>
                    <button type="button" onClick={() => setMentionMenu('mark')}>
                      @ 标注区域
                    </button>
                    <button type="button" onClick={() => setMentionMenu('reference')}>
                      # 参考图
                    </button>
                  </div>
                </div>

                <Space breakLine size="small">
                  {quickPrompts.map((text) => (
                    <Button key={text} size="small" variant="outline" onClick={() => emit({ instruction: text })}>
                      {text}
                    </Button>
                  ))}
                </Space>

                {outputPanelOpen ? (
                  <div className="podi-image-edit-workbench__inline-settings">
                    <div className="podi-image-edit-workbench__setting-field">
                      <span>尺寸预设</span>
                      <Select value={customSizeValue ? undefined : outputSize} options={IMAGE_EDIT_SIZE_OPTIONS} onChange={(next) => emit({ size: String(next || 'auto') })} />
                    </div>
                    <div className="podi-image-edit-workbench__setting-field">
                      <span>自定义尺寸</span>
                      <Input
                        value={customSizeValue}
                        onChange={(next) => emit({ size: String(next || '').trim() || 'auto' })}
                        placeholder="例如 2000x1600，留空使用预设"
                        clearable
                      />
                    </div>
                    <div className="podi-image-edit-workbench__setting-field">
                      <span>质量档位</span>
                      <Select value={outputQuality} options={IMAGE_EDIT_QUALITY_OPTIONS} onChange={(next) => emit({ quality: String(next || 'auto') })} />
                    </div>
                    <div className="podi-image-edit-workbench__setting-field">
                      <span>输出格式</span>
                      <Select value={outputFormat} options={IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS} onChange={(next) => emit({ outputFormat: String(next || 'png') })} />
                    </div>
                    <div className="podi-image-edit-workbench__setting-field is-wide">
                      <span>蒙版 URL</span>
                      <Input
                        value={value.maskUrl}
                        onChange={(next) => emit({ maskUrl: String(next) })}
                        placeholder="可选；只有蒙版才会硬限制修改区域"
                        clearable
                      />
                    </div>
                    {advancedSlot}
                  </div>
                ) : null}
              </section>
            </div>
            <aside className="podi-image-edit-workbench__side-rail" aria-label="参考图操作">
              <section className="podi-image-edit-workbench__rail-card is-reference">
                <div className="podi-image-edit-workbench__rail-head">
                  <div>
                    <Typography.Text strong>参考图</Typography.Text>
                    <Typography.Text theme="secondary">
                      {value.referenceUrls.length > 0 ? `${value.referenceUrls.length} 张，可用 #参考图 引用` : referenceRequired ? '当前意图需要参考图' : '可选，用于颜色、材质或元素参照'}
                    </Typography.Text>
                  </div>
                  <Button
                    size="small"
                    theme="primary"
                    variant={referenceFormOpen ? 'base' : 'outline'}
                    aria-expanded={referenceFormOpen}
                    onClick={() => setReferenceFormOpen((open) => !open)}
                  >
                    {referenceFormOpen ? '收起' : '添加参考图'}
                  </Button>
                </div>
                {referenceRequired ? <Alert theme="warning" message="当前改图意图必须提供参考图。" /> : null}
                {referenceFormOpen ? (
                  <div className="podi-image-edit-workbench__ref-form">
                    <Button variant="outline" loading={uploading} onClick={() => referenceInputRef.current?.click()}>
                      上传本地参考图
                    </Button>
                    <div className="podi-image-edit-workbench__ref-input-row">
                      <Input value={referenceDraft} onChange={(next) => setReferenceDraft(String(next))} placeholder="或粘贴参考图 URL" clearable />
                      <Button variant="outline" onClick={addReferenceDraft}>
                        添加链接
                      </Button>
                    </div>
                  </div>
                ) : null}
                <input
                  ref={referenceInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  disabled={uploading}
                  onChange={async (event) => {
                    try {
                      await uploadReferenceImage(event.target.files?.[0]);
                    } finally {
                      event.currentTarget.value = '';
                    }
                  }}
                />
                {selectedReferenceUrl ? (
                  <div className="podi-image-edit-workbench__ref-preview">
                    <div className="podi-image-edit-workbench__ref-preview-toolbar">
                      <Typography.Text theme="secondary">预览 {formatEditorReferenceMention(selectedReferenceIndex)}</Typography.Text>
                      <div>
                        <button type="button" aria-label="参考图缩小" onClick={() => updateReferenceZoom(-0.1)}>
                          -
                        </button>
                        <strong>{referenceZoomPercent}%</strong>
                        <button type="button" aria-label="参考图放大" onClick={() => updateReferenceZoom(0.1)}>
                          +
                        </button>
                      </div>
                    </div>
                    <button type="button" className="podi-image-edit-workbench__ref-preview-image" onClick={() => onPreviewImage?.(selectedReferenceUrl, `参考图 ${selectedReferenceIndex + 1}`)}>
                      <img src={selectedReferenceUrl} alt={`参考图 ${selectedReferenceIndex + 1}`} style={{ transform: `scale(${referenceZoom})` }} />
                    </button>
                    <Button variant="outline" onClick={() => insertMention(formatEditorReferenceMention(selectedReferenceIndex))}>
                      引用当前参考图到指令
                    </Button>
                  </div>
                ) : (
                  <div className="podi-image-edit-workbench__ref-empty">
                    <Typography.Text strong>这里放参考图</Typography.Text>
                    <Typography.Text theme="secondary">上传后可直接预览、缩放，并在指令里用 #参考图1 引用。</Typography.Text>
                    <div className="podi-image-edit-workbench__ref-empty-actions">
                      <Button size="small" variant="outline" loading={uploading} onClick={() => referenceInputRef.current?.click()}>
                        上传参考图
                      </Button>
                      <Button size="small" variant="outline" onClick={() => setReferenceFormOpen(true)}>
                        粘贴链接
                      </Button>
                    </div>
                  </div>
                )}
                {value.referenceUrls.length > 0 ? (
                  <div className="podi-image-edit-workbench__refs">
                    {value.referenceUrls.map((url, index) => (
                      <div key={`${url}-${index}`} className={`podi-image-edit-workbench__ref${index === selectedReferenceIndex ? ' is-active' : ''}`}>
                        <button type="button" onClick={() => setSelectedReferenceIndex(index)}>
                          <img src={url} alt={`参考图 ${index + 1}`} />
                        </button>
                        <div>
                          <Typography.Text>{formatEditorReferenceMention(index)} · 参考图 {index + 1}</Typography.Text>
                          <Typography.Text theme="secondary" ellipsis>
                            {url}
                          </Typography.Text>
                        </div>
                        <Button size="small" variant="outline" onClick={() => insertMention(formatEditorReferenceMention(index))}>
                          引用
                        </Button>
                        <Button
                          size="small"
                          theme="danger"
                          variant="outline"
                          onClick={() => removeReference(index)}
                        >
                          删除
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            </aside>
          </div>
        </div>
      </div>

    </div>
  );
}
