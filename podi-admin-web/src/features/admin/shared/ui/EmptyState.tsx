import { Typography } from "tdesign-react";

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="podi-empty-state">
      <Typography.Text>{title}</Typography.Text>
      {hint ? <Typography.Text theme="secondary">{hint}</Typography.Text> : null}
    </div>
  );
}
