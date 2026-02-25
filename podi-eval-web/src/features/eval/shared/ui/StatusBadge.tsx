import { Tag } from "tdesign-react";
import { mapStatusToBadge } from "../status";

export function StatusBadge({ status, fallbackText }: { status?: string | null; fallbackText?: string }) {
  const meta = mapStatusToBadge(status);
  const explicit = String(fallbackText || '').trim();
  const text = explicit || (meta.normalized === 'unknown' ? String(status || meta.text) : meta.text);
  return (
    <Tag theme={meta.theme} variant="light">
      {text}
    </Tag>
  );
}
