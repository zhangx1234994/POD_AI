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
    const clearStrayDialogMask = () => {
      const dialogs = Array.from(document.querySelectorAll('.t-dialog, .t-drawer')) as HTMLElement[];
      const hasVisibleDialog = dialogs.some((el) => el.offsetParent !== null);
      if (hasVisibleDialog) return;
      const masks = Array.from(
        document.querySelectorAll('.t-dialog__mask, .t-drawer__mask'),
      ) as HTMLElement[];
      if (masks.length === 0) return;
      masks.forEach((m) => m.parentElement?.removeChild(m));
      document.body.style.removeProperty('overflow');
    };
    clearStrayDialogMask();
    const timer = window.setInterval(clearStrayDialogMask, 1500);
    return () => window.clearInterval(timer);
  }, []);

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
      const dialogs = Array.from(document.querySelectorAll('.t-dialog, .t-drawer')) as HTMLElement[];
      const hasVisibleDialog = dialogs.some((el) => el.offsetParent !== null);
      if (hasVisibleDialog) return;
      const masks = Array.from(
        document.querySelectorAll('.t-dialog__mask, .t-drawer__mask'),
      ) as HTMLElement[];
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
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#dbeafe_0%,_#f8fafc_35%,_#e2e8f0_100%)] px-4 py-10">
        <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_28px_80px_rgba(15,23,42,0.18)] lg:grid-cols-[1.1fr_1fr]">
          <div className="relative hidden bg-[linear-gradient(145deg,#0f172a_0%,#1e293b_55%,#0f172a_100%)] p-10 text-slate-100 lg:block">
            <div className="absolute right-[-40px] top-[-40px] h-40 w-40 rounded-full bg-cyan-400/20 blur-2xl" />
            <div className="absolute bottom-[-50px] left-[-30px] h-44 w-44 rounded-full bg-indigo-400/20 blur-2xl" />
            <p className="relative text-xs uppercase tracking-[0.3em] text-slate-400">PODI Console</p>
            <h1 className="relative mt-4 text-3xl font-semibold leading-tight">
              管理中台
              <br />
              统一控制入口
            </h1>
            <p className="relative mt-4 text-sm leading-7 text-slate-300">
              在一个入口里管理执行节点、能力目录、ComfyUI 同步发布和任务追踪。
            </p>
            <ul className="relative mt-8 space-y-3 text-sm text-slate-200">
              <li>• 节点与资源清单统一管理</li>
              <li>• 回执、告警、版本差异可追踪</li>
              <li>• 测评端和中台数据同源</li>
            </ul>
          </div>
          <div className="p-7 sm:p-10">
            <div className="mb-6">
              <p className="text-xs uppercase tracking-[0.26em] text-slate-400">Admin Access</p>
              <h2 className="mt-2 text-3xl font-semibold text-slate-900">登录管理控制台</h2>
              <p className="mt-2 text-sm text-slate-500">使用后台账号继续，建议仅在内网环境访问。</p>
            </div>
            <form className="space-y-5" onSubmit={handleSubmit}>
              <div>
                <label className="mb-2 block text-xs uppercase tracking-[0.2em] text-slate-500">用户名 / 邮箱</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
                  placeholder="admin"
                />
              </div>
              <div>
                <label className="mb-2 block text-xs uppercase tracking-[0.2em] text-slate-500">密码</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
                  placeholder="••••••••"
                />
              </div>
              {error ? <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-500">{error}</p> : null}
              <button
                type="submit"
                disabled={loading}
                className="mt-2 w-full rounded-xl bg-gradient-to-r from-sky-600 to-blue-600 px-4 py-3 font-semibold text-white shadow-lg shadow-sky-500/20 transition hover:from-sky-500 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? '登录中...' : '进入控制台'}
              </button>
            </form>
          </div>
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
