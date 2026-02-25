import { Tag } from "tdesign-react";
import { mapStatusToBadge } from "../status";

export function StatusBadge({ status, label }: { status?: string | null; label?: string }) {
  const meta = mapStatusToBadge(status, label);
  return (
    <Tag theme={meta.theme} variant="light">
      {meta.text}
    </Tag>
  );
}
