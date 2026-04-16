import { useMemo, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { navItems } from '../config/clientCatalog';
import { useWalletSnapshot } from '../hooks/useWalletSnapshot';
import LoginDialog from './LoginDialog';

export default function TopNav() {
  const { auth, isAuthenticated, logout } = useAuth();
  const [loginVisible, setLoginVisible] = useState(false);
  const { balance } = useWalletSnapshot(auth?.user.id);

  const primaryNav = useMemo(
    () => navItems.filter((item) => ['home', 'studio', 'design', 'shoot', 'toolbox'].includes(item.key)),
    [],
  );

  return (
    <>
      <nav className="client-topbar">
        <Link to="/home" className="client-topbar__brand">
          <div className="client-topbar__logo">P</div>
          <div className="client-topbar__brand-copy">
            <div className="client-topbar__name">PODI Studio</div>
            <div className="client-topbar__tag">Fashion Design Production Platform</div>
          </div>
        </Link>

        <div className="client-topbar__nav">
          {primaryNav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `client-topbar__link${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="client-topbar__actions">
          <NavLink
            to="/tasks"
            className={({ isActive }) => `client-topbar__utility${isActive ? ' is-active' : ''}`}
            title="任务中心"
          >
            <span className="client-topbar__utility-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
                <rect x="9" y="3" width="6" height="4" rx="1" />
                <path d="M9 12h6" />
                <path d="M9 16h6" />
              </svg>
            </span>
            <span className="client-topbar__utility-copy">
              <small>回看</small>
              <strong>任务中心</strong>
            </span>
          </NavLink>

          <NavLink
            to="/assets"
            className={({ isActive }) => `client-topbar__utility${isActive ? ' is-active' : ''}`}
            title="资产与模板中心"
          >
            <span className="client-topbar__utility-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
            </span>
            <span className="client-topbar__utility-copy">
              <small>沉淀</small>
              <strong>资产中心</strong>
            </span>
          </NavLink>

          <div className="client-balance-chip">
            <div className="client-balance-chip__value">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v12" />
                <path d="M15 9.5a3 3 0 1 0 0 5" />
              </svg>
              {typeof balance === 'number' ? balance.toLocaleString() : '--'}
            </div>
            <Link to="/wallet" className="client-balance-chip__action">
              套餐
            </Link>
          </div>

          {isAuthenticated ? (
            <button className="client-topbar__session" type="button" onClick={logout}>
              <span>{auth?.user.role || '已登录'}</span>
              <strong>退出</strong>
            </button>
          ) : (
            <button className="client-primary-button" type="button" onClick={() => setLoginVisible(true)}>
              登录体验真实链路
            </button>
          )}
        </div>
      </nav>

      <LoginDialog visible={loginVisible} onClose={() => setLoginVisible(false)} />
    </>
  );
}
