import type { CSSProperties, ReactNode } from "react";
import { Alert, Card, Space, Tag, Typography } from "tdesign-react";

export type OperationFlowTheme = "success" | "warning" | "danger" | "primary" | "default";

export interface OperationFlowStep {
  key: string;
  title: string;
  detail: string;
  action: string;
  done: string;
  theme?: OperationFlowTheme;
  checks?: string[];
}

const tagTheme = (theme?: OperationFlowTheme): "success" | "warning" | "danger" | "primary" | "default" =>
  theme || "primary";

const alertTheme = (theme?: OperationFlowTheme): "success" | "warning" | "error" | "info" => {
  if (theme === "success") return "success";
  if (theme === "warning") return "warning";
  if (theme === "danger") return "error";
  return "info";
};

export function OperationFlowCard({
  title,
  description,
  summary,
  summaryTheme = "primary",
  steps,
  extra,
  style,
  className,
}: {
  title: string;
  description: string;
  summary?: string;
  summaryTheme?: OperationFlowTheme;
  steps: OperationFlowStep[];
  extra?: ReactNode;
  style?: CSSProperties;
  className?: string;
}) {
  if (steps.length === 0) return null;

  return (
    <Card
      bordered
      className={className}
      style={style}
      title={
        <Space align="center" style={{ justifyContent: "space-between", width: "100%", flexWrap: "wrap", gap: 12 }}>
          <div>
            <Typography.Text strong>{title}</Typography.Text>
            <div>
              <Typography.Text theme="secondary">{description}</Typography.Text>
            </div>
          </div>
          {extra}
        </Space>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        {summary ? <Alert theme={alertTheme(summaryTheme)} message={summary} /> : null}
        <div className="podi-operation-flow-grid">
          {steps.map((step, index) => {
            const theme = tagTheme(step.theme);
            return (
              <section key={step.key} className={`podi-operation-flow-item podi-operation-flow-item--${theme}`}>
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Space align="center" style={{ justifyContent: "space-between", width: "100%", gap: 8 }}>
                    <Tag theme={theme} variant="light">
                      第 {index + 1} 步
                    </Tag>
                    <Typography.Text theme="secondary">{step.done}</Typography.Text>
                  </Space>
                  <Typography.Text strong>{step.title}</Typography.Text>
                  <Typography.Text theme="secondary">{step.detail}</Typography.Text>
                  {step.checks && step.checks.length > 0 ? (
                    <ol className="podi-operation-flow-checks">
                      {step.checks.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ol>
                  ) : null}
                  <Typography.Text theme={theme === "danger" ? "error" : theme === "warning" ? "warning" : "secondary"}>
                    下一步：{step.action}
                  </Typography.Text>
                </Space>
              </section>
            );
          })}
        </div>
      </Space>
    </Card>
  );
}
