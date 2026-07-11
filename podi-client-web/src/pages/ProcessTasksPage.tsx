/**
 * AI 批处理任务页 — 列表页进入任务详情
 */
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Clock3,
  Download,
  Grid3X3,
  Info,
  Loader2,
  RefreshCw,
  ShoppingBag,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import type { ProcessTask, ProcessTaskStatus } from "../types";

const statusMeta: Record<ProcessTaskStatus, { label: string; desc: string; progress: number }> = {
  pending: {
    label: "等待调度",
    desc: "任务已提交，正在等待处理资源。",
    progress: 26,
  },
  processing: {
    label: "处理中",
    desc: "AI 正在处理图片，完成后会自动写入素材库。",
    progress: 68,
  },
  completed: {
    label: "已完成",
    desc: "结果已写入素材库，可以预览、下载或继续做产品。",
    progress: 100,
  },
  failed: {
    label: "失败",
    desc: "任务未完成，请查看失败原因或到管理端按 runId 排查。",
    progress: 100,
  },
};

function resolveTaskTitle(task: ProcessTask) {
  return `${task.abilityTitle ?? "图片处理"}任务`;
}

function isRunning(task: ProcessTask) {
  return task.status === "pending" || task.status === "processing";
}

function getTaskCountLabel(task: ProcessTask) {
  const inputCount = task.inputCount ?? task.inputImages?.length ?? 0;
  const outputCount = task.resultCount ?? task.resultImages?.length ?? 0;
  return `${inputCount} 张输入 / ${outputCount} 张输出`;
}

