import { useMemo, useState } from "react";
import { Input, Layout, Menu, Space, Tooltip, Typography } from "tdesign-react";
import type { AppShellProps } from "../types/ui";

export function AdminShell({
  title,
  subtitle,
  theme,
  navItems,
  activeNav,
  onSelectNav,
  headerTitle,
  headerSubtitle,
  headerActions,
  contentRef,
  children,
}: AppShellProps) {
  const [navKeyword, setNavKeyword] = useState("");
  const filteredNavItems = useMemo(() => {
    const keyword = navKeyword.trim().toLowerCase();
    if (!keyword) return navItems;
    return navItems.filter((item) => {
      const label = String(item.label || "").toLowerCase();
      const description = String(item.description || "").toLowerCase();
      return label.includes(keyword) || description.includes(keyword);
    });
  }, [navItems, navKeyword]);
  const coreItems = filteredNavItems.filter((item) => !item.advanced);
  const advancedItems = filteredNavItems.filter((item) => item.advanced);
  const hasNavResult = coreItems.length > 0 || advancedItems.length > 0;

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
          <Input
            size="small"
            clearable
            value={navKeyword}
            placeholder="搜索模块（如：能力 / 监控）"
            onChange={(value) => setNavKeyword(String(value))}
          />
          {!hasNavResult ? (
            <div className="podi-shell__nav-empty">
              <Typography.Text theme="secondary">未找到匹配模块，请换个关键词。</Typography.Text>
            </div>
          ) : null}
          <div className="podi-shell__nav-section">
            <Typography.Text theme="secondary">核心模块</Typography.Text>
            <Menu value={activeNav} theme={theme === "dark" ? "dark" : "light"} onChange={(value) => onSelectNav(String(value))}>
              {coreItems.map((item) => (
                <Menu.MenuItem key={item.id} value={item.id}>
                  <Tooltip content={item.description || item.label}>
                    <span>{item.label}</span>
                  </Tooltip>
                </Menu.MenuItem>
              ))}
            </Menu>
          </div>
          {advancedItems.length > 0 ? (
            <div className="podi-shell__nav-section">
              <Typography.Text theme="secondary">高级模块</Typography.Text>
              <Menu value={activeNav} theme={theme === "dark" ? "dark" : "light"} onChange={(value) => onSelectNav(String(value))}>
                {advancedItems.map((item) => (
                  <Menu.MenuItem key={item.id} value={item.id}>
                    <Tooltip content={item.description || item.label}>
                      <span>{item.label}</span>
                    </Tooltip>
                  </Menu.MenuItem>
                ))}
              </Menu>
            </div>
          ) : null}
        </Space>
      </Layout.Aside>

      <Layout>
        <Layout.Header className="podi-shell__header" style={{ padding: "0 16px" }}>
          <Space align="center" style={{ justifyContent: "space-between", width: "100%", height: "100%" }}>
            <Space direction="vertical" size={2}>
              <Typography.Text strong>{headerTitle}</Typography.Text>
              {headerSubtitle ? <Typography.Text theme="secondary">{headerSubtitle}</Typography.Text> : null}
            </Space>
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
