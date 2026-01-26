import { LoginGate } from './components/LoginGate';
import { IntegrationDashboard } from './pages/IntegrationDashboard';
import { useEffect, useState } from 'react';
import { ConfigProvider } from 'tdesign-react';
import zhCN from 'tdesign-react/es/locale/zh_CN';

type ThemeMode = 'light' | 'dark';

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
        <IntegrationDashboard
          theme={theme}
          onToggleTheme={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
        />
      </LoginGate>
    </ConfigProvider>
  );
}

export default App;