export default function ProcessTasksPage() {
  const { state, navigate } = useApp();
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const tasks = state.processTasks;

  useEffect(() => {
    if (detailTaskId && !tasks.some((task) => task.id === detailTaskId)) {
      setDetailTaskId(null);
    }
  }, [detailTaskId, tasks]);

  const activeTask = useMemo(
    () => tasks.find((task) => task.id === detailTaskId) ?? null,
    [detailTaskId, tasks]
  );

  const runningCount = tasks.filter(isRunning).length;
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const latestTask = tasks[0] ?? null;

  if (activeTask) {
    return <TaskDetail task={activeTask} onBack={() => setDetailTaskId(null)} />;
  }

  if (tasks.length === 0) {
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
        title="处理记录"
        desc="这里集中查看图片批处理的运行状态和结果。任务不占主导航，属于账号下的工作记录。"
      />

      <section className="task-overview-strip">
        <div>
          <small>运行中</small>
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
          <strong>{latestTask?.abilityTitle ?? "暂无"}</strong>
          <span>{latestTask ? latestTask.createdAt : "创建任务后显示"}</span>
        </div>
      </section>

      <section className="task-list-panel">
        <div className="task-list-panel-head">
          <div>
            <small>AI 图片处理</small>
            <strong>全部任务</strong>
          </div>
          <button className="secondary" onClick={() => navigate("process")}>
            新建批处理
          </button>
        </div>

        <div className="task-table">
          {tasks.map((task) => {
            const meta = statusMeta[task.status];
            return (
              <button key={task.id} className="task-row-card" onClick={() => setDetailTaskId(task.id)}>
                <span className={`task-status-pill ${task.status}`}>{meta.label}</span>
                <span className="task-row-main">
                  <strong>{task.abilityTitle}</strong>
                  <em>{task.id}</em>
                </span>
                <span>{getTaskCountLabel(task)}</span>
                <span>{task.createdAt}</span>
                <b>查看详情</b>
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function TaskDetail({ task, onBack }: { task: ProcessTask; onBack: () => void }) {
  const { navigate } = useApp();
  const meta = statusMeta[task.status];
  const resultImages = task.resultImages ?? [];
  const inputImages = task.inputImages ?? [];
  const isCompleted = task.status === "completed";
  const isTaskRunning = isRunning(task);
  const isServerBacked = task.executionMode === "business" || Boolean(task.runIds?.length);
  const executionModeLabel = isServerBacked ? "真实业务" : "本地记录";
  const executionModeText = isServerBacked
    ? `已提交中台业务 run${task.runIds?.length ? `：${task.runIds.join(" / ")}` : ""}。`
    : "这条记录没有关联中台 runId，只能作为本地历史记录参考。";

  return (
    <main className="page-shell task-page task-detail-page">
      <button className="process-back-link" onClick={onBack}>
        <ArrowLeft size={16} />
        返回任务列表
      </button>

      <PageHeader
        eyebrow="任务详情"
        title={resolveTaskTitle(task)}
        desc={`任务号 ${task.id}。查看处理状态、关键参数和结果素材。`}
      />

      <section className="task-detail-layout">
        <div className="task-detail-main">
          <section className={`task-status-panel ${task.status}`}>
            <div className="task-status-head">
              <div>
                <small>当前状态</small>
                <strong>{meta.label}</strong>
                <span>{meta.desc}</span>
              </div>
              <em>{task.id}</em>
            </div>
            <div className="task-progress-track">
              <span style={{ width: `${meta.progress}%` }} />
            </div>
            <div className="task-meta-row">
              <span>提交时间：{task.createdAt}</span>
              {task.completedAt && <span>完成时间：{task.completedAt}</span>}
              <span>输入：{task.inputCount ?? inputImages.length} 张</span>
              <span>预计输出：{task.resultCount ?? resultImages.length} 张</span>
            </div>
            <div className={`task-runtime-note ${isServerBacked ? "server" : "demo"}`}>
              {isServerBacked ? <Info size={16} /> : <AlertCircle size={16} />}
              <span>{executionModeText}</span>
            </div>
            {task.status === "failed" && task.errorMessage && (
              <div className="task-runtime-note demo">
                <AlertCircle size={16} />
                <span>{task.errorMessage}</span>
              </div>
            )}
          </section>

          {isTaskRunning && (
            <section className="task-waiting-panel">
              <Loader2 className="spin" size={22} />
              <div>
                <strong>任务正在后台执行</strong>
                <span>可以离开页面。完成后结果会沉淀到素材库，任务列表也会更新状态。</span>
              </div>
              <button className="secondary" onClick={() => navigate("assets")}>
                先去素材库
              </button>
            </section>
          )}

          {isCompleted && (
            <section className="task-results-panel">
              <div className="task-section-title">
                <div>
                  <CheckCircle2 size={18} />
                  <strong>{resultImages.length} 张结果已生成</strong>
                </div>
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
              </div>

              <div className="task-result-grid">
                {resultImages.map((image, index) => (
                  <article key={`${task.id}-${image}-${index}`}>
                    <img src={image} alt={`${task.abilityTitle} 结果 ${index + 1}`} />
                    <div>
                      <span>{task.outputLabel ?? "处理结果"} {index + 1}</span>
                      <button title="下载">
                        <Download size={14} />
                      </button>
                      <button title="继续处理" onClick={() => navigate("process")}>
                        <RefreshCw size={14} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="task-detail-side">
          <div className="task-side-head">
            <strong>任务参数</strong>
            <em>{executionModeLabel}</em>
          </div>
          <span>用于核对本次能力、尺寸、策略和输出口径。</span>
          <dl className="task-param-list">
            <div>
              <dt>能力</dt>
              <dd>{task.abilityTitle}</dd>
            </div>
            <div>
              <dt>{task.type === "extend" ? "扩图范围" : "输出尺寸"}</dt>
              <dd>{task.sizeLabel}</dd>
            </div>
            <div>
              <dt>处理策略</dt>
              <dd>{task.optionLabel}</dd>
            </div>
            <div>
              <dt>输出类型</dt>
              <dd>{task.outputLabel}</dd>
            </div>
            <div>
              <dt>输入来源</dt>
              <dd>{task.inputAssetIds.length > 0 ? "OSS 上传素材" : "本地记录"}</dd>
            </div>
            {task.runIds?.length ? (
              <div>
                <dt>中台 run</dt>
                <dd>{task.runIds.join(" / ")}</dd>
              </div>
            ) : null}
            {task.errorMessage ? (
              <div>
                <dt>失败原因</dt>
                <dd>{task.errorMessage}</dd>
              </div>
            ) : null}
          </dl>
        </aside>
      </section>
    </main>
  );
}
