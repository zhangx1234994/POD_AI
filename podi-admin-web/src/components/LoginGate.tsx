import { useEffect, useState } from 'react';
import { adminAuthAPI } from '../services/authAPI';
import { ADMIN_TOKEN_INVALID_EVENT } from '../services/adminApi';
import type { AuthUser } from '../types/admin';

const ACCESS_TOKEN_KEY = 'podi_admin_access_token';
const REFRESH_TOKEN_KEY = 'podi_admin_refresh_token';
const CURRENT_USER_KEY = 'podi_admin_current_user';
const TOKEN_INVALID_FLAG = 'podi_admin_token_invalid';
const TOKEN_INVALID_AT_KEY = 'podi_admin_token_invalid_at';

type LoginGateChildren = React.ReactNode | ((currentUser: AuthUser | null) => React.ReactNode);

export function LoginGate({ children }: { children: LoginGateChildren }) {
  const [token, setToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
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
      localStorage.removeItem(CURRENT_USER_KEY);
      localStorage.removeItem(TOKEN_INVALID_FLAG);
      localStorage.removeItem(TOKEN_INVALID_AT_KEY);
      setToken(null);
      setCurrentUser(null);
      setError(invalidReason || '登录已失效，请重新登录');
    } else {
      const cached = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (cached) {
        setToken(cached);
        const cachedUser = localStorage.getItem(CURRENT_USER_KEY);
        if (cachedUser) {
          try {
            setCurrentUser(JSON.parse(cachedUser));
          } catch {
            localStorage.removeItem(CURRENT_USER_KEY);
          }
        }
      }
    }

    const handleTokenInvalid = (event: Event) => {
      const detail = (event as CustomEvent<{ message?: string }>).detail;
      setToken(null);
      setCurrentUser(null);
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
      if (resp.user) {
        localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(resp.user));
        setCurrentUser(resp.user);
      } else {
        localStorage.removeItem(CURRENT_USER_KEY);
        setCurrentUser(resp.role ? ({ role: resp.role } as AuthUser) : null);
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
    localStorage.removeItem(CURRENT_USER_KEY);
    setToken(null);
    setCurrentUser(null);
    setForm({ username: '', password: '' });
  };

  if (!token) {
    return (
      <div className="podi-login">
        <div className="podi-login__card">
          <div className="podi-login__intro">
            <div className="podi-login__intro-tag">PODI Console</div>
            <h1>管理中台统一入口</h1>
            <p>统一管理执行节点、能力目录、ComfyUI 同步发布、任务回执与告警。</p>
            <ul>
              <li>配置、发布、执行、回填统一追踪</li>
              <li>中台与测评端数据同源</li>
              <li>异常状态可定位、可复盘</li>
            </ul>
          </div>
          <div className="podi-login__form-panel">
            <div className="podi-login__title">登录管理控制台</div>
            <div className="podi-login__subtitle">使用后台账号继续，建议仅在内网环境访问。</div>
            <form className="podi-login__form" onSubmit={handleSubmit}>
              <div className="podi-login__field">
                <label>用户名 / 邮箱</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder="admin"
                />
              </div>
              <div className="podi-login__field">
                <label>密码</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                />
              </div>
              {error ? <div className="podi-login__error">{error}</div> : null}
              <button type="submit" disabled={loading} className="podi-login__submit">
                {loading ? '登录中...' : '进入控制台'}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="podi-login-session">
      <button onClick={handleSignOut} className="podi-login-session__signout">
        退出登录
      </button>
      {typeof children === 'function' ? children(currentUser) : children}
    </div>
  );
}
