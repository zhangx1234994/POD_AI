import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

interface SidebarContextValue {
  collapsed: boolean;
  setCollapsed: (v: boolean | ((p: boolean) => boolean)) => void;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue>({
  collapsed: false,
  setCollapsed: () => {},
  toggle: () => {},
});

export const SidebarProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [collapsed, setCollapsedState] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('sidebar-collapsed');
      return v === '1';
    } catch (e) {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
    } catch (e) {
      // ignore
    }
  }, [collapsed]);

  const setCollapsed = useCallback((v: boolean | ((p: boolean) => boolean)) => {
    setCollapsedState((prev) => (typeof v === 'function' ? (v as any)(prev) : v));
  }, []);

  const toggle = useCallback(() => setCollapsedState((c) => !c), []);

  // backward compatibility: dispatch a window event when collapsed changes
  useEffect(() => {
    try {
      const ev = new CustomEvent('sidebar:toggle', { detail: { collapsed } });
      window.dispatchEvent(ev);
    } catch (e) {
      // ignore
    }
  }, [collapsed]);

  // 监听登出事件，登出后将侧边栏恢复为展开状态
  useEffect(() => {
    const handleLogout = () => {
      try {
        setCollapsedState(false);
        // 同步 localStorage 写入由 useEffect([collapsed]) 负责
      } catch (e) {
        // ignore
      }
    };

    window.addEventListener('auth:logout', handleLogout as EventListener);
    return () => window.removeEventListener('auth:logout', handleLogout as EventListener);
  }, [setCollapsedState]);

  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed, toggle }}>
      {children}
    </SidebarContext.Provider>
  );
};

export const useSidebar = () => useContext(SidebarContext);

export default SidebarContext;
