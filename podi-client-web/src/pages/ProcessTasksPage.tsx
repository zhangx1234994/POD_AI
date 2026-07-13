/**
 * AI 批处理任务页 — 列表页进入任务详情
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Clock3,
  Download,
  Grid3X3,
  ImageIcon,
  Loader2,
  RefreshCw,
  ShoppingBag,
  WandSparkles,
  X,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import { advanceClientProcessTask } from "../api";
import { assetTypeLabels } from "../utils/constants";
import type { ProcessTask, ProcessTaskStatus, ProductDesignAgentSession } from "../types";

const resumeAgentSessionKey = "podi.resumeAgentDesignSession";

function designSessionMeta(session: ProductDesignAgentSession) {
  const plans = session.plans || [];
  const plan = [...plans].reverse().find((item) => item.planId === session.currentPlanId) || plans[plans.length - 1];
  const status = session.status === "executing"
    ? "生成中"
    : session.status === "completed" || session.status === "preview_ready"
      ? "可查看"
      : session.status === "failed"
        ? "需要处理"
        : "待确认";
  return {
    plan,
    status,
    title: plan?.designBrief?.title || plan?.summaryForUser || "AI 产品设计",
    style: plan?.designBrief?.styleName,
  };
}

const statusMeta: Record<ProcessTaskStatus, { label: string; desc: string; progress: number }> = {
  pending: {
    label: "排队中",
    desc: "图片已排队，正在等待开始生成。",
    progress: 26,
  },
  processing: {
    label: "生成中",
    desc: "图片正在陆续生成，已完成的结果会先显示。",
    progress: 68,
  },
  completed: {
    label: "已完成",
    desc: "结果已写入素材库，可以预览、下载或继续做产品。",
    progress: 100,
  },
  failed: {
    label: "失败",
    desc: "任务未完成。请查看失败原因，修正后重新提交。",
    progress: 100,
  },
};

function resolveTaskTitle(task: ProcessTask) {
  return resolveTaskAbilityTitle(task);
}

const taskTypeTitles: Record<string, string> = {
  clean: "图片标准化",
  extend: "扩图",
  extract: "花纹提取",
  variation: "裂变生成",
  seamless2: "两方连续",
  seamless4: "四方连续",
  image_edit: "单图精修",
};

function resolveTaskAbilityTitle(task: ProcessTask) {
  if (task.abilityTitle && !["默认处理", "图片批处理", "默认处理任务"].includes(task.abilityTitle)) return task.abilityTitle;
  return taskTypeTitles[task.type] ?? "图片处理";
}

function isRunning(task: ProcessTask) {
  return task.status === "pending" || task.status === "processing";
}

function isDisplayableImageUrl(value?: string | null) {
  if (!value) return false;
  const url = value.trim();
  if (!url) return false;
  if (url.startsWith("/demo/") || url.startsWith("/uploads/")) return true;
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return false;
    const pathname = decodeURIComponent(parsed.pathname).toLowerCase();
    if (/\.(png|jpe?g|webp|gif|bmp|avif)$/.test(pathname)) return true;
    const filename = decodeURIComponent(parsed.searchParams.get("filename") || "").toLowerCase();
    if (/\.(png|jpe?g|webp|gif|bmp|avif)$/.test(filename)) return true;
    return (parsed.searchParams.get("response-content-type") || "").toLowerCase().startsWith("image/");
  } catch {
    return false;
  }
}

function validResultImages(task: ProcessTask) {
  return (task.resultImages || []).filter(isDisplayableImageUrl);
}

function validQueueItemImages(item?: QueueItemSnapshot) {
  return (item?.resultImages || []).filter(isDisplayableImageUrl);
}

function getTaskCountLabel(task: ProcessTask) {
  const progress = getTaskProgress(task);
  if (progress.failed > 0 && task.status === "failed") {
    return `成功 ${progress.completed} 张 · 失败 ${progress.failed} 张`;
  }
  return `已生成 ${progress.completed}/${progress.total} 张`;
}

function taskPreviewImages(task: ProcessTask) {
  const inputImages = (task.inputImages || []).filter(Boolean);
  const resultImages = validResultImages(task);
  return (inputImages.length ? inputImages : resultImages).slice(0, 4);
}

function taskResultPreviewImages(task: ProcessTask) {
  return validResultImages(task).slice(0, 4);
}

function taskUserStageLabel(task: ProcessTask) {
  const progress = getTaskProgress(task);
  if (task.status === "completed") return "结果已入库";
  if (task.status === "failed") return "生成失败";
  if (progress.completed > 0) return `${progress.completed} 张已生成`;
  if (task.status === "pending") return "排队中";
  return "生成中";
}

function taskListSubtitle(task: ProcessTask) {
  const title = resolveTaskAbilityTitle(task);
  const parts = [task.optionLabel, task.sizeLabel].filter((item): item is string => {
    if (!item) return false;
    if (["默认处理", "默认处理任务", "图片批处理"].includes(item)) return false;
    return item !== title && !item.includes(title) && !title.includes(item);
  });
  return parts.length > 0 ? parts.join(" · ") : "点开查看输入图、参数和结果";
}

type QueueItemSnapshot = {
  index?: number;
  inputIndex?: number;
  variantIndex?: number;
  inputImage?: string;
  status?: string;
  resultImages?: string[];
  errorMessage?: string | null;
};

type GenerationSlot = {
  key: string;
  index: number;
  state: "completed" | "processing" | "queued" | "failed";
  sourceImage?: string;
  resultImage?: string;
  message: string;
};

function taskQueueItems(task: ProcessTask): QueueItemSnapshot[] {
  const raw = task.params?.queueItems;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is QueueItemSnapshot => Boolean(item) && typeof item === "object");
}

function getTaskProgress(task: ProcessTask) {
  const queueItems = taskQueueItems(task);
  const total = queueItems.length || task.inputCount || task.inputImages?.length || 0;
  const resultImages = validResultImages(task);
  const completedFromItems = queueItems.filter((item) => validQueueItemImages(item).length > 0).length;
  const failed = queueItems.filter((item) => item.status === "failed").length;
  const running = queueItems.filter((item) =>
    ["dispatching", "running", "submitted", "processing"].includes(String(item.status || "").toLowerCase())
  ).length;
  const queued = queueItems.filter((item) =>
    ["queued", "pending"].includes(String(item.status || "").toLowerCase())
  ).length;
  const completed = Math.max(resultImages.length, completedFromItems);
  const safeTotal = Math.max(total, completed + failed, resultImages.length);
  return {
    total: safeTotal,
    completed,
    failed,
    running,
    queued: Math.max(0, queued || safeTotal - completed - failed - running),
  };
}

function getTaskProgressLine(task: ProcessTask) {
  const progress = getTaskProgress(task);
  if (task.status === "completed") return `${progress.completed} 张图片已生成`;
  if (task.status === "failed") return progress.completed > 0 ? `${progress.completed} 张已生成，${progress.failed || 1} 张失败` : "生成失败";
  if (progress.completed > 0) return `${progress.completed} 张已生成，剩余图片生成中`;
  return task.status === "pending" ? "等待开始生成" : "正在生成图片";
}

function getTaskStageLine(task: ProcessTask) {
  const progress = getTaskProgress(task);
  if (task.status === "completed") return "结果已保存到素材库";
  if (task.status === "failed") return task.errorMessage || "请重新提交或换一组图片再试";
  if (progress.completed > 0) return "已出的结果可先查看，剩余结果会继续刷新";
  return "可以离开页面，完成后会出现在这里";
}

function buildGenerationSlots(task: ProcessTask): GenerationSlot[] {
  const inputImages = task.inputImages ?? [];
  const resultImages = validResultImages(task);
  const queueItems = taskQueueItems(task);
  const total = Math.max(task.inputCount ?? 0, inputImages.length, queueItems.length, resultImages.length);

  if (total === 0 && resultImages.length > 0) {
    return resultImages.map((image, index) => ({
      key: `${task.id}-result-${index}`,
      index,
      state: "completed",
      resultImage: image,
      message: "已生成",
    }));
  }

  return Array.from({ length: total }, (_, index) => {
    const queueItem = queueItems.find((item) => Number(item.index) === index) ?? queueItems[index];
    const itemResult = validQueueItemImages(queueItem)[0];
    const resultImage = itemResult || resultImages[index];
    const sourceIndex = Number.isFinite(Number(queueItem?.inputIndex)) ? Number(queueItem?.inputIndex) : index;
    const sourceImage = queueItem?.inputImage || inputImages[sourceIndex] || (inputImages.length === 1 ? inputImages[0] : undefined);
    const rawStatus = String(queueItem?.status || "").toLowerCase();
    if (resultImage) {
      return {
        key: `${task.id}-slot-${index}`,
        index,
        state: "completed",
        sourceImage,
        resultImage,
        message: "已生成",
      };
    }
    if (rawStatus === "failed" || (task.status === "failed" && index >= resultImages.length)) {
      return {
        key: `${task.id}-slot-${index}`,
        index,
        state: "failed",
        sourceImage,
        message: queueItem?.errorMessage || "这张生成失败",
      };
    }
    return {
      key: `${task.id}-slot-${index}`,
      index,
      state: rawStatus === "queued" || task.status === "pending" ? "queued" : "processing",
      sourceImage,
      message: rawStatus === "queued" || task.status === "pending" ? "等待生成" : "生成中",
    };
  });
}

const pendingProductAssetKey = "podi.pendingProductDesignAssetId";

function rememberProductDesignAsset(assetId: string) {
  try {
    window.localStorage.setItem(pendingProductAssetKey, assetId);
  } catch {
    // Ignore storage failures.
  }
}

function downloadImage(url: string, name: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.click();
}

export default function ProcessTasksPage() {
  const { state, navigate, dispatch, activeUserId } = useApp();
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const tasks = state.processTasks;
  const designSessions = state.designAgentSessions;
  const tasksRef = useRef(tasks);
  const pollingRef = useRef(false);
  const advancingTaskIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

  useEffect(() => {
    let cancelled = false;

    const pollBusinessTasks = async () => {
      if (pollingRef.current) return;
      pollingRef.current = true;
      const candidates = tasksRef.current.filter((task) => {
        if (task.status === "completed" || task.status === "failed") return false;
        return Boolean(task.params?.realBusinessRun);
      });
      try {
        for (const task of candidates) {
          if (advancingTaskIdsRef.current.has(task.id)) {
            continue;
          }
          advancingTaskIdsRef.current.add(task.id);
          try {
            const nextTask = await advanceClientProcessTask({ userId: activeUserId, taskId: task.id }).catch(() => null);
            if (cancelled) return;
            if (!nextTask) {
              continue;
            }
            dispatch({
              type: "UPDATE_PROCESS_TASK",
              id: task.id,
              patch: nextTask,
            });
            const nextTaskResultImages = validResultImages(nextTask);
            if (nextTask.status === "completed" && nextTaskResultImages.length) {
              const existingIds = new Set(state.assets.map((asset) => asset.id));
              const assets = nextTaskResultImages.map((image, index) => ({
                id: nextTask.outputAssetIds[index] || `asset-${nextTask.id}-${index}`,
                type: nextTask.resultType || "processed",
                title: `${assetTypeLabels[nextTask.resultType || "processed"] ?? "处理图"} · ${resolveTaskAbilityTitle(nextTask)} ${String(index + 1).padStart(2, "0")}`,
                url: image,
                thumbnailUrl: image,
                source: resolveTaskAbilityTitle(nextTask),
                createdAt: nextTask.completedAt || nextTask.createdAt,
                selected: false,
                favorite: false,
                visibility: "private" as const,
                batchId: nextTask.id,
              })).filter((asset) => !existingIds.has(asset.id));
              if (assets.length > 0) {
                dispatch({ type: "ADD_ASSETS", assets });
              }
            }
          } finally {
            advancingTaskIdsRef.current.delete(task.id);
          }
        }
      } finally {
        pollingRef.current = false;
      }
    };

    void pollBusinessTasks();
    const timer = window.setInterval(() => {
      void pollBusinessTasks();
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeUserId, dispatch]);

  const activeTask = useMemo(
    () => tasks.find((task) => task.id === detailTaskId) ?? null,
    [detailTaskId, tasks]
  );

  const runningDesignCount = designSessions.filter((session) => session.status === "executing").length;
  const runningCount = tasks.filter(isRunning).length + runningDesignCount;
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const latestTask = tasks[0] ?? null;

  if (activeTask) {
    return <TaskDetail task={activeTask} onBack={() => setDetailTaskId(null)} />;
  }

  const resumeDesignSession = (session: ProductDesignAgentSession) => {
    try {
      window.localStorage.setItem(resumeAgentSessionKey, session.sessionId);
    } catch {
      // Ignore storage failures.
    }
    dispatch({ type: "SET_SELECTED_PRODUCT", productId: session.productId });
    navigate("productDesign");
  };

  if (tasks.length === 0 && designSessions.length === 0) {
    return (
      <main className="page-shell task-page">
        <PageHeader
          eyebrow="任务中心"
          title="还没有图片处理任务。"
          desc="从图片批处理页选择能力、上传图片并提交，任务状态和结果会集中出现在这里。"
        />
        <section className="task-empty-panel">
          <Clock3 size={28} />
          <strong>暂无任务</strong>
          <span>任务中心会保存批处理进度、结果入口和后续动作。</span>
          <button className="primary" onClick={() => navigate("process")}>
            去创建任务
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell task-page task-list-page">
      <PageHeader
        eyebrow="任务中心"
        title="生成任务与设计会话"
        desc="离开设计页面不会中断生成；从这里返回原来的方案、对话和结果。"
      />

      <section className="task-overview-strip">
        <div>
          <small>进行中</small>
          <strong>{runningCount}</strong>
          <span>等待或正在处理的任务</span>
        </div>
        <div>
          <small>已完成</small>
          <strong>{completedCount}</strong>
          <span>结果已进入素材库</span>
        </div>
        <div>
          <small>最近任务</small>
          <strong>{latestTask ? resolveTaskAbilityTitle(latestTask) : "暂无"}</strong>
          <span>{latestTask ? `${latestTask.createdAt} · ${statusMeta[latestTask.status].label}` : "创建任务后显示"}</span>
        </div>
      </section>

      {designSessions.length > 0 && (
        <section className="agent-task-panel">
          <div className="task-list-panel-head">
            <div><small>AI 产品设计</small><strong>可继续的设计</strong></div>
            <span>{runningDesignCount ? `${runningDesignCount} 个正在后台生成` : "方案与结果会一直保留"}</span>
          </div>
          <div className="agent-task-list">
            {designSessions.map((session) => {
              const meta = designSessionMeta(session);
              const preview = session.previewAsset?.thumbnailUrl || session.previewAsset?.url || session.resultAssets?.[0]?.thumbnailUrl || session.resultAssets?.[0]?.url;
              return (
                <button key={session.sessionId} className={`agent-task-row ${session.status}`} onClick={() => resumeDesignSession(session)}>
                  <span className="agent-task-preview">{preview ? <img src={preview} alt={session.productName} /> : <WandSparkles size={22} />}</span>
                  <span className="agent-task-copy">
                    <small>{session.productName}</small>
                    <strong>{meta.title}</strong>
                    <em>{[meta.style, session.updatedAt].filter(Boolean).join(" · ")}</em>
                  </span>
                  <span className="agent-task-status"><i className={session.status === "executing" ? "spin-dot" : ""} />{meta.status}</span>
                  <span className="agent-task-action">返回设计</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {tasks.length > 0 && <section className="task-list-panel">
        <div className="task-list-panel-head">
          <div>
            <small>处理记录</small>
            <strong>最近处理</strong>
          </div>
          <button className="secondary" onClick={() => navigate("process")}>
            新建任务
          </button>
        </div>

        <div className="task-table">
          {tasks.map((task) => {
            const meta = statusMeta[task.status];
            const previewImages = taskPreviewImages(task);
            const resultPreviewImages = taskResultPreviewImages(task);
            const progress = getTaskProgress(task);
            return (
              <button key={task.id} className="task-row-card" onClick={() => setDetailTaskId(task.id)}>
                <span className={`task-status-pill ${task.status}`}>{meta.label}</span>
                <span className="task-thumb-flow" aria-label="任务图片变化预览">
                  <span className="task-thumb-strip task-thumb-strip-input">
                    {previewImages.length > 0 ? (
                      previewImages.map((image, index) => (
                        <img key={`${task.id}-preview-${image}-${index}`} src={image} alt={`${resolveTaskAbilityTitle(task)} 原图 ${index + 1}`} />
                      ))
                    ) : (
                      <em>暂无原图</em>
                    )}
                  </span>
                  <span className="task-thumb-flow-arrow">→</span>
                  <span className="task-thumb-strip task-thumb-strip-output">
                    {resultPreviewImages.length > 0 ? (
                      resultPreviewImages.map((image, index) => (
                        <img key={`${task.id}-result-preview-${image}-${index}`} src={image} alt={`${resolveTaskAbilityTitle(task)} 结果 ${index + 1}`} />
                      ))
                    ) : (
                      <span className={`task-result-placeholder ${task.status}`}>{task.status === "failed" ? "失败" : "生成中"}</span>
                    )}
                    {progress.completed > 0 && <strong className="task-result-bubble">{progress.completed} 张</strong>}
                  </span>
                </span>
                <span className="task-row-main">
                  <strong>{resolveTaskAbilityTitle(task)}</strong>
                  <em>{taskListSubtitle(task)}</em>
                </span>
                <span className="task-row-progress">
                  <strong>{getTaskCountLabel(task)}</strong>
                  <em>{getTaskProgressLine(task)}</em>
                </span>
                <span className="task-row-time">
                  <strong>{task.createdAt}</strong>
                  <em>{taskUserStageLabel(task)}</em>
                </span>
                <b>详情</b>
              </button>
            );
          })}
        </div>
      </section>}
    </main>
  );
}

function TaskDetail({ task, onBack }: { task: ProcessTask; onBack: () => void }) {
  const { state, navigate, dispatch } = useApp();
  const [previewResult, setPreviewResult] = useState<{ image: string; index: number } | null>(null);
  const meta = statusMeta[task.status];
  const resultImages = validResultImages(task);
  const inputImages = task.inputImages ?? [];
  const progress = getTaskProgress(task);
  const slots = buildGenerationSlots(task);
  const hasResults = resultImages.length > 0;
  const singleSourceMultiResult = inputImages.length === 1 && slots.length > 1;
  const resultAssetId = (index: number) => task.outputAssetIds?.[index] || `asset-${task.id}-${index + 1}`;

  const ensureResultAsset = (image: string, index: number) => {
    const assetId = resultAssetId(index);
    if (!state.assets.some((asset) => asset.id === assetId)) {
      dispatch({
        type: "ADD_ASSETS",
        assets: [{
          id: assetId,
          type: task.resultType || "processed",
          title: `${assetTypeLabels[task.resultType || "processed"] ?? "处理图"} · ${resolveTaskAbilityTitle(task)} ${String(index + 1).padStart(2, "0")}`,
          url: image,
          thumbnailUrl: image,
          source: resolveTaskAbilityTitle(task),
          createdAt: task.completedAt || task.createdAt,
          selected: false,
          favorite: false,
          visibility: "private",
          batchId: task.id,
        }],
      });
    }
    return assetId;
  };

  const useResultForProduct = (image: string, index: number) => {
    const assetId = ensureResultAsset(image, index);
    rememberProductDesignAsset(assetId);
    dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: assetId });
    dispatch({ type: "SELECT_ASSETS", ids: [assetId] });
    navigate("products");
  };

  const continueProcessing = (image: string, index: number) => {
    const assetId = ensureResultAsset(image, index);
    dispatch({ type: "SELECT_ASSETS", ids: [assetId] });
    navigate("imageEditor");
  };

  return (
    <main className="page-shell task-page task-detail-page">
      <button className="process-back-link" onClick={onBack}>
        <ArrowLeft size={16} />
        返回任务列表
      </button>

      <PageHeader
        eyebrow="任务详情"
        title={resolveTaskTitle(task)}
        desc="这里展示每张图片的生成状态。已完成的结果会直接出现，未完成的图片会继续刷新。"
      />

      <section className="task-detail-layout">
        <div className="task-detail-main">
          <section className={`task-status-panel ${task.status}`}>
            <div className="task-status-head">
              <div>
                <small>当前状态</small>
                <strong>{meta.label}</strong>
                <span>{getTaskStageLine(task)}</span>
              </div>
              {hasResults && <em>{resultImages.length} 张已生成</em>}
            </div>
            <div className="task-progress-track">
              <span style={{ width: `${progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : meta.progress}%` }} />
            </div>
            <div className="task-meta-row">
              <span>提交时间：{task.createdAt}</span>
              {task.completedAt && <span>完成时间：{task.completedAt}</span>}
              <span>图片：{progress.total} 张</span>
              <span>已生成：{progress.completed} 张</span>
              <span>状态：{taskUserStageLabel(task)}</span>
            </div>
            {task.queueSummary && (
              <div className="task-queue-summary">
                <span>等待生成 {task.queueSummary.queued ?? 0}</span>
                <span>正在生成 {task.queueSummary.running ?? 0}</span>
                <span>已生成 {task.queueSummary.completed ?? 0}</span>
                <span>失败 {task.queueSummary.failed ?? 0}</span>
              </div>
            )}
            {task.status === "failed" && task.errorMessage && (
              <div className="task-error-inline" role="alert">
                {task.errorMessage}
              </div>
            )}
          </section>

          {task.status !== "completed" && (
            <section className="task-waiting-panel">
              <Loader2 className="spin" size={22} />
              <div>
                <strong>结果会陆续出现</strong>
                <span>
                  可以离开页面。完成的图片会自动保存到素材库，也会保留在下方结果区。
                </span>
              </div>
              <button className="secondary" onClick={() => navigate("assets")}>
                先去素材库
              </button>
            </section>
          )}

          {slots.length > 0 && (
            <section className="task-generation-panel">
              <div className="task-section-title">
                <div>
                  <Grid3X3 size={18} />
                  <strong>图片生成进度</strong>
                </div>
                {hasResults && (
                  <div className="task-result-actions">
                    <button className="secondary" onClick={() => navigate("assets")}>
                      <Grid3X3 size={15} />
                      打开素材库
                    </button>
                    <button className="primary" onClick={() => navigate("products")}>
                      <ShoppingBag size={15} />
                      做产品
                    </button>
                  </div>
                )}
              </div>
              <div className="task-generation-grid">
                {slots.map((slot) => (
                  <article key={slot.key} className={`generation-card ${slot.state}`}>
                    <div className="generation-pair">
                      <div className="generation-pair-cell source">
                        {slot.sourceImage ? (
                          <img src={slot.sourceImage} alt={`${resolveTaskAbilityTitle(task)} 原图 ${slot.index + 1}`} />
                        ) : (
                          <ImageIcon size={24} />
                        )}
                        <small>{singleSourceMultiResult ? "原图" : `原图 ${slot.index + 1}`}</small>
                      </div>
                      <span className="generation-pair-arrow">→</span>
                      <div className={`generation-pair-cell target ${slot.state}`}>
                        {slot.resultImage ? (
                          <button className="generation-result-button" type="button" onClick={() => setPreviewResult({ image: slot.resultImage!, index: slot.index })}>
                            <img src={slot.resultImage} alt={`${resolveTaskAbilityTitle(task)} 结果 ${slot.index + 1}`} />
                          </button>
                        ) : (
                          <>
                            {slot.state === "processing" && <Loader2 className="generation-spinner spin" size={24} />}
                            {slot.state === "queued" && <span className="generation-skeleton" />}
                            {slot.state === "failed" && <AlertCircle className="generation-error-icon" size={26} />}
                            {slot.state !== "failed" && <ImageIcon size={24} />}
                          </>
                        )}
                        <small>{slot.resultImage ? `结果 ${slot.index + 1}` : slot.state === "failed" ? "失败" : slot.state === "queued" ? "排队中" : "生成中"}</small>
                      </div>
                    </div>
                    <div className="generation-caption">
                      <strong>{slot.resultImage ? `结果 ${slot.index + 1} 已生成` : `结果 ${slot.index + 1}`}</strong>
                      <span>{slot.message}</span>
                      {slot.resultImage && (
                        <div className="generation-card-actions">
                          <button title="下载结果图" onClick={() => downloadImage(slot.resultImage!, `${task.id}-result-${slot.index + 1}.png`)}>
                            <Download size={14} />
                          </button>
                          <button title="单图精修" onClick={() => continueProcessing(slot.resultImage!, slot.index)}>
                            <WandSparkles size={14} />
                          </button>
                          <button title="做产品" onClick={() => useResultForProduct(slot.resultImage!, slot.index)}>
                            <ShoppingBag size={14} />
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="task-detail-side">
          <strong>处理设置</strong>
          <span>这些是提交时选择的能力和尺寸，方便你确认这批图的处理方式。</span>
          <div className="task-params-panel compact">
            <div>
              <small>能力</small>
              <strong>{resolveTaskAbilityTitle(task)}</strong>
            </div>
            <div>
              <small>{task.type === "extend" ? "扩图范围" : "输出尺寸"}</small>
              <strong>{task.sizeLabel}</strong>
            </div>
            <div>
              <small>处理策略</small>
              <strong>{task.optionLabel || "默认处理"}</strong>
            </div>
            <div>
              <small>输出类型</small>
              <strong>{task.outputLabel}</strong>
            </div>
          </div>
        </aside>
      </section>

      {previewResult && (
        <div className="task-result-modal-backdrop" role="presentation" onClick={() => setPreviewResult(null)}>
          <section className="task-result-modal" role="dialog" aria-modal="true" aria-label="结果图预览" onClick={(event) => event.stopPropagation()}>
            <div className="task-result-modal__media">
              <img src={previewResult.image} alt={`${resolveTaskAbilityTitle(task)} 结果 ${previewResult.index + 1}`} />
            </div>
            <div className="task-result-modal__side">
              <button className="icon-button" type="button" onClick={() => setPreviewResult(null)} aria-label="关闭">
                <X size={18} />
              </button>
              <small>{resolveTaskAbilityTitle(task)} · 结果 {previewResult.index + 1}</small>
              <strong>结果图已生成</strong>
              <p>可以下载、进入单图精修，或直接带到产品试做里做杯子。</p>
              <div className="task-result-modal__actions">
                <button className="primary" type="button" onClick={() => useResultForProduct(previewResult.image, previewResult.index)}>
                  <ShoppingBag size={15} />
                  做产品
                </button>
                <button className="secondary" type="button" onClick={() => continueProcessing(previewResult.image, previewResult.index)}>
                  <WandSparkles size={15} />
                  单图精修
                </button>
                <button className="secondary" type="button" onClick={() => downloadImage(previewResult.image, `${task.id}-result-${previewResult.index + 1}.png`)}>
                  <Download size={15} />
                  下载
                </button>
                <button className="secondary" type="button" onClick={() => navigate("assets")}>
                  <Grid3X3 size={15} />
                  打开素材库
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
