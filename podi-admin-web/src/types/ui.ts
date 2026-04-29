import type { ReactNode, RefObject } from "react";

export type ThemeMode = "light" | "dark";

export type UnifiedStatus =
  | "success"
  | "failed"
  | "running"
  | "queued"
  | "cancelled"
  | "inactive"
  | "unknown";

export type StatusBadgeTheme = "success" | "danger" | "warning" | "default" | "primary";

export type StatusBadgeMeta = {
  normalized: UnifiedStatus;
  theme: StatusBadgeTheme;
  text: string;
};

export type AppShellNavItem = {
  id: string;
  label: string;
  shortLabel?: string;
  icon?: ReactNode;
  description?: string;
  group?: string;
  groupLabel?: string;
  advanced?: boolean;
};

export type AppShellProps = {
  title: string;
  subtitle?: string;
  theme: ThemeMode;
  navItems: AppShellNavItem[];
  activeNav: string;
  onSelectNav: (id: string) => void;
  headerTitle: string;
  headerSubtitle?: string;
  headerActions?: ReactNode;
  contentRef?: RefObject<HTMLDivElement>;
  children: ReactNode;
};

export type PageSectionConfig = {
  id?: string;
  title: string;
  description?: string;
};
