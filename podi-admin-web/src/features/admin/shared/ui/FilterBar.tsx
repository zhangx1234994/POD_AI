import { Space } from "tdesign-react";
import type { ReactNode } from "react";

export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <div className="podi-filter-bar">
      <Space align="center" size="small" style={{ flexWrap: "wrap" }} className="podi-filter-bar__inner">
        {children}
      </Space>
    </div>
  );
}
