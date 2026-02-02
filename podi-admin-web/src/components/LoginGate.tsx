import { useEffect, useState } from 'react';
import { adminAuthAPI } from '../services/authAPI';
import { ADMIN_TOKEN_INVALID_EVENT } from '../services/adminApi';

const ACCESS_TOKEN_KEY = 'podi_admin_access_token';
const REFRESH_TOKEN_KEY = 'podi_admin_refresh_token';
const TOKEN_INVALID_FLAG = 'podi_admin_token_invalid';
const TOKEN_INVALID_AT_KEY = 'podi_admin_token_invalid_at';

export function LoginGate({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [form, setForm] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const invalidReason = localStorage.getItem(TOKEN_INVALID_FLAG);
    if (invalidReason) {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(TOKEN_INVALID_FLAG);
      localStorage.removeItem(TOKEN_INVALID_AT_KEY);
      setToken(null);
      setError(invalidReason || '登录已失效，请重新登录');
    } else {
      const cached = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (cached) {
        setToken(cached);
      }
    }

    const handleTokenInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ message?: string }>).detail;
      setToken(null);
      setError(detail?.message || '登录已失效，请重新登录');
    };
    window.addEventListener(ADMIN_TOKEN_INVALID_EVENT, handleTokenInvalid);
    return () => {
      window.removeEventListener(ADMIN_TOKEN_INVALID_EVENT, handleTokenInvalid);
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    const clearStrayDialogMask = () => {
      const dialogs = Array.from(document.querySelectorAll('.t-dialog')) as HTMLElement[];
      const hasVisibleDialog = dialogs.some((el) => el.offsetParent !== null);
      if (hasVisibleDialog) return;
      const masks = Array.from(document.querySelectorAll('.t-dialog__mask')) as HTMLElement[];
      if (masks.length === 0) return;
      masks.forEach((m) => m.parentElement?.removeChild(m));
      document.body.style.removeProperty('overflow');
    };
    clearStrayDialogMask();
    const timer = window.setInterval(clearStrayDialogMask, 1500);
    return () => window.clearInterval(timer);
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.username || !form.password) {
      setError('请输入用户名和密码');
      return;
    }
    setLoading(true);
    setError(null);
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      setLoading(false);
      setError('登录超时，请检查网络或服务是否可用');
    }, 20000);
    try {
      const resp = await adminAuthAPI.login(form.username, form.password);
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      localStorage.setItem(ACCESS_TOKEN_KEY, resp.accessToken);
      if (resp.refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, resp.refreshToken);
      }
      setToken(resp.accessToken);
      setForm({ username: '', password: '' });
    } catch (err) {
      if (!settled) {
        settled = true;
        window.clearTimeout(timeoutId);
        console.error('login failed', err);
        setError(err instanceof Error ? err.message : '登录失败，请检查网络或服务状态');
      }
    } finally {
      if (!settled) {
        settled = true;
        window.clearTimeout(timeoutId);
      }
      setLoading(false);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setToken(null);
    setForm({ username: '', password: '' });
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 px-4">
        <div className="w-full max-w-md rounded-3xl border border-slate-800/70 bg-slate-900/80 p-10 shadow-[0_35px_120px_rgba(0,0,0,0.45)] backdrop-blur">
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">PODI Studio</p>
            <h1 className="text-3xl font-semibold text-white mt-2">管理员登录</h1>
            <p className="text-sm text-slate-400 mt-2">使用后台账号进入控制台，管理执行节点、工作流与接口配置。</p>
          </div>
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs uppercase tracking-[0.2em] text-slate-500 mb-2">用户名 / 邮箱</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/30"
                placeholder="admin"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.2em] text-slate-500 mb-2">密码</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/30"
                placeholder="••••••••"
              />
            </div>
            {error && <p className="text-sm text-red-400 text-center">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-500 px-4 py-3 font-semibold text-white shadow-lg shadow-sky-500/30 hover:from-sky-400 hover:to-indigo-400 disabled:opacity-50"
            >
              {loading ? '登录中...' : '进入控制台'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div>
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-950/70">
        <div>
          <h2 className="text-lg font-semibold text-white">PODI 管理控制台</h2>
          <p className="text-xs text-slate-400">独立入口 · 仅限管理员访问</p>
        </div>
        <button onClick={handleSignOut} className="text-sm text-slate-300 hover:text-white">
          退出
        </button>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
