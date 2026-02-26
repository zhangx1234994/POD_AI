import type { ReactNode } from "react";
import { Space, Typography } from "tdesign-react";

type ActionBarProps = {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
};

export function ActionBar({ title, description, actions }: ActionBarProps) {
  return (
    <div className="podi-action-bar">
      <Space direction="vertical" size={2} style={{ minWidth: 240 }}>
        <Typography.Text strong>{title}</Typography.Text>
        {description ? <Typography.Text theme="secondary">{description}</Typography.Text> : null}
      </Space>
      {actions ? <div className="podi-action-bar__actions">{actions}</div> : null}
    </div>
  );
}
