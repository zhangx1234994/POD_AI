import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import { Alert, Button, Card, Input, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import { ImageEditIcon } from 'tdesign-icons-react';
import './image-edit.css';
import {
  formatEditorToolLabel,
  getImageEditQuickPrompts,
  IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS,
  IMAGE_EDIT_QUALITY_OPTIONS,
  IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS,
  IMAGE_EDIT_SIZE_OPTIONS,
  IMAGE_EDIT_SKILL_OPTIONS,
  normalizeImageEditQuality,
} from './model';
import type { ImageEditMark, ImageEditPoint, ImageEditTool } from './model';

export type ImageEditWorkbenchValue = {
  imageUrl: string;
  editSkill: string;
  instruction: string;
  marks: ImageEditMark[];
  referenceUrls: string[];
  maskUrl: string;
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
  taskSummary?: string;
  payloadPreview?: unknown;
  advancedSlot?: ReactNode;
  docSlot?: ReactNode;
  onImageMetaChange?: (meta: { displayW: number; displayH: number; naturalW: number; naturalH: number }) => void;
};

const normalizeSkill = (value: string): string => {
  const raw = String(value || '').trim();
  if (IMAGE_EDIT_SKILL_OPTIONS.some((item) => item.value === raw)) return raw;
  return IMAGE_EDIT_SKILL_OPTIONS[0].value;
};

const formatJson = (value: unknown): string => {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return String(value || '');
  }
};

