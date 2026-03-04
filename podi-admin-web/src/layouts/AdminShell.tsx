import { useEffect, useMemo, useState } from "react";
import { Button, Input, Layout, Menu, Space, Tooltip, Typography } from "tdesign-react";
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
  const [viewportWidth, setViewportWidth] = useState<number>(() => (typeof window === "undefined" ? 1440 : window.innerWidth));
  const [manualCompactNav, setManualCompactNav] = useState<boolean>(false);
  const compactNav = manualCompactNav || viewportWidth < 1280;
  const iconOnlyNav = manualCompactNav || viewportWidth < 1040;
  const ultraNarrowNav = viewportWidth < 920;
  const asideWidth = ultraNarrowNav ? 76 : iconOnlyNav ? 88 : compactNav ? 204 : 248;
  const headerPadding = ultraNarrowNav ? "6px 10px" : compactNav ? "8px 12px" : "8px 16px";
  const contentPadding = ultraNarrowNav ? 10 : compactNav ? 12 : 16;
  const compactTitle = iconOnlyNav ? "AI" : "AI 管理";

  const renderNavContent = (label: string, shortLabel?: string) => {
    if (!iconOnlyNav) return <span>{label}</span>;
    const badge = (shortLabel || label || "M")
      .replace(/\s+/g, "")
      .slice(0, 2)
      .toUpperCase();
    return <span className="podi-shell__nav-badge">{badge}</span>;
  };

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  useEffect(() => {
    if (!iconOnlyNav) return;
    if (!navKeyword) return;
    setNavKeyword("");
  }, [iconOnlyNav, navKeyword]);
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
    <Layout className="podi-shell" style={{ height: "100vh", minWidth: 0 }}>
      <Layout.Aside
        width={`${asideWidth}px`}
        className={`podi-shell__aside${iconOnlyNav ? " podi-shell__aside--icon-only" : ""}`}
        style={{ padding: compactNav ? 10 : 14, overflow: "auto" }}
      >
        <Space direction="vertical" size="small" style={{ width: "100%" }}>
          <div>
            <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
              {!iconOnlyNav ? <Typography.Text theme="secondary">控制台</Typography.Text> : <span />}
              <Button
                size="small"
                variant="text"
                onClick={() => setManualCompactNav((prev) => !prev)}
                style={{ padding: 0, minWidth: 0 }}
              >
                {manualCompactNav ? "展开" : "收起"}
              </Button>
            </Space>
            <Typography.Title level="h4" style={{ margin: "4px 0 0" }}>
              {ultraNarrowNav || compactNav ? compactTitle : title}
            </Typography.Title>
            {!ultraNarrowNav && !compactNav && subtitle ? <Typography.Text theme="secondary">{subtitle}</Typography.Text> : null}
          </div>
          {!iconOnlyNav ? (
            <Input
              size="small"
              clearable
              value={navKeyword}
              placeholder={compactNav ? "搜索模块" : "搜索模块（如：能力 / 监控）"}
              onChange={(value) => setNavKeyword(String(value))}
            />
          ) : null}
          {!hasNavResult ? (
            <div className="podi-shell__nav-empty">
              <Typography.Text theme="secondary">未找到匹配模块，请换个关键词。</Typography.Text>
            </div>
          ) : null}
          <div className="podi-shell__nav-section">
            {!iconOnlyNav ? <Typography.Text theme="secondary">核心模块</Typography.Text> : null}
            <Menu value={activeNav} theme={theme === "dark" ? "dark" : "light"} onChange={(value) => onSelectNav(String(value))}>
              {coreItems.map((item) => (
                <Menu.MenuItem key={item.id} value={item.id}>
                  <Tooltip content={item.description || item.label}>
                    <span className="podi-shell__nav-item-inner">
                      <span className="podi-shell__nav-item-icon">
                        {item.icon || renderNavContent(item.label, item.shortLabel)}
                      </span>
                      {!iconOnlyNav ? <span>{item.label}</span> : null}
                    </span>
                  </Tooltip>
                </Menu.MenuItem>
              ))}
            </Menu>
          </div>
          {advancedItems.length > 0 ? (
            <div className="podi-shell__nav-section">
              {!iconOnlyNav ? <Typography.Text theme="secondary">高级模块</Typography.Text> : null}
              <Menu value={activeNav} theme={theme === "dark" ? "dark" : "light"} onChange={(value) => onSelectNav(String(value))}>
                {advancedItems.map((item) => (
                  <Menu.MenuItem key={item.id} value={item.id}>
                    <Tooltip content={item.description || item.label}>
                      <span className="podi-shell__nav-item-inner">
                        <span className="podi-shell__nav-item-icon">
                          {item.icon || renderNavContent(item.label, item.shortLabel)}
                        </span>
                        {!iconOnlyNav ? <span>{item.label}</span> : null}
                      </span>
                    </Tooltip>
                  </Menu.MenuItem>
                ))}
              </Menu>
            </div>
          ) : null}
        </Space>
      </Layout.Aside>

      <Layout style={{ minWidth: 0 }}>
        <Layout.Header className="podi-shell__header" style={{ padding: headerPadding, height: "auto" }}>
          <div className="podi-shell__header-inner">
            <Space direction="vertical" size={2} style={{ minWidth: 0 }}>
              <Typography.Text strong>{headerTitle}</Typography.Text>
              {!ultraNarrowNav && headerSubtitle ? <Typography.Text theme="secondary">{headerSubtitle}</Typography.Text> : null}
            </Space>
            {headerActions ? <div className="podi-shell__header-actions">{headerActions}</div> : null}
          </div>
        </Layout.Header>
        <Layout.Content className="podi-shell__content" style={{ padding: contentPadding, overflow: "hidden", minWidth: 0 }}>
          <div className="podi-shell__content-scroll" ref={contentRef}>
            {children}
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
