import type { StatusBadgeMeta, UnifiedStatus } from "../../../types/ui";

const SUCCESS = new Set(["success", "succeeded", "completed", "done", "ok", "active", "on"]);
const FAILED = new Set(["failed", "error", "timeout", "rejected", "off"]);
const RUNNING = new Set(["running", "processing", "in_progress"]);
const QUEUED = new Set(["queued", "pending", "created"]);
const CANCELLED = new Set(["cancelled", "canceled", "stopped", "aborted"]);
const INACTIVE = new Set(["inactive", "deprecated", "disabled"]);

const defaultLabels: Record<UnifiedStatus, string> = {
  success: "成功",
  failed: "失败",
  running: "执行中",
  queued: "排队中",
  cancelled: "已取消",
  inactive: "未启用",
  unknown: "未知",
};

export function mapStatusToBadge(status?: string | null, fallbackLabel?: string): StatusBadgeMeta {
  const raw = String(status || "").trim();
  const normalizedRaw = raw.toLowerCase();

  if (SUCCESS.has(normalizedRaw)) {
    return { normalized: "success", theme: "success", text: fallbackLabel || defaultLabels.success };
  }
  if (FAILED.has(normalizedRaw)) {
    return { normalized: "failed", theme: "danger", text: fallbackLabel || defaultLabels.failed };
  }
  if (RUNNING.has(normalizedRaw)) {
    return { normalized: "running", theme: "warning", text: fallbackLabel || defaultLabels.running };
  }
  if (QUEUED.has(normalizedRaw)) {
    return { normalized: "queued", theme: "warning", text: fallbackLabel || defaultLabels.queued };
  }
  if (CANCELLED.has(normalizedRaw)) {
    return { normalized: "cancelled", theme: "default", text: fallbackLabel || defaultLabels.cancelled };
  }
  if (INACTIVE.has(normalizedRaw)) {
    return { normalized: "inactive", theme: "default", text: fallbackLabel || defaultLabels.inactive };
  }
  return {
    normalized: "unknown",
    theme: "default",
    text: raw || fallbackLabel || defaultLabels.unknown,
  };
}
