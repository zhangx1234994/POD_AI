import * as React from 'react';
import { useState, useEffect, useCallback, ReactNode } from 'react';
import { AuthContext, AuthContextType, User } from './AuthContext';
import { authAPI, removeToken } from '../utils/http';

interface AuthProviderProps {
  children: ReactNode;
}

const AuthProviderComponent: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 检查认证状态（基于JWT）
  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    try {
      // 先检查是否有token
      const token = localStorage.getItem('token');
      if (!token) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      const response = await authAPI.getCurrentUser();
      const data = response;
      if (data && data.user_id) {
        // 如果当前内存中已有相同用户，则避免重复 setUser 导致组件重复触发依赖于 user 的 effect
        // 这样可以避免像 fetchPointsStatistics 被触发多次这种重复请求的情况
        const currentUserId = (user && user.id) || null;
        if (currentUserId === String(data.user_id)) {
          setIsLoading(false);
          return;
        }

        setUser({
          id: data.user_id,
          username: data.username || data.user_id,
          nickname: data.nickname || data.username || data.user_id,
          email: data.email,
        });
        try {
          localStorage.setItem('userId', String(data.user_id));
          localStorage.setItem('X-User-Id', String(data.user_id));
          // 保存用户platform到localStorage，用于调试
          localStorage.setItem('platform', String(data.platform));
        } catch (e) {}
      } else {
        // 无有效用户信息，清除token并设置用户为null
        removeToken();
        setUser(null);
      }
    } catch (error) {
      // 会话无效，清除token并设置用户为null
      console.error('认证检查失败:', error);
      removeToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  // 登录函数
  const login = useCallback(async (username: string, password: string) => {
    try {
      const data = await authAPI.login(username, password);
      if (!data) throw new Error('登录响应数据为空');

      // 检查并保存token
      if (data.token) {
        localStorage.setItem('token', data.token);
      } else {
        throw new Error('登录响应中未找到token');
      }

      const userId = data.user_id || data.userId || data.id;
      if (userId) {
        // 保存用户ID到localStorage，用于调试
        localStorage.setItem('userId', String(userId));
        localStorage.setItem('X-User-Id', String(userId));
        // 保存用户platform到localStorage，用于调试
        localStorage.setItem('platform', String(data.platform));
        setUser({
          id: userId,
          username: data.username || username,
          nickname: data.nickname || data.username || username,
          email: data.email,
        });
        try {
          // 登录成功后，设置侧边栏为展开状态（仅登录后生效）
          localStorage.setItem('sidebar-collapsed', '0');
        } catch (e) {}
      } else {
        throw new Error('登录响应中未找到用户ID');
      }
    } catch (error) {
      console.error('登录错误:', error);
      throw error;
    }
  }, []);

  // 手机号验证码登录
  const loginPhone = useCallback(async (phone: string, code: string, agreed_privacy = true) => {
    try {
      const data = await authAPI.loginPhone(phone, code, agreed_privacy);
      if (!data) throw new Error('登录响应数据为空');

      // authAPI.loginPhone will set token if returned, but ensure token is present
      const token = localStorage.getItem('token');
      if (!token && data.token) {
        localStorage.setItem('token', data.token);
      }

      // 如果响应中包含用户ID，保存到localStorage以便请求拦截器使用
      const userId = data.user_id || data.userId || data.id;
      if (userId) {
        try {
          localStorage.setItem('userId', String(userId));
          localStorage.setItem('X-User-Id', String(userId));
          // 保存用户platform到localStorage，用于调试
          localStorage.setItem('platform', String(data.platform));
          setUser({
            id: userId,
            username: data.username || data.user_name || phone,
            nickname: data.nickname || data.username || data.user_name || phone,
            email: data.email,
          });
          try {
            // 登录成功后默认展开侧边栏（仅登录后生效）
            localStorage.setItem('sidebar-collapsed', '0');
          } catch (e) {}
        } catch (e) {}
      }

      // Refresh user info
      try {
        await checkAuth();
      } catch (e) {
        // ignore, higher-level callers will handle
      }
    } catch (error) {
      console.error('手机号登录错误:', error);
      throw error;
    }
  }, [checkAuth]);

  // 登出函数
  const logout = useCallback(async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('登出请求失败:', error);
    } finally {
      removeToken();
      localStorage.removeItem('userId');
      localStorage.removeItem('X-User-Id');
      localStorage.removeItem('platform');
      try {
        // 登出时清理侧边栏偏好，让未登录时恢复默认展开
        localStorage.removeItem('sidebar-collapsed');
      } catch (e) {}
      setUser(null);
      try {
        const ev = new CustomEvent('auth:logout');
        window.dispatchEvent(ev);
      } catch (e) {
        // ignore
      }
    }
  }, []);

  // 初始化时检查认证状态
  useEffect(() => {
    // 仅在有token时才尝试检查认证状态
    const token = localStorage.getItem('token');
    if (token) {
      checkAuth();
    } else {
      setIsLoading(false);
    }
  }, [checkAuth]);

  // 监听401错误事件
  useEffect(() => {
    const handleUnauthorized = () => {
      // 清理会话相关的内存态和本地存储
      removeToken();
      localStorage.removeItem('userId');
      localStorage.removeItem('X-User-Id');
      localStorage.removeItem('platform');
      setUser(null);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, []);

  const contextValue: AuthContextType = React.useMemo(
    () => ({
      user,
      isLoading,
      login,
      logout,
      checkAuth,
      loginPhone,
    }),
    [user, isLoading, login, logout, checkAuth, loginPhone]
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
};

// 创建并导出稳定的AuthProvider
export const AuthProvider = AuthProviderComponent;
