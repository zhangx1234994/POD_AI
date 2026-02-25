import { Alert } from "tdesign-react";
import type { ReactNode } from "react";

export function ErrorState({ title, children }: { title: string; children?: ReactNode }) {
  return <Alert theme="error" title={title} message={children} />;
}
