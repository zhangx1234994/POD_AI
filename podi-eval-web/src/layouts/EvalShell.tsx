import { Layout, Menu, Space, Typography } from "tdesign-react";
import type { AppShellProps } from "../types/ui";

export function EvalShell({
  title,
  subtitle,
  theme,
  navItems = [],
  activeNav = '',
  onSelectNav,
  showSidebar = true,
  sidebarTitle = '测试大类',
  sidebarSubtitle = '选择分类后，右侧展示对应能力卡片。',
  headerTabs,
  headerActions,
  contentRef,
  children,
}: AppShellProps) {
  return (
    <Layout className="podi-shell" style={{ height: "100vh" }}>
      <Layout.Header className="podi-shell__header" style={{ padding: "0 24px" }}>
        <Space align="center" style={{ justifyContent: "space-between", width: "100%", height: "100%" }}>
          <Space direction="vertical" size={2}>
            <Typography.Text strong>{title}</Typography.Text>
            {subtitle ? <Typography.Text theme="secondary">{subtitle}</Typography.Text> : null}
          </Space>
          <Space align="center">
            {headerTabs}
            {headerActions}
          </Space>
        </Space>
      </Layout.Header>
      <Layout>
        {showSidebar ? (
          <Layout.Aside className="podi-shell__aside" style={{ width: 260, padding: 16, overflow: "auto" }}>
            <Space direction="vertical" size="small" style={{ width: "100%" }}>
              <div>
                <Typography.Text theme="secondary">分类筛选</Typography.Text>
                <Typography.Title level="h5" style={{ margin: "6px 0 0" }}>
                  {sidebarTitle}
                </Typography.Title>
                <Typography.Text theme="secondary">{sidebarSubtitle}</Typography.Text>
              </div>
              <Menu
                value={activeNav}
                theme={theme === "dark" ? "dark" : "light"}
                onChange={(value) => onSelectNav?.(String(value))}
              >
                {navItems.map((item) => (
                  <Menu.MenuItem key={item.id} value={item.id}>
                    <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
                      <span>{item.label}</span>
                      <Typography.Text theme="secondary">{item.count ?? 0}</Typography.Text>
                    </Space>
                  </Menu.MenuItem>
                ))}
              </Menu>
            </Space>
          </Layout.Aside>
        ) : null}
        <Layout.Content className="podi-shell__content" style={{ padding: 24, overflow: "auto" }}>
          <div ref={contentRef} style={{ maxWidth: 1400, margin: "0 auto" }}>
            {children}
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
