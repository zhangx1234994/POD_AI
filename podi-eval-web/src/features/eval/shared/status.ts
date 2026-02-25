import type { StatusBadgeMeta } from "../../../types/ui";

const SUCCESS = new Set(["success", "succeeded", "completed", "done", "ok"]);
const FAILED = new Set(["failed", "error", "timeout", "rejected"]);
const RUNNING = new Set(["running", "processing", "in_progress"]);
const QUEUED = new Set(["queued", "pending", "created", "submitted"]);
const CANCELLED = new Set(["cancelled", "canceled", "stopped", "aborted"]);

export function mapStatusToBadge(status?: string | null): StatusBadgeMeta {
  const raw = String(status || "").trim();
  const normalized = raw.toLowerCase();

  if (SUCCESS.has(normalized)) return { normalized: "success", theme: "success", text: "成功" };
  if (FAILED.has(normalized)) return { normalized: "failed", theme: "danger", text: "失败" };
  if (RUNNING.has(normalized)) return { normalized: "running", theme: "warning", text: "执行中" };
  if (QUEUED.has(normalized)) return { normalized: "queued", theme: "warning", text: "排队中" };
  if (CANCELLED.has(normalized)) return { normalized: "cancelled", theme: "default", text: "已取消" };
  return { normalized: "unknown", theme: "default", text: raw || "未知" };
}
