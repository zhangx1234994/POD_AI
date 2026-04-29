import { LoginGate } from './components/LoginGate';
import { lazy, Suspense, useEffect, useState } from 'react';
import { ConfigProvider } from 'tdesign-react';
import zhCN from 'tdesign-react/es/locale/zh_CN';

type ThemeMode = 'light' | 'dark';

const IntegrationDashboard = lazy(() =>
  import('./pages/IntegrationDashboard').then((mod) => ({ default: mod.IntegrationDashboard })),
);

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem('podi.admin.theme');
  return stored === 'dark' ? 'dark' : 'light';
}

function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme());

  useEffect(() => {
    const isDark = theme === 'dark';
    // TDesign dark mode is driven by `t-theme-dark` class.
    document.documentElement.classList.toggle('t-theme-dark', isDark);
    // Keep Tailwind dark variants working during migration.
    document.documentElement.classList.toggle('dark', isDark);
    window.localStorage.setItem('podi.admin.theme', theme);
  }, [theme]);

  return (
    <ConfigProvider globalConfig={zhCN}>
      <LoginGate>
        {(currentUser) => (
          <Suspense
            fallback={
              <div style={{ padding: 32, color: '#344054', fontSize: 14 }}>管理端加载中，请稍候...</div>
            }
          >
            <IntegrationDashboard
              theme={theme}
              currentUser={currentUser}
              onToggleTheme={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
            />
          </Suspense>
        )}
      </LoginGate>
    </ConfigProvider>
  );
}

export default App;
