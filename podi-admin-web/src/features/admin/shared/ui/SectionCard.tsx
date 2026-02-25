import { Card } from "tdesign-react";
import type { ReactNode } from "react";

export function SectionCard({ title, extra, children }: { title?: ReactNode; extra?: ReactNode; children: ReactNode }) {
  return (
    <Card bordered title={title} actions={extra}>
      {children}
    </Card>
  );
}
