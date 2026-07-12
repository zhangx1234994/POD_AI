import { useMemo, useRef, useState, type PointerEvent } from "react";
import {
  ArrowLeft,
  Circle,
  ClipboardList,
  Eraser,
  ImageIcon,
  MousePointer2,
  PenLine,
  Plus,
  Scan,
  Send,
  Sparkles,
  SquareDashedMousePointer,
  X,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { createClientAsset, createClientProcessTask, uploadClientImage } from "../api";
import type { AssetItem } from "../types";

type MarkTool = "point" | "rect" | "circle" | "freehand";
type EditSkill = "local_modify" | "reference_transfer" | "remove_inpaint" | "canvas_outpaint";
type OutputQuality = "preview" | "production" | "premium";

interface ImageMark {
  id: string;
  tool: MarkTool;
  mention: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  points?: Array<{ x: number; y: number }>;
}

interface DraftMark {
  tool: MarkTool;
  startX: number;
  startY: number;
  x: number;
  y: number;
  points: Array<{ x: number; y: number }>;
}

const markTools: Array<{ id: MarkTool; label: string; icon: typeof MousePointer2 }> = [
  { id: "point", label: "点选", icon: MousePointer2 },
  { id: "rect", label: "矩形", icon: SquareDashedMousePointer },
  { id: "circle", label: "圆形", icon: Circle },
  { id: "freehand", label: "手绘", icon: PenLine },
];

const editSkills: Array<{ id: EditSkill; label: string }> = [
  { id: "local_modify", label: "局部精修" },
  { id: "reference_transfer", label: "参考图替换" },
  { id: "remove_inpaint", label: "删除修补" },
  { id: "canvas_outpaint", label: "扩展画布" },
];

const qualityOptions: Array<{ id: OutputQuality; label: string }> = [
  { id: "preview", label: "预览" },
  { id: "production", label: "生产" },
  { id: "premium", label: "高质" },
];
const IMAGE_EDIT_CREDIT_COST = 6;

function displayTitle(asset?: AssetItem | null) {
  if (!asset) return "未选择主图";
  return asset.title.length > 24 ? `${asset.title.slice(0, 24)}...` : asset.title;
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

function normalizeBox(mark: DraftMark) {
  const x = Math.min(mark.startX, mark.x);
  const y = Math.min(mark.startY, mark.y);
  const width = Math.abs(mark.x - mark.startX);
  const height = Math.abs(mark.y - mark.startY);
  return {
    x: clampPercent(x),
    y: clampPercent(y),
    width: clampPercent(width),
    height: clampPercent(height),
  };
}

function markGeometryText(mark: ImageMark) {
  if (mark.tool === "point") return `点选位置 x=${mark.x.toFixed(1)}%, y=${mark.y.toFixed(1)}%`;
  if (mark.tool === "freehand") return `手绘区域 ${mark.points?.length || 0} 个定位点`;
  return `区域 x=${mark.x.toFixed(1)}%, y=${mark.y.toFixed(1)}%, w=${(mark.width || 0).toFixed(1)}%, h=${(mark.height || 0).toFixed(1)}%`;
}

function normalizeImageUrl(value: string) {
  const raw = value.trim();
  if (!raw) return "";
  if (typeof window === "undefined") return raw;
  try {
    return new URL(raw, window.location.origin).href;
  } catch {
    return raw;
  }
}

function outputSizeForApi(value: string) {
  return value === "原图尺寸" ? "auto" : value;
}

export default function ImageEditorPage() {
  const { state, dispatch, navigate, activeUserId, isAuthenticated } = useApp();
  const selectedAsset =
    state.assets.find((asset) => state.selectedAssetIds.includes(asset.id) && asset.visibility !== "removed") ??
    state.assets.find((asset) => asset.visibility !== "removed" && asset.type !== "product_preview") ??
    null;
  const [manualImageUrl, setManualImageUrl] = useState("");
  const [activeTool, setActiveTool] = useState<MarkTool>("rect");
  const [editSkill, setEditSkill] = useState<EditSkill>("local_modify");
  const [instruction, setInstruction] = useState("");
  const [referenceInput, setReferenceInput] = useState("");
  const [referenceUrls, setReferenceUrls] = useState<string[]>([]);
  const [marks, setMarks] = useState<ImageMark[]>([]);
  const [draftMark, setDraftMark] = useState<DraftMark | null>(null);
  const [quality, setQuality] = useState<OutputQuality>("production");
  const [outputSize, setOutputSize] = useState("原图尺寸");
  const [notice, setNotice] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedPayload, setSubmittedPayload] = useState<Record<string, unknown> | null>(null);
  const [uploadingMainImage, setUploadingMainImage] = useState(false);
  const mainImageInputRef = useRef<HTMLInputElement | null>(null);

  const imageUrl = manualImageUrl.trim() || selectedAsset?.url || selectedAsset?.thumbnailUrl || "";
  const submitImageUrl = normalizeImageUrl(imageUrl);
  const activeSourceAsset = manualImageUrl.trim() ? null : selectedAsset;
  const selectedAssetLabel = displayTitle(selectedAsset);

  const payload = useMemo(() => {
    const refs = referenceUrls.map((url, index) => ({
      url: normalizeImageUrl(url),
      label: `参考图${index + 1}`,
      mention: `#参考图${index + 1}`,
      role: "reference",
    }));
    return {
      version: "gpt-image2-editor-v1",
      imageUrl: submitImageUrl,
      instruction,
      prompt: instruction,
      skill: editSkill,
      editSkill,
      quality,
      size: outputSizeForApi(outputSize),
      output_format: "png",
      source: "podi-client-image-editor",
      channel: "client-image-editor",
      sourceAssetId: activeSourceAsset?.id || null,
      referenceImages: refs,
      selectionHints: marks.map((mark) => ({
        mention: mark.mention,
        type: mark.tool,
        geometryText: markGeometryText(mark),
        box: mark.tool === "freehand" ? undefined : {
          x: mark.x,
          y: mark.y,
          width: mark.width || 0,
          height: mark.height || 0,
        },
        points: mark.points,
      })),
      metadata: {
        sourceAssetId: activeSourceAsset?.id || null,
        sourceAssetTitle: activeSourceAsset?.title || null,
        referenceImageUrls: referenceUrls.map(normalizeImageUrl),
        markCount: marks.length,
      },
    };
  }, [activeSourceAsset, editSkill, instruction, marks, outputSize, quality, referenceUrls, submitImageUrl]);

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2600);
  };

  const pointFromEvent = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: clampPercent(((event.clientX - rect.left) / rect.width) * 100),
      y: clampPercent(((event.clientY - rect.top) / rect.height) * 100),
    };
  };

  const addMark = (mark: Omit<ImageMark, "id" | "mention">) => {
    const nextIndex = marks.length + 1;
    setMarks((items) => [
      ...items,
      {
        ...mark,
        id: `mark-${Date.now()}-${nextIndex}`,
        mention: `@标注${nextIndex}`,
      },
    ]);
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!imageUrl) return;
    const point = pointFromEvent(event);
    event.currentTarget.setPointerCapture(event.pointerId);
    if (activeTool === "point") {
      addMark({ tool: "point", x: point.x, y: point.y, width: 0, height: 0 });
      return;
    }
    setDraftMark({
      tool: activeTool,
      startX: point.x,
      startY: point.y,
      x: point.x,
      y: point.y,
      points: [point],
    });
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!draftMark) return;
    const point = pointFromEvent(event);
    setDraftMark((draft) => {
      if (!draft) return draft;
      return {
        ...draft,
        x: point.x,
        y: point.y,
        points: draft.tool === "freehand" ? [...draft.points, point] : draft.points,
      };
    });
  };

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (!draftMark) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (draftMark.tool === "freehand") {
      addMark({
        tool: "freehand",
        x: draftMark.startX,
        y: draftMark.startY,
        points: draftMark.points,
      });
      setDraftMark(null);
      return;
    }
    const box = normalizeBox(draftMark);
    if (box.width < 1 && box.height < 1) {
      addMark({ tool: draftMark.tool, x: draftMark.startX, y: draftMark.startY, width: 0, height: 0 });
    } else {
      addMark({ tool: draftMark.tool, ...box });
    }
    setDraftMark(null);
  };

  const addReference = () => {
    const value = referenceInput.trim();
    if (!value) return;
    setReferenceUrls((items) => [...items, value]);
    setReferenceInput("");
  };

  const insertMention = (mention: string) => {
    setInstruction((value) => `${value}${value && !value.endsWith(" ") ? " " : ""}${mention} `);
  };

  const uploadMainImage = async (file: File | undefined) => {
    if (!file || uploadingMainImage) return;
    if (!isAuthenticated) {
      setSubmitError("请先登录，上传图片后会保存到你的素材库。");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    setUploadingMainImage(true);
    setSubmitError("");
    try {
      const upload = await uploadClientImage(file, activeUserId);
      const title = file.name.replace(/\.[^.]+$/, "") || "上传图片";
      const asset = await createClientAsset({
        userId: activeUserId,
        type: "original",
        title,
        url: upload.url,
        thumbnailUrl: upload.url,
        source: "单图精修上传",
        visibility: "private",
        metadata: {
          objectKey: upload.objectKey ?? null,
          originalFileName: file.name,
          uploadSource: "image-editor-main-image",
        },
      });
      dispatch({ type: "ADD_ASSETS", assets: [asset] });
      dispatch({ type: "SELECT_ASSETS", ids: [asset.id] });
      setManualImageUrl("");
      setMarks([]);
      showNotice("主图已上传，可以直接标注并精修。");
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "主图上传失败，请稍后重试。");
    } finally {
      setUploadingMainImage(false);
    }
  };

  const submitEditorRequest = async () => {
    if (!submitImageUrl) {
      showNotice("先选择或粘贴一张主图。");
      return;
    }
    if (submitImageUrl.startsWith("blob:")) {
      setSubmitError("这张图还是本地临时地址，图片生成服务读取不到。请先上传到素材库或使用云端图片。");
      return;
    }
    if (!instruction.trim()) {
      showNotice("先写清楚这张图要改成什么样。");
      return;
    }
    if (!isAuthenticated) {
      setSubmitError("请先登录，精修任务会保存到你的任务中心和素材库。");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    if (IMAGE_EDIT_CREDIT_COST > state.aiCredits) {
      setSubmitError(`积分不足：单图精修需要 ${IMAGE_EDIT_CREDIT_COST} 积分，当前可用 ${state.aiCredits} 积分。`);
      window.setTimeout(() => navigate("wallet"), 900);
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    setSubmittedPayload(payload);
    try {
      const task = await createClientProcessTask({
        userId: activeUserId,
        type: "image_edit",
        abilityTitle: "单图精修",
        outputLabel: "精修结果",
        inputAssetIds: activeSourceAsset?.id ? [activeSourceAsset.id] : [],
        inputImages: [submitImageUrl],
        optionLabel: editSkills.find((item) => item.id === editSkill)?.label || "单图精修",
        sizeLabel: outputSize,
        outputCount: 1,
        params: {
          realBusinessRun: true,
          businessKey: "image_edit",
          candidateCount: 1,
          expectedOutputCount: 1,
          costCredits: IMAGE_EDIT_CREDIT_COST,
          businessRunIds: [],
          resultImages: [],
          submitMode: "real-image-edit",
          requestPayloadTemplate: payload,
          imageEditor: {
            skill: editSkill,
            markCount: marks.length,
            referenceCount: referenceUrls.length,
          },
        },
      });
      dispatch({ type: "ADD_PROCESS_TASK", task });
      if (task.wallet) dispatch({ type: "SET_WALLET", wallet: task.wallet });
      showNotice("精修任务已提交，结果会回到任务中心。");
      navigate("tasks");
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "精修任务提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="page-shell image-editor-page">
      <div className="image-editor-topbar">
        <button className="secondary" onClick={() => navigate(state.previousView === "inspire" ? "inspire" : "assets")}>
          <ArrowLeft size={16} />
          返回
        </button>
        <div className="image-editor-source">
          <ImageIcon size={18} />
          <span>{selectedAssetLabel}</span>
        </div>
        <button className="secondary" onClick={() => navigate("process")}>
          <ClipboardList size={15} />
          多图批处理
        </button>
      </div>

      <section className="image-editor-url-row">
        <input
          ref={mainImageInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(event) => {
            void uploadMainImage(event.target.files?.[0]);
            event.currentTarget.value = "";
          }}
        />
        <input
          value={manualImageUrl}
          onChange={(event) => setManualImageUrl(event.target.value)}
          placeholder="粘贴主图 URL，或从素材库选择一张图"
        />
        <button className="secondary" onClick={() => mainImageInputRef.current?.click()} disabled={uploadingMainImage}>
          <Plus size={15} />
          {uploadingMainImage ? "上传中" : "上传主图"}
        </button>
        <button
          className="secondary"
          onClick={() => {
            dispatch({ type: "CLEAR_SELECTION" });
            setManualImageUrl("");
            navigate("assets");
          }}
        >
          从素材库选
        </button>
      </section>

      <section className="image-editor-workbench">
        <div className="image-editor-canvas-shell">
          <div className="image-editor-toolbar" aria-label="标注工具">
            {markTools.map((tool) => {
              const Icon = tool.icon;
              return (
                <button
                  key={tool.id}
                  className={activeTool === tool.id ? "active" : ""}
                  onClick={() => setActiveTool(tool.id)}
                  title={tool.label}
                >
                  <Icon size={15} />
                  <span>{tool.label}</span>
                </button>
              );
            })}
            <button className="ghost" onClick={() => setMarks([])} title="清空标注">
              <Eraser size={15} />
              <span>清空</span>
            </button>
          </div>

          <div
            className={`image-editor-stage ${imageUrl ? "" : "is-empty"}`}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          >
            {imageUrl ? (
              <>
                <img src={imageUrl} alt="待精修主图" draggable={false} />
                <svg className="image-editor-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
                  {marks.map((mark, index) => {
                    if (mark.tool === "point") {
                      return (
                        <g key={mark.id}>
                          <circle cx={mark.x} cy={mark.y} r="1.8" />
                          <text x={mark.x + 2} y={mark.y + 1.5}>{index + 1}</text>
                        </g>
                      );
                    }
                    if (mark.tool === "circle") {
                      return <ellipse key={mark.id} cx={mark.x + (mark.width || 0) / 2} cy={mark.y + (mark.height || 0) / 2} rx={(mark.width || 4) / 2} ry={(mark.height || 4) / 2} />;
                    }
                    if (mark.tool === "freehand") {
                      const path = (mark.points || []).map((point, pointIndex) => `${pointIndex === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
                      return <path key={mark.id} d={path} />;
                    }
                    return <rect key={mark.id} x={mark.x} y={mark.y} width={mark.width || 4} height={mark.height || 4} rx="1.2" />;
                  })}
                  {draftMark && draftMark.tool !== "freehand" ? (
                    <rect className="draft" {...normalizeBox(draftMark)} rx="1.2" />
                  ) : null}
                  {draftMark?.tool === "freehand" ? (
                    <path className="draft" d={draftMark.points.map((point, pointIndex) => `${pointIndex === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ")} />
                  ) : null}
                </svg>
              </>
            ) : (
              <div className="image-editor-empty">
                <ImageIcon size={34} />
                <strong>先提供一张主图</strong>
                <span>上传、粘贴 URL，或从素材库选择一张图片。</span>
                <button className="primary" onClick={() => mainImageInputRef.current?.click()} disabled={uploadingMainImage}>
                  <Plus size={16} />
                  {uploadingMainImage ? "上传中" : "上传主图"}
                </button>
              </div>
            )}
          </div>

          <section className="image-editor-marks">
            <div>
              <strong>@ 标注区域</strong>
              <span>{marks.length ? `${marks.length} 个位置` : "暂无标注"}</span>
            </div>
            {marks.length ? (
              <div className="image-editor-mark-list">
                {marks.map((mark) => (
                  <button key={mark.id} onClick={() => insertMention(mark.mention)}>
                    <span>{mark.mention}</span>
                    <small>{markGeometryText(mark)}</small>
                    <X
                      size={14}
                      onClick={(event) => {
                        event.stopPropagation();
                        setMarks((items) => items.filter((item) => item.id !== mark.id));
                      }}
                    />
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <section className="image-editor-composer">
            <div className="image-editor-skill-row">
              {editSkills.map((skill) => (
                <button key={skill.id} className={editSkill === skill.id ? "active" : ""} onClick={() => setEditSkill(skill.id)}>
                  {skill.label}
                </button>
              ))}
            </div>
            <textarea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="例如：把 @标注1 的图案改成蓝色陶瓷质感，整体保持原来的构图和清晰度。"
            />
            <div className="image-editor-submit-row">
              <div className="image-editor-inline-settings">
                <label>
                  尺寸
                  <select value={outputSize} onChange={(event) => setOutputSize(event.target.value)}>
                    <option>原图尺寸</option>
                    <option>1024x1024</option>
                    <option>1536x1536</option>
                    <option>2048x2048</option>
                  </select>
                </label>
                <label>
                  质量
                  <select value={quality} onChange={(event) => setQuality(event.target.value as OutputQuality)}>
                    {qualityOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                </label>
              </div>
              <button className="primary" onClick={submitEditorRequest} disabled={submitting}>
                <Send size={16} />
                {submitting ? "提交中..." : "提交精修任务"}
              </button>
            </div>
            {submitError ? <p className="image-editor-submit-error">{submitError}</p> : null}
          </section>
        </div>

        <aside className="image-editor-rail">
          <section>
            <div className="image-editor-rail-head">
              <strong># 参考图</strong>
              <span>{referenceUrls.length}</span>
            </div>
            <div className="image-editor-ref-input">
              <input
                value={referenceInput}
                onChange={(event) => setReferenceInput(event.target.value)}
                placeholder="粘贴参考图 URL"
              />
              <button className="secondary" onClick={addReference}>
                <Plus size={14} />
              </button>
            </div>
            {referenceUrls.length ? (
              <div className="image-editor-ref-list">
                {referenceUrls.map((url, index) => (
                  <button key={`${url}-${index}`} onClick={() => insertMention(`#参考图${index + 1}`)}>
                    <img src={url} alt={`参考图 ${index + 1}`} />
                    <span>{`#参考图${index + 1}`}</span>
                    <X
                      size={14}
                      onClick={(event) => {
                        event.stopPropagation();
                        setReferenceUrls((items) => items.filter((_, itemIndex) => itemIndex !== index));
                      }}
                    />
                  </button>
                ))}
              </div>
            ) : (
              <div className="image-editor-rail-empty">
                <Scan size={22} />
                <span>需要匹配颜色、材质或元素时再加参考图。</span>
              </div>
            )}
          </section>

          <section className="image-editor-request-card">
            <div className="image-editor-rail-head">
              <strong>任务参数</strong>
              <Sparkles size={16} />
            </div>
            <dl>
              <div>
                <dt>主图</dt>
                <dd>{imageUrl ? "已就绪" : "未选择"}</dd>
              </div>
              <div>
                <dt>标注</dt>
                <dd>{marks.length} 个</dd>
              </div>
              <div>
                <dt>参考图</dt>
                <dd>{referenceUrls.length} 张</dd>
              </div>
              <div>
                <dt>输出</dt>
                <dd>{outputSize} · PNG</dd>
              </div>
              <div>
                <dt>积分</dt>
                <dd>{IMAGE_EDIT_CREDIT_COST} 积分</dd>
              </div>
            </dl>
          </section>

          {submittedPayload ? (
            <details className="image-editor-payload" open>
              <summary>已生成请求预览</summary>
              <pre>{JSON.stringify(submittedPayload, null, 2)}</pre>
            </details>
          ) : null}
        </aside>
      </section>

      {notice ? <div className="floating-notice">{notice}</div> : null}
    </main>
  );
}
