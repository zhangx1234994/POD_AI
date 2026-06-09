import { useEffect, useState } from "react";
import { Button, Layout, Menu, Space, Typography } from "tdesign-react";
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
  const [viewportWidth, setViewportWidth] = useState<number>(() => (typeof window === "undefined" ? 1440 : window.innerWidth));
  const [manualCompact, setManualCompact] = useState(false);
  const mobile = viewportWidth < 760;
  const compact = manualCompact || viewportWidth < 1240;
  const iconOnly = manualCompact || viewportWidth < 1024;
  const asideWidth = iconOnly ? 96 : compact ? 180 : 260;
  const showSideNav = showSidebar && !mobile;
  const showMobileNav = showSidebar && mobile && navItems.length > 0;

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const renderNavContent = (label: string, shortLabel?: string) => {
    if (!iconOnly) {
      return <span>{label}</span>;
    }
    return <span className="podi-eval-shell__nav-badge">{(shortLabel || label || "A").slice(0, 2).toUpperCase()}</span>;
  };

  return (
    <Layout className="podi-shell" style={{ height: "100dvh", minHeight: 0 }}>
      <Layout.Header className="podi-shell__header" style={{ padding: compact ? "10px 12px" : "12px 20px", height: "auto" }}>
        <div className="podi-eval-shell__header-inner">
          <div className="podi-eval-shell__header-title">
            <Space direction="vertical" size={2} style={{ minWidth: 0 }}>
              <Typography.Text strong>{title}</Typography.Text>
              {subtitle && !iconOnly ? <Typography.Text theme="secondary">{subtitle}</Typography.Text> : null}
            </Space>
          </div>
          <div className="podi-eval-shell__header-controls">
            <Space align="center" style={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
              {headerTabs}
              {headerActions}
              {!mobile ? (
                <Button size="small" variant="outline" onClick={() => setManualCompact((prev) => !prev)}>
                  {manualCompact ? "展开侧栏" : "收紧侧栏"}
                </Button>
              ) : null}
            </Space>
          </div>
        </div>
      </Layout.Header>
      <Layout style={{ minHeight: 0, flex: 1 }}>
        {showSideNav ? (
          <Layout.Aside className={`podi-shell__aside${iconOnly ? " podi-eval-shell__aside--icon" : ""}`} style={{ width: asideWidth, padding: compact ? 10 : 16, overflow: "auto" }}>
            <Space direction="vertical" size="small" style={{ width: "100%" }}>
              <div>
                {!iconOnly ? <Typography.Text theme="secondary">分类筛选</Typography.Text> : null}
                <Typography.Title level="h5" style={{ margin: "6px 0 0" }}>
                  {iconOnly ? "评测" : sidebarTitle}
                </Typography.Title>
                {!iconOnly ? <Typography.Text theme="secondary">{sidebarSubtitle}</Typography.Text> : null}
              </div>
              <Menu
                value={activeNav}
                theme={theme === "dark" ? "dark" : "light"}
                onChange={(value) => onSelectNav?.(String(value))}
              >
                {navItems.map((item) => (
                  <Menu.MenuItem key={item.id} value={item.id}>
                    <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
                      <span className="podi-eval-shell__nav-item-inner">
                        <span className="podi-eval-shell__nav-item-icon">{item.icon || renderNavContent(item.label, item.shortLabel)}</span>
                        {!iconOnly ? <span>{item.label}</span> : null}
                      </span>
                      {!iconOnly ? <Typography.Text theme="secondary">{item.count ?? 0}</Typography.Text> : null}
                    </Space>
                  </Menu.MenuItem>
                ))}
              </Menu>
            </Space>
          </Layout.Aside>
        ) : null}
        <Layout.Content className="podi-shell__content" style={{ padding: mobile ? 12 : 24, overflow: "auto", minHeight: 0 }}>
          <div ref={contentRef} className="podi-eval-shell__content-inner" style={{ maxWidth: mobile ? "none" : 1400, margin: "0 auto" }}>
            {showMobileNav ? (
              <nav className="podi-eval-shell__mobile-nav" aria-label={sidebarTitle}>
                {navItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`podi-eval-shell__mobile-nav-item${activeNav === item.id ? " podi-eval-shell__mobile-nav-item--active" : ""}`}
                    onClick={() => onSelectNav?.(String(item.id))}
                  >
                    <span className="podi-eval-shell__mobile-nav-icon">
                      {item.icon || <span>{(item.shortLabel || item.label || "A").slice(0, 2).toUpperCase()}</span>}
                    </span>
                    <span>{item.label}</span>
                    {item.count !== undefined ? <small>{item.count}</small> : null}
                  </button>
                ))}
              </nav>
            ) : null}
            {children}
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
