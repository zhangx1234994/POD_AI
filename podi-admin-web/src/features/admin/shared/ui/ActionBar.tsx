import { Space } from "tdesign-react";
import type { ReactNode } from "react";

export function ActionBar({ children }: { children: ReactNode }) {
  return (
    <div className="podi-action-bar">
      <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
        {children}
      </Space>
    </div>
  );
}
