import type { ReactNode, RefObject } from "react";

export type ThemeMode = "light" | "dark";

export type UnifiedStatus = "success" | "failed" | "running" | "queued" | "cancelled" | "unknown";

export type StatusBadgeTheme = "success" | "danger" | "warning" | "default" | "primary";

export type StatusBadgeMeta = {
  normalized: UnifiedStatus;
  theme: StatusBadgeTheme;
  text: string;
};

export type AppShellNavItem = {
  id: string;
  label: string;
  count?: number;
};

export type AppShellProps = {
  title: string;
  subtitle?: string;
  theme: ThemeMode;
  navItems?: AppShellNavItem[];
  activeNav?: string;
  onSelectNav?: (id: string) => void;
  showSidebar?: boolean;
  sidebarTitle?: string;
  sidebarSubtitle?: string;
  headerTabs?: ReactNode;
  headerActions?: ReactNode;
  contentRef?: RefObject<HTMLDivElement>;
  children: ReactNode;
};
