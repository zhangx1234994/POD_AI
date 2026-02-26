import type { ReactNode } from "react";
import { Space, Typography } from "tdesign-react";

type FilterBarProps = {
  title?: ReactNode;
  description?: ReactNode;
  controls: ReactNode;
};

export function FilterBar({ title, description, controls }: FilterBarProps) {
  return (
    <div className="podi-filter-bar">
      {(title || description) ? (
        <Space direction="vertical" size={2}>
          {title ? <Typography.Text strong>{title}</Typography.Text> : null}
          {description ? <Typography.Text theme="secondary">{description}</Typography.Text> : null}
        </Space>
      ) : null}
      <div className="podi-filter-bar__controls">{controls}</div>
    </div>
  );
}
