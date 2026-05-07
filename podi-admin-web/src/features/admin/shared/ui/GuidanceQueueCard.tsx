import type { CSSProperties } from "react";
import { Alert, Button, Card, Col, Row, Space, Tag, Typography } from "tdesign-react";

export type GuidanceQueueTheme = "success" | "warning" | "danger" | "primary" | "default";

export interface GuidanceQueueItem {
  key: string;
  title: string;
  detail: string;
  theme: GuidanceQueueTheme;
  action?: string;
  priority?: string;
  onClick?: () => void;
  loading?: boolean;
}

const toAlertTheme = (theme: GuidanceQueueTheme): "success" | "warning" | "error" | "info" => {
  if (theme === "success") return "success";
  if (theme === "danger") return "error";
  if (theme === "warning") return "warning";
  return "info";
};

const toTextTheme = (theme: GuidanceQueueTheme): "error" | "warning" | "secondary" => {
  if (theme === "danger") return "error";
  if (theme === "warning") return "warning";
  return "secondary";
};

export function GuidanceQueueCard({
  title = "当前先处理什么",
  items,
  maxItems = 4,
  summary,
  style,
}: {
  title?: string;
  items: GuidanceQueueItem[];
  maxItems?: number;
  summary?: string;
  style?: CSSProperties;
}) {
  const visibleItems = items.slice(0, maxItems);
  const firstItem = visibleItems[0];
  if (!firstItem) return null;
  const summaryMessage = summary || [firstItem.priority, firstItem.action || firstItem.title].filter(Boolean).join("：");

  return (
    <Card bordered title={title} style={style}>
      <Space direction="vertical" size="small" style={{ width: "100%" }}>
        {summaryMessage ? <Alert theme={toAlertTheme(firstItem.theme)} message={summaryMessage} /> : null}
        <Row gutter={[12, 12]}>
          {visibleItems.map((item) => (
            <Col key={item.key} xs={12} lg={visibleItems.length === 1 ? 12 : 12 / Math.min(visibleItems.length, 4)}>
              <div className="h-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Space size={6} breakLine>
                    {item.priority ? (
                      <Tag theme={item.theme} variant="light">
                        {item.priority}
                      </Tag>
                    ) : null}
                    <Tag theme={item.theme} variant="light">
                      {item.title}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  {item.onClick ? (
                    <Button size="small" variant="outline" loading={item.loading} onClick={item.onClick}>
                      {item.action || "查看"}
                    </Button>
                  ) : item.action ? (
                    <Typography.Text theme={toTextTheme(item.theme)}>建议：{item.action}</Typography.Text>
                  ) : null}
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Space>
    </Card>
  );
}
