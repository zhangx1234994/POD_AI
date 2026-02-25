import { Layout, Menu, Space, Tooltip, Typography } from "tdesign-react";
import type { AppShellProps } from "../types/ui";

export function AdminShell({
  title,
  subtitle,
  theme,
  navItems,
  activeNav,
  onSelectNav,
  headerTitle,
  headerActions,
  contentRef,
  children,
}: AppShellProps) {
  return (
    <Layout className="podi-shell" style={{ height: "100vh" }}>
      <Layout.Aside className="podi-shell__aside" style={{ width: 260, padding: 16, overflow: "auto" }}>
        <Space direction="vertical" size="small" style={{ width: "100%" }}>
          <div>
            <Typography.Text theme="secondary">控制台</Typography.Text>
            <Typography.Title level="h4" style={{ margin: "6px 0 0" }}>
              {title}
            </Typography.Title>
            {subtitle ? <Typography.Text theme="secondary">{subtitle}</Typography.Text> : null}
          </div>
          <Menu value={activeNav} theme={theme === "dark" ? "dark" : "light"} onChange={(value) => onSelectNav(String(value))}>
            {navItems.map((item) => (
              <Menu.MenuItem key={item.id} value={item.id}>
                <Tooltip content={item.description || item.label}>
                  <span>{item.label}</span>
                </Tooltip>
              </Menu.MenuItem>
            ))}
          </Menu>
        </Space>
      </Layout.Aside>

      <Layout>
        <Layout.Header className="podi-shell__header" style={{ padding: "0 16px" }}>
          <Space align="center" style={{ justifyContent: "space-between", width: "100%", height: "100%" }}>
            <Typography.Text strong>{headerTitle}</Typography.Text>
            {headerActions}
          </Space>
        </Layout.Header>
        <Layout.Content className="podi-shell__content" style={{ padding: 16, overflow: "hidden" }}>
          <div ref={contentRef} style={{ height: "100%", overflow: "auto" }}>
            {children}
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
