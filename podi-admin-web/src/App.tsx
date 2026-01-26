import { LoginGate } from './components/LoginGate';
import { IntegrationDashboard } from './pages/IntegrationDashboard';
import { useEffect, useState } from 'react';

type ThemeMode = 'light' | 'dark';

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem('podi.admin.theme');
  return stored === 'dark' ? 'dark' : 'light';
}

function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme());

  useEffect(() => {
    const isDark = theme === 'dark';
    document.documentElement.classList.toggle('dark', isDark);
    window.localStorage.setItem('podi.admin.theme', theme);
  }, [theme]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-50">
      <LoginGate>
        <IntegrationDashboard theme={theme} onToggleTheme={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))} />
      </LoginGate>
    </div>
  );
}

export default App;
