import { Space, Typography } from "tdesign-react";

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <Space direction="vertical" size={2} style={{ width: "100%" }} className="podi-page-header">
      <Typography.Title level="h4" style={{ margin: 0 }}>
        {title}
      </Typography.Title>
      {description ? <Typography.Text theme="secondary">{description}</Typography.Text> : null}
    </Space>
  );
}