const getMarkColor = (tool: ImageEditTool): string => {
  if (tool === 'point') return '#f97316';
  if (tool === 'rect') return '#0ea5e9';
  if (tool === 'circle') return '#8b5cf6';
  return '#16a34a';
};

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
    taskSummary = '',
    payloadPreview,
    advancedSlot,
    docSlot,
    onImageMetaChange,
  } = props;

  const [activeTool, setActiveTool] = useState<ImageEditTool>('rect');
  const [drawing, setDrawing] = useState<ImageEditMark | null>(null);
  const [referenceDraft, setReferenceDraft] = useState('');
  const [imageMeta, setImageMeta] = useState({ displayW: 0, displayH: 0, naturalW: 0, naturalH: 0 });
  const idRef = useRef(1);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const referenceInputRef = useRef<HTMLInputElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const emit = useCallback(
    (patch: Partial<ImageEditWorkbenchValue>) => {
      onChange({ ...value, ...patch });
    },
    [onChange, value],
  );

  const selectedSkill = normalizeSkill(value.editSkill);
  const selectedSkillConfig = useMemo(
    () => IMAGE_EDIT_SKILL_OPTIONS.find((item) => item.value === selectedSkill) || IMAGE_EDIT_SKILL_OPTIONS[0],
    [selectedSkill],
  );
  const quickPrompts = useMemo(() => getImageEditQuickPrompts(selectedSkill), [selectedSkill]);
  const referenceRequired = IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS.has(selectedSkill);
  const outputSize = String(value.size || 'auto');
  const outputQuality = normalizeImageEditQuality(value.quality);
  const outputFormat = String(value.outputFormat || 'png');
  const customSizeValue = IMAGE_EDIT_SIZE_OPTIONS.some((item) => item.value === outputSize) ? '' : outputSize;

  const syncImageMeta = useCallback(() => {
    const img = imageRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const nextMeta = {
      displayW: rect.width,
      displayH: rect.height,
      naturalW: img.naturalWidth || rect.width,
      naturalH: img.naturalHeight || rect.height,
    };
    setImageMeta(nextMeta);
    onImageMetaChange?.(nextMeta);
  }, [onImageMetaChange]);

  useEffect(() => {
    if (!value.imageUrl.trim()) return;
    syncImageMeta();
    const handleResize = () => syncImageMeta();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [syncImageMeta, value.imageUrl]);

  const getDisplayPoint = (evt: ReactMouseEvent): ImageEditPoint | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const rect = stage.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return {
      x: Math.max(0, Math.min(rect.width, evt.clientX - rect.left)),
      y: Math.max(0, Math.min(rect.height, evt.clientY - rect.top)),
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
      name: `区域${seq}`,
      type: tool,
      points,
      created_at: Date.now(),
    };
  };

  const handlePointerDown = (evt: ReactMouseEvent) => {
    if (!value.imageUrl.trim()) return;
    const displayPoint = getDisplayPoint(evt);
    if (!displayPoint) return;
    const point = toOrigPoint(displayPoint);
    if (activeTool === 'point') {
      emit({ marks: [...value.marks, createMark('point', [point])] });
      return;
    }
    setDrawing(createMark(activeTool, [point]));
  };

  const handlePointerMove = (evt: ReactMouseEvent) => {
    if (!drawing) return;
    const displayPoint = getDisplayPoint(evt);
    if (!displayPoint) return;
    const point = toOrigPoint(displayPoint);
    setDrawing((prev) => {
      if (!prev) return prev;
      if (prev.type === 'freehand') {
        const last = prev.points[prev.points.length - 1];
        if (last && Math.hypot(point.x - last.x, point.y - last.y) < 4) return prev;
        return { ...prev, points: [...prev.points, point] };
      }
      return { ...prev, points: [prev.points[0], point] };
    });
  };

  const finalizeDrawing = () => {
    if (!drawing) return;
    const mark = drawing;
    let shouldAdd = true;
    if ((mark.type === 'rect' || mark.type === 'circle') && mark.points.length >= 2) {
      const a = mark.points[0];
      const b = mark.points[1];
      shouldAdd = Math.hypot(a.x - b.x, a.y - b.y) >= 6;
    }
    if ((mark.type === 'rect' || mark.type === 'circle') && mark.points.length < 2) shouldAdd = false;
    if (mark.type === 'freehand' && mark.points.length < 2) shouldAdd = false;
    if (shouldAdd) emit({ marks: [...value.marks, mark] });
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
    emit({ referenceUrls: [...value.referenceUrls, url] });
  };

  const addReferenceDraft = () => {
    const url = referenceDraft.trim();
    if (!url) return;
    emit({ referenceUrls: value.referenceUrls.includes(url) ? value.referenceUrls : [...value.referenceUrls, url] });
    setReferenceDraft('');
  };

  const renderMark = (mark: ImageEditMark, index: number) => {
    const points = mark.points.map(toDisplayPoint);
    const label = mark.name || `区域${index + 1}`;
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

  return (
    <div className="podi-image-edit-workbench">
      <div className="podi-image-edit-workbench__header">
        <div className="podi-image-edit-workbench__title">
          <span className="podi-image-edit-workbench__icon">
            <ImageEditIcon />
          </span>
          <div>
            <Typography.Text strong>图编辑组件工作台</Typography.Text>
            <Typography.Text theme="secondary">主图、选择区域、参考图和改图目标会被统一编译成中台任务。</Typography.Text>
          </div>
        </div>
        <Button theme="primary" loading={submitting} disabled={submitting || Boolean(blockingReason)} onClick={onSubmit}>
          开始改图
        </Button>
      </div>

      <div className="podi-image-edit-workbench__modes">
        {IMAGE_EDIT_SKILL_OPTIONS.map((item) => (
          <button
            key={item.value}
            type="button"
            className={item.value === selectedSkill ? 'is-active' : ''}
            onClick={() => emit({ editSkill: item.value })}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </div>

      <div className="podi-image-edit-workbench__grid">
        <div className="podi-image-edit-workbench__canvas">
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

          <div
            ref={stageRef}
            className={`podi-image-edit-workbench__stage ${value.imageUrl.trim() ? '' : 'is-empty'}`}
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={finalizeDrawing}
            onMouseLeave={finalizeDrawing}
          >
            {value.imageUrl.trim() ? (
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
                  {[...value.marks, ...(drawing ? [drawing] : [])].map(renderMark)}
                </svg>
              </>
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
        </div>

        <aside className="podi-image-edit-workbench__inspector">
          <Card bordered title="改图目标">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Tag theme={referenceRequired ? 'warning' : 'success'} variant="light">
                {selectedSkillConfig.label}
              </Tag>
              <Textarea
                value={value.instruction}
                onChange={(next) => emit({ instruction: String(next) })}
                autosize={{ minRows: 4, maxRows: 8 }}
                placeholder="例如：把圈出的杯子改成蓝色陶瓷材质，其他区域保持不变。"
              />
              <Space breakLine size="small">
                {quickPrompts.map((text) => (
                  <Button key={text} size="small" variant="outline" onClick={() => emit({ instruction: text })}>
                    {text}
                  </Button>
                ))}
              </Space>
            </Space>
          </Card>

          <Card bordered title={`参考图（${value.referenceUrls.length}）`}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {referenceRequired ? <Alert theme="warning" message="当前模式必须上传参考图。" /> : null}
              <Space align="center" style={{ width: '100%' }}>
                <Input
                  value={referenceDraft}
                  onChange={(next) => setReferenceDraft(String(next))}
                  placeholder="粘贴参考图 URL"
                  clearable
                />
                <Button variant="outline" onClick={addReferenceDraft}>
                  添加
                </Button>
                <Button variant="outline" loading={uploading} onClick={() => referenceInputRef.current?.click()}>
                  上传
                </Button>
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
              </Space>
              {value.referenceUrls.length === 0 ? (
                <Typography.Text theme="secondary">暂无参考图。</Typography.Text>
              ) : (
                <div className="podi-image-edit-workbench__refs">
                  {value.referenceUrls.map((url, index) => (
                    <div key={`${url}-${index}`} className="podi-image-edit-workbench__ref">
                      <button type="button" onClick={() => onPreviewImage?.(url, `参考图 ${index + 1}`)}>
                        <img src={url} alt={`参考图 ${index + 1}`} />
                      </button>
                      <div>
                        <Typography.Text>参考图 {index + 1}</Typography.Text>
                        <Typography.Text theme="secondary" ellipsis>
                          {url}
                        </Typography.Text>
                      </div>
                      <Button
                        size="small"
                        theme="danger"
                        variant="outline"
                        onClick={() => emit({ referenceUrls: value.referenceUrls.filter((_, idx) => idx !== index) })}
                      >
                        删除
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Space>
          </Card>

          <Card bordered title="输出设置">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Select value={customSizeValue ? undefined : outputSize} options={IMAGE_EDIT_SIZE_OPTIONS} onChange={(next) => emit({ size: String(next || 'auto') })} />
              <Input
                value={customSizeValue}
                onChange={(next) => emit({ size: String(next || '').trim() || 'auto' })}
                placeholder="自定义尺寸，例如 2000x1600。留空时使用上方预设。"
                clearable
              />
              <Select
                value={outputQuality}
                options={IMAGE_EDIT_QUALITY_OPTIONS}
                onChange={(next) => emit({ quality: String(next || 'auto') })}
              />
              <Select
                value={outputFormat}
                options={IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS}
                onChange={(next) => emit({ outputFormat: String(next || 'png') })}
              />
              <Input
                value={value.maskUrl}
                onChange={(next) => emit({ maskUrl: String(next) })}
                placeholder="可选：蒙版 URL。只有蒙版才会硬限制修改区域。"
                clearable
              />
              {advancedSlot}
            </Space>
          </Card>

          <Card bordered title="任务检查">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {blockingReason ? (
                <Alert theme="warning" message={blockingReason} />
              ) : (
                <Alert theme="success" message="输入已就绪，可以提交一次可复盘的图编辑任务。" />
              )}
              <pre className="podi-image-edit-workbench__summary">{taskSummary || '暂无任务摘要。'}</pre>
              <details className="podi-image-edit-workbench__payload">
                <summary>查看请求预览</summary>
                <pre>{formatJson(payloadPreview)}</pre>
              </details>
            </Space>
          </Card>
        </aside>
      </div>

      {docSlot}
    </div>
  );
}
